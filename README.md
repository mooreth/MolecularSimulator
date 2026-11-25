# MolecularSimulator

**Interactive atomistic simulation and molecular-machine control using LAMMPS, Python, and SAMSON.**

> **Release status: Public alpha — Pass 2.4**  
> This is an experimental research prototype. It has a working carbon-molecule demonstration and tested multi-motor controls, but it is not yet a general-purpose molecular simulation front end.

MolecularSimulator connects a running LAMMPS simulation to a live molecular structure in SAMSON. Python coordinates the simulation, receives Interactive Molecular Dynamics (IMD) frames, forwards atomic coordinates to SAMSON, and translates keyboard input into prescribed motion of selected atom groups.

The initial development focus is **carbon-based molecular systems**, including diamond mechanosynthesis and atomically precise machines. The current example uses two C60 fullerenes and the AIREBO potential.

## Development and AI assistance

MolecularSimulator was developed by **Tom Moore** in an extended human–AI engineering collaboration. Tom established the research goals and requirements, directed the architecture and design decisions, evaluated implementation choices, and carried out integration testing in his SAMSON/LAMMPS environment. **ChatGPT (OpenAI, GPT-6)** provided substantial assistance with software design, code generation, refactoring, debugging, and technical documentation.

This acknowledgement records the actual development process; it does not designate an AI system as a legal author, copyright holder, or representative of OpenAI. See [AI_ASSISTANCE.md](AI_ASSISTANCE.md) for the project's attribution approach.

## What it can do now

- Stream atom coordinates from LAMMPS to a live SAMSON model.
- Control multiple independently configured molecular groups.
- Prescribe linear translation along configurable global XYZ axes.
- Prescribe rotation around a configurable axis and pivot.
- Configure network ports, file paths, keyboard bindings, motor speeds, and simulation update cadence in one TOML file.
- Discover SAMSON structural groups and export their atom memberships as LAMMPS groups.

## Demonstration system

The repository includes `c60_240_collide.data`, a 300-atom, two-fullerene carbon system. The supplied `simulation.in` uses AIREBO and integrates the generated `free` group. The default configuration defines two motors:

| Group | Forward | Stop | Reverse | Example axis |
|---|---|---|---|---|
| `motor1` | J | K | L | +X |
| `motor2` | F | G | H | +Y |
| `motor3` (optional rotation example) | U | I | O | +Z |

`motor3` is commented out in `IMD_client/config.toml`; enable it only after creating and exporting a SAMSON group with that name.

## Architecture

```text
SAMSON Python environment
  SAMSON_run.py
      |  creates the visualization model
      |  receives coordinate updates on TCP port 5679
      v
  Live SAMSON molecular structure
      ^
      |  TCP coordinate frames
      |
Python controller (main.py) <---- keyboard input
      |
      |  LAMMPS Python API
      v
LAMMPS simulation
      |
      |  IMD stream (default port 5678)
      v
IMDClient receiver thread
```

The application supports both a single-machine setup and a split remote-compute setup.

### Remote compute: Linux LAMMPS + Windows SAMSON

The validated remote arrangement uses two computers:

- **Linux compute node (Node3):** runs the MolecularSimulator Python controller and LAMMPS locally.
- **Windows workstation:** runs SAMSON and the SAMSON-side `SAMSON_run.py` TCP receiver.

```text
Windows workstation                                  Linux compute node
SAMSON + SAMSON_run.py                               main.py + Python LAMMPS
TCP receiver: 0.0.0.0:5679  <--- coordinate frames ---  samson_host = Windows LAN IP
                                                       LAMMPS fix imd :5678
                         <--- local IMD stream -------  imd_host = 127.0.0.1
```

The two network settings have different roles:

- `imd_host` is the address used by the controller's IMD receiver to connect to the LAMMPS IMD listener. When LAMMPS and the controller run on the same Linux node, use `127.0.0.1`.
- `samson_host` is the address used by the controller to connect to the SAMSON receiver. On the Linux compute node, set this to the Windows workstation's reachable LAN IP address.
- On the Windows SAMSON workstation, `samson_host` is the receiver bind address; use `0.0.0.0` to listen on the workstation's network interfaces.

The default ports are **5678** for IMD and **5679** for the SAMSON coordinate stream. Permit inbound TCP port 5679 through the Windows firewall for the private network. Keep the IMD connection local to the Linux compute node unless you intentionally deploy LAMMPS and its controller on separate hosts.

Use a separate machine-specific `config.toml` on each computer. Do not copy the Windows receiver's `samson_host = "0.0.0.0"` setting onto the Linux controller: the Linux controller must connect to the Windows workstation's actual LAN address. See [docs/INSTALLATION.md](docs/INSTALLATION.md) for example configurations and startup order.

### Local single-machine setup

For a local setup, the controller, LAMMPS, and SAMSON can use loopback networking. Configure the two host values for the local arrangement and keep the ports consistent with both endpoints.

## Requirements

The tested development environment for Pass 2.4 was:

- **Windows visualization workstation:** SAMSON 2026 R1 and its embedded Python/Qt environment.
- **Linux remote compute node:** Ubuntu 22.04.4 LTS, Python 3.11, and LAMMPS 30 Sep 2026 Update 1 with its Python interface and required packages.
- The remote setup uses a TCP connection from the Linux controller to the Windows SAMSON receiver.

You will need:

1. A working SAMSON installation with its Python console and Qt/PySide6 environment.
2. LAMMPS built/installed with the Python module and shared library available to the Python interpreter that runs `main.py`.
3. LAMMPS support for the **MOLECULE** package (for `atom_style molecular`), **IMD** fix/package, and **MANYBODY** package (for AIREBO) for the supplied remote example.
4. Python 3.11 or later, NumPy, and IMDClient in the environment used to run `main.py`.
5. The `CH.airebo` potential file available through LAMMPS's normal potential-file lookup or the configured working environment.

LAMMPS's command-line executable alone is not sufficient: this application imports and instantiates LAMMPS through its Python API. See the [LAMMPS Python installation documentation](https://docs.lammps.org/Python_install.html).

## Installation and first run

See **[docs/INSTALLATION.md](docs/INSTALLATION.md)** for local setup and the tested Linux-compute/Windows-SAMSON deployment procedure.

Quick outline:

1. Clone or download this repository without changing its folder structure.
2. Install the Python dependencies for the controller (`python -m pip install -r requirements.txt`) into the Python environment that can import the LAMMPS Python module.
3. Open `IMD_client/config.toml` and verify the data, group, and simulation file paths and network ports.
4. In the SAMSON Python console, execute `IMD_client/SAMSON_run.py`.
5. Create the required SAMSON structural groups on the newly imported model (at least `motor1` and `motor2` with the default configuration).
6. In the **same SAMSON Python session**, execute `SAMSON_groups_setup.py` from the repository root.
7. Start `main.py` on the machine running LAMMPS (Windows for a local setup, or Linux for remote compute).
8. Focus that controller terminal and use the configured keyboard controls.

**Important:** `SAMSON_groups_setup.py` rewrites both the configured LAMMPS data file and group file using the current SAMSON coordinates and group membership. Back up any data file you need to preserve before running the exporter.

## Configuration

All application settings are in `IMD_client/config.toml`. Paths under `[files]` are resolved relative to the TOML file, not the current terminal directory.

### Simulation cadence is not the physical timestep

`[simulation].steps_per_update` controls how many MD steps the Python controller asks LAMMPS to execute per control-loop cycle. It is **not** the physical MD timestep.

The physical timestep remains in `simulation.in`:

```lammps
timestep 0.00025
```

`[imd].transfer_rate` independently controls how often LAMMPS sends coordinate frames, in MD steps.

### Linear motor

Each motor is configured under `[motors.<name>]`. For example:

```toml
[motors.motor1]
group = "motor1"
fix_id = "motor1_move"
motion = "linear"
velocity = 10.0
axis = [1.0, 0.0, 0.0]
forward_key = "j"
stop_key = "k"
reverse_key = "l"
```

The axis is expressed in the global LAMMPS coordinate frame and normalized automatically. `velocity` is the speed magnitude in the active LAMMPS distance/time units. With the supplied `units metal` setup, velocity is in Å/ps.

### Rotational motor

A motor can instead use `motion = "rotate"`:

```toml
[motors.motor3]
group = "motor3"
fix_id = "motor3_rotate"
motion = "rotate"
axis = [0.0, 0.0, 1.0]
period = 10.0
pivot = "group_centroid"  # or [x, y, z] in Angstroms
forward_key = "u"
stop_key = "i"
reverse_key = "o"
```

`period` is the time for one complete 360-degree revolution in the active LAMMPS time units (ps with `units metal`). `pivot = "group_centroid"` uses the initial centroid of the exported motor group; an explicit XYZ pivot is also supported. Positive and negative rotation follow the right-hand rule. This is prescribed kinematic motion using `fix move`, not a torque-driven rotor.

More detail is in [docs/CONFIGURATION.md](docs/CONFIGURATION.md) and [MULTI_MOTOR_SETUP.md](MULTI_MOTOR_SETUP.md).

## Current limitations

Please read these before trying a system other than the supplied carbon example.

- **Carbon/AIREBO demonstration:** The included `simulation.in` maps two atom types to carbon with `CH.airebo`. It is not a universal force-field setup.
- **No topology preservation in the SAMSON exporter:** `SAMSON_groups_setup.py` currently rebuilds the configured LAMMPS data file with `Masses` and `Atoms` sections. It does not preserve Bonds, Angles, Dihedrals, Impropers, their coefficient sections, or velocities. Do not use this exporter for a bonded force field that requires those sections.
- **No protein/AMBER workflow:** Protein preparation, general force-field parameterization, and bonded topology support are not implemented in this release.
- **Prescribed motion:** Motors use LAMMPS `fix move`; their motion is imposed rather than calculated from applied torque or forces.
- **Group discipline matters:** Motor and anchor groups are excluded from `free` and therefore from the supplied integration/thermostat fixes. Do not assign the same atoms to multiple independently moving motors. Keep groups consistent with the physical mechanism being modeled.
- **Example force field:** Users are responsible for selecting a physically appropriate force field, atom types, coefficients, units, and boundary conditions for any system they substitute.
- **Platform scope:** The local workflow was developed on Windows. The remote-compute workflow has also been exercised with Ubuntu 22.04 on Node3 running LAMMPS and the controller, and Windows running SAMSON. Other operating systems and deployment combinations have not been validated.

## Validation status

Pass 2.4 includes recorded automated checks for Python syntax, configuration parsing, linear and rotational motor command generation, axis normalization, pivot calculation, and mocked controller behavior. The included test notes are:

- `AXIS_TEST_RESULTS.txt`
- `ROTATION_TEST_RESULTS.txt`
- `PASS_2_4_NOTES.md`

The project was exercised in a Windows/SAMSON/LAMMPS environment and in a split-machine deployment: Ubuntu 22.04 Node3 ran LAMMPS 30 Sep 2026 Update 1 and the Python controller, while a Windows workstation ran SAMSON 2026 R1. The remote test loaded a 7,242-atom molecular system, established the local LAMMPS IMD connection and remote SAMSON TCP connection, and demonstrated live response to keyboard commands for three motor groups. This verifies basic remote operation; responsiveness and scaling still need performance characterization. The repository does not yet include a comprehensive automated regression-test suite, so contributors should treat the recorded checks as a starting point rather than a guarantee for every installation.

## Project roadmap

The near-term development focus is diamond systems:

- Improve topology handling for diamond structures.
- Integrate and validate the project's diamond force field.
- Extend atomistic machine examples and workflows.

Protein/AMBER support is intentionally outside the initial release scope. Community requests and contributions may help determine whether that becomes a future direction.

## Contributing and support

Bug reports, questions, feature requests, and pull requests are welcome. Please include:

- Operating system and version.
- Python version.
- SAMSON version.
- LAMMPS version and enabled packages.
- A minimal reproduction, relevant configuration, and complete error output.

See [CONTRIBUTING.md](CONTRIBUTING.md) for suggested issue and pull-request details.

## Acknowledgements

MolecularSimulator builds on the [LAMMPS](https://www.lammps.org/) molecular dynamics engine, [IMDClient](https://github.com/Becksteinlab/imdclient), and the [SAMSON](https://www.samson-connect.net/) molecular design platform. Please consult the respective projects for their licenses and terms.

## License

This project is released under the MIT License. See the [LICENSE](LICENSE) file for the complete license text. The MIT License applies to this repository’s original project code and documentation. Third-party software and services (including LAMMPS, SAMSON, and IMDClient) remain subject to their own licenses and terms.
