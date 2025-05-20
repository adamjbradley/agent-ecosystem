# dev_watch.py
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Paths or extensions to watch
WATCHED_DIRS = ["agents", "dashboard", "db", "analytics", "offer_worker.py", "match_worker.py", "docker-compose.yml", './']
EXTS = {".py", ".yaml", ".yml", ".tex"}

class RebuildHandler(FileSystemEventHandler):
    def __init__(self):
        self._last = 0
        self.debounce = 1.0  # seconds

    def on_any_event(self, event):
        # only rebuild on file changes (not directory events)
        if event.is_directory: 
            return
        if not any(event.src_path.endswith(ext) for ext in EXTS):
            return
        now = time.time()
        if now - self._last < self.debounce:
            return
        self._last = now
        print(f"[dev_watch] Detected change in {event.src_path}. Rebuilding...")
        subprocess.run(["docker-compose", "down"], check=True)
        subprocess.run(["docker-compose", "up", "--build", "-d"], check=True)
        print("[dev_watch] Services restarted.")

if __name__ == "__main__":
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
