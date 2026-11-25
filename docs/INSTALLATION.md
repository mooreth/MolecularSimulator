# Installation and first run

This guide covers the local workflow and the tested remote-compute arrangement: Ubuntu 22.04 on Node3 runs the Python controller and LAMMPS; a Windows workstation runs SAMSON 2026 R1 and the SAMSON TCP receiver. Python 3.11 is used for the controller.

## 1. Obtain the repository

Clone the repository or download its ZIP archive. Keep the supplied directory structure intact because the default paths in `IMD_client/config.toml` are relative to that file.

## 2. Prepare the Python environment for `main.py`

The command-line controller imports NumPy, IMDClient, and the LAMMPS Python module. The SAMSON-side scripts also import NumPy, so NumPy must be available in SAMSON’s embedded Python environment as well. Open a terminal using the Python interpreter that can load your LAMMPS shared library, then install the ordinary Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

IMDClient requires Python 3.11 or later. Its installation instructions are also available at [imdclient on PyPI](https://pypi.org/project/imdclient/).

The LAMMPS Python package and its shared library are installed/configured separately from this requirements file. Follow the [official LAMMPS Python installation guide](https://docs.lammps.org/Python_install.html). Confirm that the same interpreter can import both `lammps` and `imdclient`.

A quick import check from that terminal is:

```powershell
python -c "import numpy, imdclient; from lammps import lammps; print('Python dependencies imported')"
```

This check verifies imports only; it does not prove that the LAMMPS shared library has all required simulation features.

## 3. Verify the LAMMPS build and potential file

For the supplied example, LAMMPS must be able to use:

- The Python interface and shared library.
- The IMD package/fix (`fix imd`).
- The MOLECULE package (for `atom_style molecular`).
- The MANYBODY package (AIREBO).
- The `CH.airebo` potential file.

The exact build procedure depends on how LAMMPS was installed. Check the LAMMPS startup output and package/build configuration if a command is reported as unknown.

## 4. Review `config.toml`

Open `IMD_client/config.toml` and check:

- `[files]`: `data_file`, `group_file`, and `simulation_file`.
- `[network]`: host, IMD port, and SAMSON port.
- `[lammps]`: atom style must match the data file's `Atoms` section.
- `[motors]`: each configured motor's group name must match a SAMSON group you will create.

The network settings are machine-specific. For a single-machine setup, use loopback addresses. For remote compute, follow section 8 below: the Windows receiver binds to `0.0.0.0:5679`, while the Linux controller connects to the Windows workstation's LAN IP on port 5679 and connects to its local LAMMPS IMD listener on `127.0.0.1:5678`.

The default configuration has `motor1` and `motor2` enabled. You must create both groups in SAMSON before launching `main.py`. The optional `motor3` rotational example is commented out.

## 5. Start the SAMSON visualization endpoint

1. Launch SAMSON and open its Python console.
2. Execute `IMD_client/SAMSON_run.py` from the repository. This imports the configured LAMMPS data file into a SAMSON structural model and starts the TCP receiver.
3. Create the structural groups on this newly imported model. For the default setup, create groups named `motor1` and `motor2`. You may also create static groups such as `anchor1`.
4. Without restarting SAMSON, execute `SAMSON_groups_setup.py` from the repository root in the **same SAMSON Python session**.

The exporter reuses the atom objects registered by `SAMSON_run.py`; it does not import a second model.

### Important: exporter overwrites the configured data file

`SAMSON_groups_setup.py` writes two outputs:

- The configured LAMMPS data file, using the current SAMSON atom coordinates and preserved atom metadata supported by this prototype.
- The configured LAMMPS group file, containing discovered structural groups and the generated `free` group.

Back up the original data file before running the exporter if you need to retain it. The current exporter writes only `Masses` and `Atoms` in the data file; it is not suitable for bonded/topological systems.

Review the exporter output in the SAMSON console. Confirm that the configured motor groups were discovered and that their atom counts look correct.

## 6. Start the LAMMPS controller

Open a Windows terminal. Change directory to `IMD_client` and launch `main.py` using the Python interpreter configured above:

```powershell
cd path\to\MolecularSimulator\IMD_client
python main.py
```

The controller reads the shared `config.toml`, starts LAMMPS through its Python API, connects to the IMD stream, and forwards frames to SAMSON. Keep the terminal open and focused for keyboard control.

## 8. Remote compute: Linux controller and Windows SAMSON

This deployment keeps molecular visualization on the Windows workstation while moving LAMMPS computation and the Python controller to a Linux compute node. The two programs use different network endpoints; do not use one shared host setting for both.

### 8.1 Linux compute-node requirements

The validated Node3 environment used Ubuntu 22.04.4 LTS, Python 3.11 in a dedicated virtual environment, and LAMMPS 30 Sep 2026 Update 1 built with its shared library and Python interface.

The LAMMPS build used these relevant features:

- **MOLECULE** — required by the example's `atom_style molecular`.
- **MANYBODY** — required by `pair_style airebo`.
- **IMD** — required by `fix imd`.
- MPI and shared-library support were enabled in the tested build.

Make sure the LAMMPS Python module and shared library come from the same build. A stale `liblammps.so` bundled in the Python `site-packages/lammps` directory can take precedence over the newly installed library. If the command-line `lmp` recognizes a package but Python reports it missing, check which shared library the Python wrapper loads.

The tested Node3 layout kept LAMMPS source, build, and install directories separate and used a dedicated virtual environment. The shared-library directory was added to `LD_LIBRARY_PATH` for the shell session:

```bash
source ~/environments/molecularsimulator/bin/activate
export LD_LIBRARY_PATH=/home/tom/software/lammps/install/lib:$LD_LIBRARY_PATH
```

Use paths appropriate to your installation. Verify the LAMMPS executable and Python interface independently before launching the controller.

### 8.2 Machine-specific network configuration

Use a separate `IMD_client/config.toml` on each machine.

**Windows workstation — SAMSON receiver**

The SAMSON-side `SAMSON_run.py` reads `samson_host` as its bind address. Configure the Windows copy as follows:

```toml
[network]
samson_host = "0.0.0.0"
imd_host = "127.0.0.1"
imd_port = 5678
samson_port = 5679
```

Start SAMSON and execute `IMD_client/SAMSON_run.py` in its Python console. Confirm that the console reports it is listening on `0.0.0.0:5679`. Allow inbound TCP port 5679 through the Windows firewall on the trusted/private network.

**Linux compute node — controller and LAMMPS**

Configure the Linux copy with the Windows workstation's actual LAN address. For example, if the Windows workstation is `192.168.68.63`:

```toml
[network]
imd_host = "127.0.0.1"
samson_host = "192.168.68.63"
imd_port = 5678
samson_port = 5679
```

Replace the example address with the current reachable address of the Windows workstation. Do not set the Linux controller's `samson_host` to `0.0.0.0`: that value is for the server's bind address, not for a client connection.

The IMD listener remains local to Node3 because LAMMPS and the Python controller run on the same machine. The controller connects to that listener through `127.0.0.1:5678`; it separately connects to the Windows SAMSON receiver at `<Windows-LAN-IP>:5679`.

### 8.3 Startup order

1. On Windows, launch SAMSON and execute `SAMSON_run.py`. Confirm the receiver is listening on port 5679.
2. On Linux, open a terminal, activate the MolecularSimulator virtual environment, and set the LAMMPS shared-library path if required.
3. Change to the Linux project's `IMD_client` directory and run:

   ```bash
   python main.py
   ```

4. Confirm the controller loads the configured atom count, initializes LAMMPS and the IMD listener, and reports `Connected to SAMSON.`
5. Use the keyboard in the Linux terminal to control the configured motor groups. The Linux keyboard controller uses terminal input; launch it from an interactive terminal.

### 8.4 Verified remote demonstration

The remote arrangement was exercised with a 7,242-atom molecular model on Node3. The controller loaded the motor groups, initialized LAMMPS with AIREBO, started the IMD listener on port 5678, connected to the Windows SAMSON receiver on port 5679, and demonstrated motor response to keyboard commands. This confirms the basic end-to-end remote data path and control path.

The initial demonstration showed that responsiveness can be improved. Reducing unnecessary atoms and measuring simulation, transfer, network, and rendering costs are planned optimization work; no performance target is claimed here.
## 9. Keyboard controls

Default controls:

| Motor | Forward | Stop | Reverse |
|---|---|---|---|
| `motor1` | J | K | L |
| `motor2` | F | G | H |
| Optional `motor3` rotation | U | I | O |

Press `Q` to quit. Keys are configurable in `config.toml`.

## Troubleshooting checklist

- **`No module named lammps`:** The Python interpreter running `main.py` cannot find the LAMMPS Python package. Configure/install the LAMMPS Python interface for that interpreter.
- **LAMMPS shared-library load error:** Check that the matching LAMMPS shared library is installed and discoverable by the operating system. Consult the LAMMPS Python installation guide.
- **Unknown `atom_style molecular`:** The LAMMPS build does not include the MOLECULE package.
- **Unknown `fix imd`:** The LAMMPS build does not include the IMD package/fix.
- **Unknown `pair_style airebo`:** The LAMMPS build does not include MANYBODY/AIREBO support.
- **Cannot find `CH.airebo`:** Make the potential file available in the LAMMPS potential search path or adjust the simulation input to point to its location.
- **Configured motor group missing:** Create a SAMSON structural group with the exact configured name, rerun `SAMSON_groups_setup.py`, and then restart `main.py`.
- **SAMSON does not update:** Check that `SAMSON_run.py` is still running in the SAMSON session, that the configured ports match, and that no firewall or other process blocks the TCP connection. In remote mode, verify that the Linux controller's `samson_host` is the Windows workstation's reachable LAN IP and that Windows allows inbound TCP 5679.
- **Unexpected atoms moving:** Review group membership. Every exported jig group is excluded from `free`; verify that motor and anchor memberships reflect the intended mechanism.

For a useful bug report, include the full console output from both SAMSON and the controller terminal, plus your Python, SAMSON, and LAMMPS versions.
