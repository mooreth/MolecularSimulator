
"""Cross-platform non-blocking keyboard controller."""

import os
import queue
import threading
import time

if os.name == "nt":
    import msvcrt
else:
    import select
    import sys
    import termios
    import tty


class KeyboardController:
    def __init__(self, key_bindings=None):
        # Map one-character keys to abstract actions.
        self.key_bindings = key_bindings or {
            "j": "forward",
            "k": "stop",
            "l": "reverse",
            "q": "quit",
        }

        self.commands = queue.Queue()
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._listen,
            daemon=True
        )
        self.thread.start()

        print("\nKeyboard controller started.")
        for key, action in self.key_bindings.items():
            if action == "quit":
                description = "quit simulation"
            else:
                motor_name, direction = action.split(":", 1)
                description = f"{motor_name} {direction}"

            print(f"  {key.upper()} = {description}")

        print()

    def _dispatch_key(self, key):
        key = key.lower()
        action = self.key_bindings.get(key)

        if action is not None:
            self.commands.put(action)
            print(f"Keyboard command: {action}", flush=True)

            if action == "quit":
                self.running = False

    def _listen(self):
        if os.name == "nt":
            self._listen_windows()
        else:
            self._listen_linux()

    def _listen_windows(self):
        while self.running:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode(
                    "utf-8", errors="ignore"
                )
                self._dispatch_key(key)

            time.sleep(0.01)

    def _listen_linux(self):
        fd = sys.stdin.fileno()

        if not sys.stdin.isatty():
            print(
                "Keyboard controller requires an interactive terminal.",
                flush=True
            )
            self.running = False
            return

        old_settings = termios.tcgetattr(fd)

        try:
            tty.setcbreak(fd)

            while self.running:
                readable, _, _ = select.select(
                    [fd], [], [], 0.05
                )

                if readable:
                    key = os.read(fd, 1).decode(
                        "utf-8", errors="ignore"
                    )

                    if key:
                        self._dispatch_key(key)

        finally:
            termios.tcsetattr(
                fd, termios.TCSADRAIN, old_settings
            )

    def get_commands(self):
        pending = []

        while True:
            try:
                pending.append(self.commands.get_nowait())
            except queue.Empty:
                break

        return pending

    def stop(self):
        self.running = False

        if self.thread is not None:
            self.thread.join(timeout=1.0)

        print("Keyboard controller stopped.")
