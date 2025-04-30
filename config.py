import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Determine base folder where the app is running
if getattr(sys, 'frozen', False):
    # Running inside a bundled app
    base_folder = Path(sys.executable).resolve().parents[3]
else:
    # Running from source
    base_folder = Path(__file__).resolve().parent

# Load the env.txt next to the .app
env_path = base_folder / "env.txt"
print(f"🔍 Looking for env.txt at: {env_path}")

load_dotenv(dotenv_path=env_path)

BASE_DIR = os.getenv("BASE_DIR")
print(f"🔍 Loaded BASE_DIR: {BASE_DIR}")

# Used for static and templates (relative to app)
TEMPLATES_DIR = os.path.join(sys._MEIPASS if getattr(sys, 'frozen', False) else base_folder, "templates")
STATIC_DIR = os.path.join(sys._MEIPASS if getattr(sys, 'frozen', False) else base_folder, "static")
