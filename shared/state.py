#shared/state.py
from typing import List
from fastapi import WebSocket

active_connections: List[WebSocket] = []
