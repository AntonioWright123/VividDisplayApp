from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from camera.file_handling import start_folder_watch
from shared.state import active_connections
from urllib.parse import unquote
from config import BASE_DIR, STATIC_DIR, TEMPLATES_DIR
import os
import threading
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

# Global to hold the observer thread
watcher_thread = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code (create favorites folders)
    session_names = os.listdir(BASE_DIR)
    for session_name in session_names:
        session_path = os.path.join(BASE_DIR, session_name)
        favorites_folder = os.path.join(session_path, "favorites")

        if os.path.isdir(session_path) and not os.path.exists(favorites_folder):
            os.makedirs(favorites_folder)
            print(f"Created favorites folder: {favorites_folder}")

    print("\u2705 Startup completed. Waiting for user to select shoot/session...")
    yield
    # (Optional) Shutdown cleanup code here if needed

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=BASE_DIR), name="media")

# Set up templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse(content="", status_code=204)

@app.websocket("/ws/{shoot_name}/{session_name}")
async def websocket_endpoint(websocket: WebSocket, shoot_name: str, session_name: str):
    decoded_session = unquote(session_name)
    decoded_shoot = unquote(shoot_name)
    print(f"[WebSocket] Connected to: {decoded_shoot}/{decoded_session}")

    await websocket.accept()
    active_connections.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

@app.get("/select", response_class=HTMLResponse)
async def select_page(request: Request, shoot_name: str = None):
    shoots = [f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))]
    sessions = []

    if shoot_name:
        shoot_path = os.path.join(BASE_DIR, shoot_name)
        sessions = [
            f for f in os.listdir(shoot_path)
            if os.path.isdir(os.path.join(shoot_path, f)) and f.lower() != "favorites"
        ]
    #newer syntax for fastapi "request"
    return templates.TemplateResponse(request,"select.html", {
        "request": request,
        "shoots": shoots,
        "sessions": sessions,
        "selected_shoot": shoot_name
    })

@app.post("/start_watch")
async def start_watch(
    shoot_name: str = Form(...),
    session_name: str = Form(...)
):
    global watcher_thread

  # import was here

    if watcher_thread and watcher_thread.is_alive():
        print("🔄 Restarting watcher...")

    # Start watching correct subfolder (shoot_name/session_name)
    watcher_thread = threading.Thread(target=start_folder_watch, args=(shoot_name, session_name), daemon=True)
    watcher_thread.start()

    # Redirect properly
    url = f"/{shoot_name}/{session_name}"
    return RedirectResponse(url=url, status_code=303)


@app.get("/{shoot_name}/{session_name}", response_class=HTMLResponse)
async def display_gallery(request: Request, shoot_name: str, session_name: str):
    session_path = os.path.join(BASE_DIR, shoot_name, session_name)

    if not os.path.exists(session_path):
        return HTMLResponse("Session folder not found.", status_code=404)

    images = [
        f for f in os.listdir(session_path)
        if f.lower().endswith((".jpg", ".jpeg"))
           and not f.startswith('.') and not f.startswith('._')
    ]

    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "shoot_name": shoot_name,
        "session_name": session_name,
        "images": images,
    })


if __name__ == "__main__":
    import uvicorn
    import time
    import webbrowser
    import sys

    def start_server():
        #0.0.0.0 for phone access as well
        #127.0.0.1 for just macOs
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

    threading.Thread(target=start_server, daemon=True).start()

    # Wait 2-3 seconds to make sure server actually started
    time.sleep(2)
    # uncomment below when packaged
    #if getattr(sys, 'frozen', False):

    webbrowser.open("http://127.0.0.1:8000/select")

    #  NEW PART: Keep the main thread alive forever
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
