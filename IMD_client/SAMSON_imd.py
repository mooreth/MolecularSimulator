"""TCP client used to forward molecular frames to SAMSON."""

import json
import socket


class SamsonIMDClient:
    def __init__(self, host="127.0.0.1", port=5679, timeout=5.0):
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self.socket = None

    def connect(self):
        if self.socket is not None:
            return
        print(f"Connecting to SAMSON at {self.host}:{self.port}...")
        self.socket = socket.create_connection(
            (self.host, self.port), timeout=self.timeout
        )
        print("Connected to SAMSON.")

    def send_frame(self, frame_number, positions):
        if self.socket is None:
            raise ConnectionError("Not connected to SAMSON.")
        message = {
            "frame_number": int(frame_number),
            "positions": positions.tolist()
            if hasattr(positions, "tolist") else positions,
        }
        payload = json.dumps(message, separators=(",", ":")) + "\n"
        self.socket.sendall(payload.encode("utf-8"))

    def close(self):
        if self.socket is not None:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
            self.socket = None
            print("Disconnected from SAMSON.")
