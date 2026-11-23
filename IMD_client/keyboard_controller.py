"""Non-blocking Windows console keyboard controller."""

import msvcrt
import queue
import threading
import time


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
        self.thread = threading.Thread(target=self._listen, daemon=True)
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

    def _listen(self):
        while self.running:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                action = self.key_bindings.get(key)
                if action is not None:
                    self.commands.put(action)
                    print(f"Keyboard command: {action}", flush=True)
                    if action == "quit":
                        self.running = False

            time.sleep(0.01)

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
