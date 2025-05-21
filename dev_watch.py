# dev_watch.py
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib

# Paths or extensions to watch
WATCHED_DIRS = ["agents", "dashboard", "db", "analytics", "offer_worker.py", "match_worker.py", "docker-compose.yml", './']
EXTS = {".py", ".yaml", ".yml", ".tex"}

class RebuildHandler(FileSystemEventHandler):
    def __init__(self):
        self._last = 0
        self.debounce = 5.0  # seconds
        self.last_crc = {}

    def on_any_event(self, event):
        # only rebuild on file changes (not directory events)
        if event.is_directory:
            return
        if not any(event.src_path.endswith(ext) for ext in EXTS):
            return

        # compute new checksum
        new_crc = self.compute_crc(event.src_path)
        old_crc = self.last_crc.get(event.src_path)
        # ignore if checksum unchanged
        if new_crc and new_crc == old_crc:
            return
        # update last seen crc
        if new_crc:
            self.last_crc[event.src_path] = new_crc

        now = time.time()
        if now - self._last < self.debounce:
            return
        self._last = now
        print(f"[dev_watch] Detected real change in {event.src_path}. Rebuilding...")
        subprocess.run(["docker-compose", "down", "--timeout=10"], check=True)
        subprocess.run(["docker-compose", "up", "--build", "-d"], check=True)
        print("[dev_watch] Services restarted.")

    def compute_crc(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
            return hashlib.md5(data).hexdigest()
        except OSError:
            return None

if __name__ == "__main__":

    # ─── Startup: ensure services are running ───────────────────────
    try:
        # List running container IDs
        result = subprocess.run(
            ["docker-compose", "ps", "-q"],
            capture_output=True, text=True, check=True
        )
        running = [line for line in result.stdout.splitlines() if line.strip()]
        if not running:
            print("[dev_watch] No running services detected; starting docker-compose...")
            subprocess.run(["docker-compose", "up", "-d", "--build"], check=True)
            print("[dev_watch] Services started.")
    except subprocess.CalledProcessError as e:
        print(f"[dev_watch] Error checking services: {e}")

    observer = Observer()
    handler  = RebuildHandler()
    for path in WATCHED_DIRS:
        observer.schedule(handler, path=path, recursive=True)
    observer.start()
    print("[dev_watch] Watching for changes. Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
