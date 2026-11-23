# samson_imd.py

import socket
import json


class SamsonIMDClient:

    def __init__(self, host="127.0.0.1", port=5679, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None

    def connect(self):
        """Connect to the TCP server running inside SAMSON."""

        if self.socket is not None:
            return

        print(f"Connecting to SAMSON at {self.host}:{self.port}...")

        self.socket = socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout
        )

        print("Connected to SAMSON.")

    def send_frame(self, frame_number, positions):
        """Send one molecular frame to SAMSON."""

        if self.socket is None:
            raise ConnectionError("Not connected to SAMSON.")

        message = {
            "frame_number": int(frame_number),
            "positions": positions.tolist()
                if hasattr(positions, "tolist")
                else positions
        }

        # One JSON message per line.
        data = json.dumps(message, separators=(",", ":")) + "\n"

        self.socket.sendall(data.encode("utf-8"))

    def close(self):
        """Close the TCP connection."""

        if self.socket is not None:
            self.socket.close()
            self.socket = None
            print("Disconnected from SAMSON.")