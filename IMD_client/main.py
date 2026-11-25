"""LAMMPS-to-SAMSON molecular simulation controller."""

import queue
import threading
import time
from dataclasses import dataclass

import numpy as np
from imdclient import IMDClient
from lammps import lammps

from configuration import load_config, lammps_quote
from keyboard_controller import KeyboardController
from lammps_data import load_lammps_data
from molecular_system import MolecularSystem
from SAMSON_imd import SamsonIMDClient


@dataclass
class IMDFrame:
    frame_number: int
    timestamp: float
    atom_count: int
    positions: np.ndarray


def connect_and_receive_frames(
    frame_queue, stop_event, connected_event, n_atoms, host, imd_port
):
    """Connect to LAMMPS IMD and place received frames on a queue."""
    print("IMD: Receiver thread started.", flush=True)
    print("IMD: Waiting for LAMMPS handshake...", flush=True)
    client = None

    try:
        # The IMDClient must not install signal handlers from this worker thread.
        client = IMDClient(
            host,
            imd_port,
            n_atoms=n_atoms,
            multithreaded=False,
        )
        print("IMD: Handshake successful!", flush=True)
        connected_event.set()

        while not stop_event.is_set():
            raw_frame = client.get_imdframe()
            if raw_frame is not None:
                frame_queue.put(raw_frame)

    except Exception as error:
        if not stop_event.is_set():
            print("IMD receiver error:", repr(error), flush=True)

    finally:
        if client is not None:
            try:
                client.stop()
            except Exception:
                pass
        print("IMD receiver thread stopped.", flush=True)



def validate_configured_motor_groups(config):
    """Fail early if a configured motor has no exported LAMMPS group."""
    group_file = config["resolved_files"]["group_file"]
    exported_groups = set()
    with group_file.open("r", encoding="utf-8") as stream:
        for raw_line in stream:
            line = raw_line.split("#", 1)[0].strip()
            fields = line.split()
            if len(fields) >= 2 and fields[0] == "group":
                exported_groups.add(fields[1])

    missing = [
        motor["group"] for motor in config["motors"].values()
        if motor["group"] not in exported_groups
    ]
    if missing:
        names = ", ".join(missing)
        raise ValueError(
            f"Configured motor group(s) not found in {group_file}: {names}. "
            "Create matching structural groups in SAMSON, then rerun "
            "SAMSON_groups_setup.py before starting main.py."
        )

def _read_group_atom_ids(group_file, group_name):
    """Read the explicit atom-ID membership written by SAMSON_groups_setup."""
    with group_file.open("r", encoding="utf-8") as stream:
        for raw_line in stream:
            fields = raw_line.split("#", 1)[0].split()
            if len(fields) >= 4 and fields[0] == "group" and fields[1] == group_name:
                if fields[2] != "id":
                    raise ValueError(
                        f"Group {group_name!r} is not an explicit atom-ID group in {group_file}"
                    )
                try:
                    atom_ids = [int(value) for value in fields[3:]]
                except ValueError as error:
                    raise ValueError(
                        f"Could not parse atom IDs for group {group_name!r} in {group_file}"
                    ) from error
                if not atom_ids:
                    raise ValueError(f"Rotation group {group_name!r} contains no atoms")
                return atom_ids
    raise ValueError(
        f"Could not find explicit atom-ID definition for group {group_name!r} in {group_file}"
    )


def resolve_rotation_pivots(motors, atom_table, group_file):
    """Resolve each rotation pivot to an XYZ point in the initial LAMMPS model."""
    positions_by_id = {
        int(atom["lammps_id"]): atom["initial_position"]
        for atom in atom_table
    }

    for motor_name, motor in motors.items():
        if motor["motion"] != "rotate":
            continue

        if motor["pivot"] == "group_centroid":
            atom_ids = _read_group_atom_ids(group_file, motor["group"])
            missing = [atom_id for atom_id in atom_ids if atom_id not in positions_by_id]
            if missing:
                raise ValueError(
                    f"Rotation group {motor['group']!r} contains atom IDs not present "
                    f"in the data file: {missing[:10]}"
                )
            xyz = [positions_by_id[atom_id] for atom_id in atom_ids]
            pivot = tuple(
                sum(float(position[axis]) for position in xyz) / len(xyz)
                for axis in range(3)
            )
        else:
            pivot = tuple(motor["pivot"])

        motor["resolved_pivot"] = pivot
        print(
            f"{motor_name}: rotation pivot = "
            f"({pivot[0]:.6f}, {pivot[1]:.6f}, {pivot[2]:.6f}) A"
        )


def configure_lammps_system(lmp, config):
    """Initialize LAMMPS using explicit commands and configured file paths.

    File paths are passed directly to LAMMPS instead of relying on input-script
    variable substitution. This avoids unresolved ${variable} placeholders
    when the input file is loaded through the Python library interface.
    """
    files = config["resolved_files"]
    network = config["network"]
    imd = config["imd"]

    # These commands must precede read_data. The physical MD timestep remains
    # in simulation.in, where users normally expect to configure it.
    lmp.command("units metal")
    lmp.command(f"atom_style {config['lammps']['atom_style']}")
    lmp.command("boundary s s s")

    print("Reading LAMMPS data file:", files["data_file"], flush=True)
    lmp.command(f"read_data {lammps_quote(files['data_file'].as_posix())}")

    print("Reading SAMSON group definitions:", files["group_file"], flush=True)
    lmp.command(f"include {lammps_quote(files['group_file'].as_posix())}")

    print("Loading LAMMPS simulation settings:", files["simulation_file"], flush=True)
    lmp.file(str(files["simulation_file"]))

    # Keep the IMD endpoint in Python configuration so there is only one
    # authoritative place to set the port and transfer rate.
    lmp.command(
        f"fix comm all imd {network['imd_port']} "
        f"unwrap off fscale 100.0 trate {imd['transfer_rate']} nowait on"
    )


def motor_velocity_vector(motor_config, direction_sign=1.0):
    """Return the configured unit axis multiplied by motor speed and sign."""
    speed = motor_config["velocity"] * direction_sign
    values = [component * speed for component in motor_config["axis"]]
    return tuple(0.0 if abs(value) < 1e-14 else value for value in values)


def process_motor_command(lmp, motor_config, command, motor_direction):
    """Apply a linear or rotational command to one independently controlled motor."""
    group = motor_config["group"]
    fix_id = motor_config["fix_id"]
    motion = motor_config["motion"]

    if command in ("forward", "reverse"):
        new_direction = command
        if motor_direction != new_direction:
            if motor_direction is not None:
                lmp.command(f"unfix {fix_id}")

            sign = 1.0 if command == "forward" else -1.0
            axis = tuple(component * sign for component in motor_config["axis"])

            if motion == "linear":
                speed = motor_config["velocity"]
                vx, vy, vz = (component * speed for component in axis)
                lmp.command(
                    f"fix {fix_id} {group} move linear "
                    f"{vx:.12g} {vy:.12g} {vz:.12g}"
                )
                print(
                    f"{group} translating {command}: velocity "
                    f"({vx:.6g}, {vy:.6g}, {vz:.6g})"
                )
            elif motion == "rotate":
                px, py, pz = motor_config["resolved_pivot"]
                rx, ry, rz = axis
                period = motor_config["period"]
                lmp.command(
                    f"fix {fix_id} {group} move rotate "
                    f"{px:.12g} {py:.12g} {pz:.12g} "
                    f"{rx:.12g} {ry:.12g} {rz:.12g} "
                    f"{period:.12g} units box"
                )
                print(
                    f"{group} rotating {command}: pivot "
                    f"({px:.6g}, {py:.6g}, {pz:.6g}), axis "
                    f"({rx:.6g}, {ry:.6g}, {rz:.6g}), "
                    f"period {period:g} time-units/revolution"
                )
            else:
                raise ValueError(f"Unsupported motor motion type: {motion}")

            motor_direction = new_direction

    elif command == "stop":
        if motor_direction is not None:
            lmp.command(f"unfix {fix_id}")
            motor_direction = None
            print(f"{group} stopped")

    return motor_direction


def process_frames(frame_queue, molecule, samson_client, frame_count):
    """Update the molecular state and forward all queued frames to SAMSON."""
    frames_processed = 0

    while True:
        try:
            raw_frame = frame_queue.get_nowait()
        except queue.Empty:
            break

        positions = np.asarray(raw_frame.positions, dtype=np.float32).copy()
        frame_count += 1
        frame_data = IMDFrame(
            frame_number=frame_count,
            timestamp=time.perf_counter(),
            atom_count=len(positions),
            positions=positions,
        )

        molecule.update(frame_data)
        samson_client.send_frame(
            frame_number=frame_count,
            positions=molecule.get_positions(),
        )
        frames_processed += 1

    return frame_count, frames_processed


def main(config_file=None):
    config = load_config(config_file)
    validate_configured_motor_groups(config)
    files = config["resolved_files"]
    network = config["network"]
    simulation = config["simulation"]
    motors = config["motors"]
    controls = config["controls"]

    lmp = None
    samson_client = None
    keyboard = None
    receiver_thread = None

    stop_event = threading.Event()
    connected_event = threading.Event()
    frame_queue = queue.Queue()

    motor_directions = {name: None for name in motors}
    frame_count = 0

    try:
        print("Loading molecular model:", files["data_file"])
        atom_table = load_lammps_data(
            files["data_file"],
            atom_style=config["lammps"]["atom_style"],
            element_map=config["elements"]["overrides"],
        )
        n_atoms = len(atom_table)
        unknown_elements = sorted({
            atom["element"] for atom in atom_table
            if atom["element"] == "Unknown"
        })
        if unknown_elements:
            print(
                "Warning: some atom types could not be identified from mass. "
                "Add explicit entries under [elements.overrides] in config.toml."
            )

        print(f"Loaded atom table: {n_atoms} atoms")
        resolve_rotation_pivots(
            motors,
            atom_table,
            files["group_file"],
        )
        molecule = MolecularSystem(atom_table)

        print("Creating LAMMPS instance...")
        lmp = lammps()
        configure_lammps_system(lmp, config)

        print("Initializing LAMMPS and IMD listener...")
        lmp.command("run 0")

        print("\nConnecting to LAMMPS IMD...")
        receiver_thread = threading.Thread(
            target=connect_and_receive_frames,
            args=(
                frame_queue,
                stop_event,
                connected_event,
                n_atoms,
                network["imd_host"],
                network["imd_port"],
            ),
            daemon=True,
        )
        receiver_thread.start()

        print("\nConnecting to SAMSON...")
        samson_client = SamsonIMDClient(
            host=network["samson_host"],
            port=network["samson_port"],
        )
        samson_client.connect()

        key_bindings = {controls["quit_key"]: "quit"}
        for motor_name, motor in motors.items():
            key_bindings[motor["forward_key"]] = f"{motor_name}:forward"
            key_bindings[motor["stop_key"]] = f"{motor_name}:stop"
            key_bindings[motor["reverse_key"]] = f"{motor_name}:reverse"
        keyboard = KeyboardController(key_bindings=key_bindings)
        keyboard.start()

        print("\nSimulation controller started.")
        for motor_name, motor in motors.items():
            axis_text = tuple(round(v, 4) for v in motor["axis"])
            if motor["motion"] == "linear":
                motion_text = f"linear axis={axis_text}, speed={motor['velocity']:g} Å/ps"
            else:
                pivot_text = tuple(round(v, 4) for v in motor["resolved_pivot"])
                motion_text = (
                    f"rotation axis={axis_text}, pivot={pivot_text}, "
                    f"period={motor['period']:g} ps/revolution"
                )
            print(
                f"{motor_name}: group={motor['group']}, {motion_text}; "
                f"keys {motor['forward_key'].upper()}/{motor['stop_key'].upper()}/{motor['reverse_key'].upper()}"
            )
        print(f"Steps per Python update: {simulation['steps_per_update']}")
        print("Running simulation...\n")

        running = True
        while running:
            for command in keyboard.get_commands():
                if command == "quit":
                    running = False
                    break
                motor_name, action = command.split(":", 1)
                motor_directions[motor_name] = process_motor_command(
                    lmp, motors[motor_name], action, motor_directions[motor_name]
                )

            if not running:
                break

            lmp.command(f"run {simulation['steps_per_update']}")

            frame_count, frames_processed = process_frames(
                frame_queue, molecule, samson_client, frame_count
            )
            if frames_processed:
                print(
                    f"Frames: {frame_count} | "
                    f"Received this cycle: {frames_processed} | "
                    f"Atoms: {n_atoms}"
                )
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received.")

    except Exception as error:
        print("\nSimulation controller error:", repr(error))
        raise

    finally:
        print("\nShutting down...")
        stop_event.set()

        if keyboard is not None:
            keyboard.stop()

        if lmp is not None:
            try:
                lmp.close()
            except Exception as error:
                print("LAMMPS shutdown error:", error)

        if receiver_thread is not None:
            receiver_thread.join(timeout=2.0)

        if samson_client is not None:
            try:
                samson_client.close()
            except Exception as error:
                print("SAMSON shutdown error:", error)

        print("Controller stopped.")


if __name__ == "__main__":
    main()
