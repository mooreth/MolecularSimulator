
import os
import sys
import json
import socket
import threading
import queue

from PySide6.QtCore import QTimer


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_DIR = r"C:\LAMMPS\IMD"
DATA_FILE = os.path.join(PROJECT_DIR, "c60_240_collide.data")

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5679

DISPLAY_INTERVAL_MS = 16


# --------------------------------------------------
# Shared LAMMPS data parser
# --------------------------------------------------

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from lammps_data import load_lammps_data


# --------------------------------------------------
# Molecular system
# --------------------------------------------------

structural_model = None
samson_atoms = {}
atom_table = []

expected_atom_count = 0


# --------------------------------------------------
# TCP server state
# --------------------------------------------------

frame_queue = queue.Queue(maxsize=1)

server_socket = None
client_socket = None
server_thread = None

server_stop_event = threading.Event()

frame_timer = None

frames_received = 0
frames_displayed = 0


# --------------------------------------------------
# Create molecular system
# --------------------------------------------------

def create_molecular_system(data_file=DATA_FILE):

    global structural_model
    global samson_atoms
    global atom_table
    global expected_atom_count

    print("Loading LAMMPS data file:", data_file)

    atom_table = load_lammps_data(
    data_file,
    element_map={
        1: "C",
        2: "C",
        3: "C"
    }
)

    expected_atom_count = len(atom_table)

    print("Atoms loaded:", expected_atom_count)

    indices = sorted(
        atom["imd_index"] for atom in atom_table
    )

    if indices != list(range(expected_atom_count)):
        raise ValueError(
            "IMD indices must be contiguous and zero-based."
        )

    structural_model = SBStructuralModel()
    structural_model.name = "LAMMPS Live Simulation"

    samson_atoms = {}

    for entry in atom_table:

        element = SAMSON.getElementTypeBySymbol(
            entry["element"]
        )

        x, y, z = entry["initial_position"]

        position = SBPosition3(
            SBQuantity.angstrom(float(x)),
            SBQuantity.angstrom(float(y)),
            SBQuantity.angstrom(float(z))
        )

        atom = SBAtom(element, position)

        structural_model.addChild(atom)

        samson_atoms[entry["imd_index"]] = atom

    with SAMSON.holding("Create LAMMPS molecular system"):

        SAMSON.hold(structural_model)

        structural_model.create()

        SAMSON.getActiveDocument().addChild(
            structural_model
        )

    print("SAMSON molecular system created.")

    SAMSON.getActiveCamera().center()


# --------------------------------------------------
# Update SAMSON atom positions
# --------------------------------------------------

def update_positions(positions):

    if not SAMSON.isGUIThread():
        raise RuntimeError(
            "SAMSON atom updates must run on the GUI thread."
        )

    if len(positions) != expected_atom_count:
        raise ValueError(
            f"Expected {expected_atom_count} positions, "
            f"received {len(positions)}"
        )

    for imd_index, position in enumerate(positions):

        x, y, z = position

        atom = samson_atoms[imd_index]

        atom.setPosition(
            SBPosition3(
                SBQuantity.angstrom(float(x)),
                SBQuantity.angstrom(float(y)),
                SBQuantity.angstrom(float(z))
            )
        )

    SAMSON.requestViewportUpdate()


# --------------------------------------------------
# Store newest incoming frame
# --------------------------------------------------

def queue_latest_frame(frame):

    # Discard an older frame if the queue is full.
    if frame_queue.full():

        try:
            frame_queue.get_nowait()
        except queue.Empty:
            pass

    try:
        frame_queue.put_nowait(frame)
    except queue.Full:
        pass


# --------------------------------------------------
# TCP receiver thread
# --------------------------------------------------

def tcp_receiver():

    global server_socket
    global client_socket
    global frames_received

    try:

        server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        server_socket.bind(
            (SERVER_HOST, SERVER_PORT)
        )

        server_socket.listen(1)
        server_socket.settimeout(0.5)

        print(
            f"SAMSON listening on "
            f"{SERVER_HOST}:{SERVER_PORT}"
        )

        while not server_stop_event.is_set():

            try:
                connection, address = server_socket.accept()

            except socket.timeout:
                continue

            except OSError:
                break

            client_socket = connection

            print("IMD client connected:", address)

            connection.settimeout(0.5)

            buffer = b""

            while not server_stop_event.is_set():

                try:
                    data = connection.recv(65536)

                except socket.timeout:
                    continue

                except OSError:
                    break

                if not data:
                    break

                buffer += data

                # Process complete newline-delimited messages.
                while b"\n" in buffer:

                    line, buffer = buffer.split(b"\n", 1)

                    if not line:
                        continue

                    try:

                        frame = json.loads(
                            line.decode("utf-8")
                        )

                        positions = frame["positions"]

                        if len(positions) != expected_atom_count:
                            raise ValueError(
                                "Incorrect atom count in frame."
                            )

                        if any(len(position) != 3 for position in positions):
                            raise ValueError(
                                "Each atom must have three coordinates."
                            )

                        frames_received += 1

                        queue_latest_frame(frame)

                    except (ValueError, KeyError, TypeError) as error:

                        print("Invalid frame:", error)

            connection.close()
            client_socket = None

            print("IMD client disconnected.")

    except OSError as error:

        if not server_stop_event.is_set():
            print("TCP server error:", error)

    finally:

        if server_socket is not None:
            server_socket.close()
            server_socket = None

        print("SAMSON TCP server stopped.")


# --------------------------------------------------
# Process incoming frames on SAMSON GUI thread
# --------------------------------------------------

def process_pending_frames():

    global frames_displayed

    try:
        frame = frame_queue.get_nowait()

    except queue.Empty:
        return

    update_positions(frame["positions"])

    frames_displayed += 1


# --------------------------------------------------
# Start TCP server and display timer
# --------------------------------------------------

def start_server():

    global server_thread
    global frame_timer

    if server_thread is not None and server_thread.is_alive():

        print("SAMSON server is already running.")
        return

    server_stop_event.clear()

    # Create GUI timer.
    frame_timer = QTimer()

    frame_timer.timeout.connect(
        process_pending_frames
    )

    frame_timer.start(DISPLAY_INTERVAL_MS)

    # Start networking in a background thread.
    server_thread = threading.Thread(
        target=tcp_receiver,
        daemon=True
    )

    server_thread.start()

    print("SAMSON TCP receiver started.")


# --------------------------------------------------
# Stop TCP server
# --------------------------------------------------

def stop_server():

    global client_socket
    global server_socket
    global frame_timer

    server_stop_event.set()

    if frame_timer is not None:
        frame_timer.stop()
        frame_timer = None

    for sock in (client_socket, server_socket):

        if sock is not None:

            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                sock.close()
            except OSError:
                pass

    print("SAMSON server shutdown requested.")


# --------------------------------------------------
# Initialize SAMSON
# --------------------------------------------------

create_molecular_system()

start_server()

print("SAMSON_run.py initialized.")
