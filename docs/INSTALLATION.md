# Installation and first run

This guide describes the Pass 2.4 workflow tested on Windows with SAMSON, LAMMPS, and Python 3.11.

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
- The MANYBODY package (AIREBO).
- The `CH.airebo` potential file.

The exact build procedure depends on how LAMMPS was installed. Check the LAMMPS startup output and package/build configuration if a command is reported as unknown.

## 4. Review `config.toml`

Open `IMD_client/config.toml` and check:

- `[files]`: `data_file`, `group_file`, and `simulation_file`.
- `[network]`: host, IMD port, and SAMSON port.
- `[lammps]`: atom style must match the data file's `Atoms` section.
- `[motors]`: each configured motor's group name must match a SAMSON group you will create.

The supplied configuration uses `127.0.0.1`, IMD port `5678`, and SAMSON port `5679`. Ensure those ports are not already occupied.

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

## 7. Keyboard controls

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
- **Unknown `fix imd`:** The LAMMPS build does not include the IMD package/fix.
- **Unknown `pair_style airebo`:** The LAMMPS build does not include MANYBODY/AIREBO support.
- **Cannot find `CH.airebo`:** Make the potential file available in the LAMMPS potential search path or adjust the simulation input to point to its location.
- **Configured motor group missing:** Create a SAMSON structural group with the exact configured name, rerun `SAMSON_groups_setup.py`, and then restart `main.py`.
- **SAMSON does not update:** Check that `SAMSON_run.py` is still running in the SAMSON session, that the configured ports match, and that no firewall or other process blocks the local TCP connections.
- **Unexpected atoms moving:** Review group membership. Every exported jig group is excluded from `free`; verify that motor and anchor memberships reflect the intended mechanism.

For a useful bug report, include the full console output from both SAMSON and the controller terminal, plus your Python, SAMSON, and LAMMPS versions.
