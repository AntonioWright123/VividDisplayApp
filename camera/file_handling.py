import os
import time
import asyncio
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from shared.state import active_connections
from config import BASE_DIR
from dotenv import load_dotenv

load_dotenv()


# 5s for agressive response, 10 for a med, 15 for slow writes
processed_files = set()
recent_events = {}
CACHE_SECONDS = 10

def should_ignore_file(full_media_path):
    now = time.monotonic()

    for old_file, seen_time in list(recent_events.items()):
        if now - seen_time > CACHE_SECONDS:
            del recent_events[old_file]

    if full_media_path in processed_files:
        return True

    if full_media_path in recent_events:
        print(f"⏭️ Skipping duplicate event: {full_media_path}")
        return True

    recent_events[full_media_path] = now
    processed_files.add(full_media_path)
    return False

class NewImageHandler(FileSystemEventHandler):
    def __init__(self, shoot_name, session_name):
        self.shoot_name = shoot_name
        self.session_name = session_name
        self.session_path = os.path.join(BASE_DIR, shoot_name, session_name)

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith((".jpg", ".jpeg")):
            filename = os.path.basename(event.src_path)
            full_media_path = f"{self.shoot_name}/{self.session_name}/{filename}"

            if should_ignore_file(full_media_path):
                return

            print(f"📝 Detected new file: {filename}, waiting for it to finish writing...")

            last_size = -1
            stable_counter = 0

            # Watch the file size until it stops changing
            for attempt in range(30):  # Allow up to ~30 seconds
                try:
                    current_size = os.path.getsize(event.src_path)
                    if current_size == last_size:
                        stable_counter += 1
                        if stable_counter >= 3:  # Size stable for 3 consecutive checks
                            print(f"✅ File {filename} finished writing.")
                            break
                    else:
                        stable_counter = 0  # Reset counter if file size changes
                    last_size = current_size
                except Exception:
                    pass
                time.sleep(1)  # Check every 1 second



            print(f"[+] New image: {filename}")
            print(f"[→] Sending to clients: {full_media_path}")

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(send_to_clients(full_media_path))
            except RuntimeError:
                asyncio.run(send_to_clients(full_media_path))


async def send_to_clients(filename):
    for conn in active_connections:
        await conn.send_text(filename)

def poll_for_new_images(handler):
    while True:
        try:
            for fname in os.listdir(handler.session_path):
                if fname.lower().endswith((".jpg", ".jpeg")):
                    full_media_path = f"{handler.shoot_name}/{handler.session_name}/{fname}"
                    if not should_ignore_file(full_media_path):
                        print(f"[+] (Fallback) Found new image: {fname}")
                        asyncio.run(send_to_clients(full_media_path))
        except Exception as e:
            print(f"[!] Polling error: {e}")

        time.sleep(5)

def start_folder_watch(shoot_name, session_name):
    session_path = os.path.join(BASE_DIR, shoot_name, session_name)
    print(f"📸 Watching session: {session_path}")

    handler = NewImageHandler(shoot_name, session_name)
    observer = Observer()
    observer.schedule(handler, path=session_path, recursive=False)
    observer.start()

    threading.Thread(target=poll_for_new_images, args=(handler,), daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
