
import time
import threading
import queue
from dataclasses import dataclass

import numpy as np

from lammps import lammps
from imdclient import IMDClient

from lammps_data import load_lammps_data
from molecular_system import MolecularSystem
from SAMSON_imd import SamsonIMDClient
from keyboard_controller import KeyboardController


# ============================================================
# CONFIGURATION
# ============================================================

DATA_FILE = "C:/LAMMPS/IMD/c60_240_collide.data"
GROUP_FILE = "C:/LAMMPS/IMD/samson_groups.in"
SIMULATION_FILE = "C:/LAMMPS/IMD/simulation.in"

HOST = "127.0.0.1"
IMD_PORT = 5678
SAMSON_PORT = 5679

CHUNK_STEPS = 10

ELEMENT_MAP = {
    1: "C",
    2: "C"
}


# ============================================================
# FRAME DATA STRUCTURE
# ============================================================

@dataclass
class IMDFrame:
    frame_number: int
    timestamp: float
    atom_count: int
    positions: np.ndarray


# ============================================================
# IMD RECEIVER THREAD
# ============================================================

def connect_and_receive_frames(frame_queue, stop_event, connected_event, n_atoms):
    print("IMD: Receiver thread started.", flush=True)
    print("IMD: Waiting for LAMMPS handshake...", flush=True)

    client = None

    try:
        client = IMDClient(
            HOST,
            IMD_PORT,
            n_atoms=n_atoms,
            multithreaded=False
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


# ============================================================
# MOTOR CONTROL
# ============================================================

def process_motor_command(lmp, command, motor_direction):
    """
    Control motor1 using LAMMPS fix move.

    J = Forward (+X)
    K = Stop
    L = Reverse (-X)
    """

    if command == "forward":

        if motor_direction != "forward":

            if motor_direction is not None:
                lmp.command("unfix motor1_move")

            lmp.command(
                "fix motor1_move motor1 move linear 10.0 0.0 0.0"
            )

            motor_direction = "forward"

            print("Motor1 moving +X")

    elif command == "reverse":

        if motor_direction != "reverse":

            if motor_direction is not None:
                lmp.command("unfix motor1_move")

            lmp.command(
                "fix motor1_move motor1 move linear -10.0 0.0 0.0"
            )

            motor_direction = "reverse"

            print("Motor1 moving -X")

    elif command == "stop":

        if motor_direction is not None:

            lmp.command("unfix motor1_move")

            motor_direction = None

            print("Motor1 stopped")

    return motor_direction


# ============================================================
# FRAME PROCESSING
# ============================================================

def process_frames(
    frame_queue,
    molecule,
    samson_client,
    frame_count
):
    """
    Process all available IMD frames.

    Convert incoming coordinates into our IMDFrame structure,
    update the molecular system, and forward coordinates
    to SAMSON.
    """

    frames_processed = 0

    while not frame_queue.empty():

        raw_frame = frame_queue.get()

        positions = np.asarray(
            raw_frame.positions,
            dtype=np.float32
        ).copy()

        frame_count += 1

        frame_data = IMDFrame(
            frame_number=frame_count,
            timestamp=time.perf_counter(),
            atom_count=len(positions),
            positions=positions
        )

        molecule.update(frame_data)

        samson_client.send_frame(
            frame_number=frame_count,
            positions=molecule.get_positions()
        )

        frames_processed += 1

    return frame_count, frames_processed


# ============================================================
# MAIN
# ============================================================

def main():

    lmp = None
    samson_client = None
    keyboard = None

    receiver_thread = None

    stop_event = threading.Event()
    connected_event = threading.Event()

    frame_queue = queue.Queue()

    motor_direction = None
    frame_count = 0

    try:

        # ----------------------------------------------------
        # LOAD MOLECULAR MODEL
        # ----------------------------------------------------

        print("Creating LAMMPS instance...")

        atom_table = load_lammps_data(
            DATA_FILE,
            element_map=ELEMENT_MAP
        )

        N_ATOMS = len(atom_table)

        print(f"Loaded atom table: {N_ATOMS} atoms")

        molecule = MolecularSystem(atom_table)

        # ----------------------------------------------------
        # CREATE LAMMPS INSTANCE
        # ----------------------------------------------------

        lmp = lammps()

        print("Loading simulation.in...")

        lmp.file(SIMULATION_FILE)

        print("Initializing LAMMPS...")

        # Initialize LAMMPS and the IMD listener.
        # This does not advance simulation time.

        lmp.command("run 0")

        # ----------------------------------------------------
        # START IMD RECEIVER THREAD
        # ----------------------------------------------------

        print("\nConnecting to LAMMPS IMD...")

        receiver_thread = threading.Thread(
            target=connect_and_receive_frames,
            args=(
                frame_queue,
                stop_event,
                connected_event,
                N_ATOMS
            ),
            daemon=True
        )

        receiver_thread.start()

        print("IMD receiver thread launched.")

        # ----------------------------------------------------
        # CONNECT TO SAMSON
        # ----------------------------------------------------

        print("\nConnecting to SAMSON...")

        samson_client = SamsonIMDClient(
            host=HOST,
            port=SAMSON_PORT
        )

        samson_client.connect()

        # ----------------------------------------------------
        # START KEYBOARD CONTROLLER
        # ----------------------------------------------------

        keyboard = KeyboardController()
        keyboard.start()

        print("\nSimulation controller started.")
        print("J = Motor1 forward")
        print("K = Motor1 stop")
        print("L = Motor1 reverse")
        print("Q = Quit")
        print("\nRunning simulation...\n")

        # ----------------------------------------------------
        # MAIN SIMULATION LOOP
        # ----------------------------------------------------

        running = True

        while running:

            # -----------------------------------------------
            # CHECK KEYBOARD COMMANDS
            # -----------------------------------------------

            commands = keyboard.get_commands()

            for command in commands:

                if command == "quit":
                    running = False
                    break

                motor_direction = process_motor_command(
                    lmp,
                    command,
                    motor_direction
                )

            if not running:
                break

            # -----------------------------------------------
            # ADVANCE LAMMPS SIMULATION
            # -----------------------------------------------

            lmp.command(f"run {CHUNK_STEPS}")

            # -----------------------------------------------
            # PROCESS RECEIVED IMD FRAMES
            # -----------------------------------------------

            frame_count, frames_processed = process_frames(
                frame_queue,
                molecule,
                samson_client,
                frame_count
            )

            # -----------------------------------------------
            # DIAGNOSTICS
            # -----------------------------------------------

            if frames_processed > 0:

                print(
                    f"Frames: {frame_count} | "
                    f"Received this cycle: {frames_processed} | "
                    f"Atoms: {N_ATOMS}"
                )

            # Give the receiver thread time to run.
            time.sleep(0.01)

    except KeyboardInterrupt:

        print("\nKeyboard interrupt received.")

    except Exception as error:

        print("\nSimulation controller error:")
        print(error)

    finally:

        # ----------------------------------------------------
        # SHUTDOWN
        # ----------------------------------------------------

        print("\nShutting down...")

        stop_event.set()

        if keyboard is not None:
            keyboard.stop()

        # Close LAMMPS first to shut down the IMD connection.
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


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
