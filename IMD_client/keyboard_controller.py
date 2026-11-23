
import msvcrt
import threading
import queue
import time


class KeyboardController:

    def __init__(self):
        self.commands = queue.Queue()
        self.running = False
        self.thread = None

    def start(self):
        """Start keyboard listener thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._listen,
            daemon=True
        )
        self.thread.start()

        print("\nKeyboard controller started.")
        print("  J = Move +X")
        print("  K = Stop")
        print("  L = Move -X")
        print("  Q = Quit\n")

    def _listen(self):
        """Monitor keyboard without blocking the main program."""

        while self.running:

            if msvcrt.kbhit():
                key = msvcrt.getch().decode(
                    "utf-8", errors="ignore"
                ).lower()

                if key == "j":
                    self.commands.put("forward")
                    print("Motor command: +X")

                elif key == "k":
                    self.commands.put("stop")
                    print("Motor command: STOP")

                elif key == "l":
                    self.commands.put("reverse")
                    print("Motor command: -X")

                elif key == "q":
                    self.commands.put("quit")
                    self.running = False
                    print("Keyboard controller stopping.")

            time.sleep(0.01)

    def get_commands(self):
        """Return all pending commands."""

        pending = []

        while not self.commands.empty():
            pending.append(self.commands.get())

        return pending

    def stop(self):
        """Stop keyboard listener."""
        self.running = False

        if self.thread is not None:
            self.thread.join(timeout=1.0)

        print("Keyboard controller stopped.")
