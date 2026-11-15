"""
PC Guardian — MCP Custom Connector Server
Exposes guardian controls as an MCP-compatible HTTP API.
Connect via: https://your-tunnel-url/mcp

Run alongside main.py:
  python mcp_server.py

Tunnel publicly with ngrok:
  ngrok http 7860
  → gives you: https://xxxx.ngrok.io
  → paste that URL as your MCP connector in Claude
"""

import os
import sys
import json
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("mcp_server")

MCP_PORT  = 7860
MCP_TOKEN = "decdrv"   # Bearer token — change after testing

# ── SHARED STATE ─────────────────────────────────────────────────────────────
# Populated by main.py when it imports this module
_lock_engine = None
_camera      = None
_mic         = None
_speaker     = None
_activity    = None
_cfg         = None


def init(cfg, lock_engine, camera, mic, speaker, activity):
    global _lock_engine, _camera, _mic, _speaker, _activity, _cfg
    _cfg         = cfg
    _lock_engine = lock_engine
    _camera      = camera
    _mic         = mic
    _speaker     = speaker
    _activity    = activity


# ── MCP TOOL DEFINITIONS ─────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "lock_pc",
        "description": "Lock the PC immediately. Optionally for a set number of minutes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "duration_minutes": {
                    "type": "integer",
                    "description": "Minutes to lock for. Omit for indefinite lock."
                }
            }
        }
    },
    {
        "name": "unlock_pc",
        "description": "Unlock the PC.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_status",
        "description": "Get current PC lock status, active apps, and session duration.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "speak",
        "description": "Say a message through the PC speakers using text-to-speech.",
        "inputSchema": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string", "description": "Message to speak aloud."}
            }
        }
    },
    {
        "name": "play_preset",
        "description": "Play a preset parental message on the PC speakers.",
        "inputSchema": {
            "type": "object",
            "required": ["preset"],
            "properties": {
                "preset": {
                    "type": "string",
                    "enum": ["calm", "break", "bed", "good", "study", "eat"],
                    "description": "Preset message name."
                }
            }
        }
    },
    {
        "name": "take_snapshot",
        "description": "Take a photo from the PC webcam. Returns base64 encoded image.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_screenshot",
        "description": "Take a screenshot of what is currently on the PC screen.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_running_apps",
        "description": "List all apps currently running on the PC.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "record_mic",
        "description": "Record audio from the PC microphone. Returns base64 encoded wav.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "description": "Duration in seconds. Default 10.",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "set_volume",
        "description": "Set the PC speaker volume.",
        "inputSchema": {
            "type": "object",
            "required": ["level"],
            "properties": {
                "level": {
                    "type": "integer",
                    "description": "Volume level 0-100. Use 0 to mute."
                }
            }
        }
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory on the PC.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": r"Directory path. Default: C:\Users",
                    "default": r"C:\Users"
                }
            }
        }
    },
    {
        "name": "read_file",
        "description": "Read a file from the PC. Returns content as text.",
        "inputSchema": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "Full file path."}
            }
        }
    },
    {
        "name": "kill_app",
        "description": "Force close an application on the PC by name.",
        "inputSchema": {
            "type": "object",
            "required": ["app_name"],
            "properties": {
                "app_name": {"type": "string", "description": "Process name to kill."}
            }
        }
    },
    {
        "name": "get_activity_report",
        "description": "Get today's app usage summary and event log.",
        "inputSchema": {"type": "object", "properties": {}}
    },
]


# ── TOOL EXECUTION ────────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict) -> dict:
    try:
        if name == "lock_pc":
            dur = args.get("duration_minutes")
            _lock_engine.lock(duration_minutes=dur)
            return {"success": True, "message": f"PC locked{f' for {dur} minutes' if dur else ''}."}

        elif name == "unlock_pc":
            _lock_engine.unlock()
            return {"success": True, "message": "PC unlocked."}

        elif name == "get_status":
            return {
                "lock_status": _lock_engine.status,
                "session_duration": _activity.get_session_duration(),
                "active_apps": _activity.get_active_apps_summary(),
                "top_apps": _activity.get_top_apps_today(5),
            }

        elif name == "speak":
            _speaker.speak(args["text"])
            return {"success": True, "message": f"Speaking: {args['text']}"}

        elif name == "play_preset":
            n = _cfg.child_name
            presets = {
                "calm":  f"Calm down {n}, take a breath. Dad is here.",
                "break": f"Time for a break {n}. Come eat something.",
                "bed":   f"Bedtime {n}. Shut down the PC now.",
                "good":  f"Good job today {n}. I am proud of you.",
                "study": f"{n}, time to study now. Games later.",
                "eat":   f"{n}, come have your food. PC will wait.",
            }
            msg = presets.get(args["preset"], "")
            _speaker.speak(msg)
            return {"success": True, "message": f"Played preset: {args['preset']}"}

        elif name == "take_snapshot":
            import base64
            path = _camera.capture_snapshot()
            if not path:
                return {"success": False, "error": "Camera not available."}
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return {"success": True, "image_base64": b64, "format": "jpeg"}

        elif name == "get_screenshot":
            import base64, tempfile
            from PIL import ImageGrab
            img  = ImageGrab.grab()
            path = os.path.join(tempfile.gettempdir(), "pcg_mcp_screen.png")
            img.save(path)
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return {"success": True, "image_base64": b64, "format": "png"}

        elif name == "get_running_apps":
            return {"apps": _activity.get_running_apps()}

        elif name == "record_mic":
            import base64
            secs = args.get("seconds", 10)
            path = _mic.record_clip(secs)
            if not path:
                return {"success": False, "error": "Mic not available."}
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return {"success": True, "audio_base64": b64, "format": "wav", "seconds": secs}

        elif name == "set_volume":
            _speaker.set_volume(args["level"])
            return {"success": True, "volume": args["level"]}

        elif name == "list_directory":
            from core.file_manager import FileManager
            listing, err = FileManager(_cfg).list_dir(args.get("path", r"C:\Users"))
            if err:
                return {"success": False, "error": err}
            return {"success": True, "listing": listing}

        elif name == "read_file":
            from core.file_manager import FileManager
            data, err = FileManager(_cfg).read_file(args["path"])
            if err:
                return {"success": False, "error": err}
            try:
                return {"success": True, "content": data.decode("utf-8", errors="replace")}
            except Exception:
                import base64
                return {"success": True, "content_base64": base64.b64encode(data).decode()}

        elif name == "kill_app":
            import psutil
            killed = []
            for proc in psutil.process_iter(["name"]):
                try:
                    if args["app_name"].lower() in proc.info["name"].lower():
                        proc.kill()
                        killed.append(proc.info["name"])
                except Exception:
                    pass
            return {"success": bool(killed), "killed": killed}

        elif name == "get_activity_report":
            from logs.logger import get_today_events
            events = get_today_events()
            return {
                "top_apps": _activity.get_top_apps_today(10),
                "session": _activity.get_session_duration(),
                "event_count": len(events),
                "recent_events": events[-10:],
            }

        else:
            return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return {"error": str(e)}


# ── HTTP HANDLER ──────────────────────────────────────────────────────────────

class MCPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default HTTP logs

    def _auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {MCP_TOKEN}"

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # MCP discovery endpoint
        if path in ("/", "/mcp"):
            self._send_json(200, {
                "name": "PC Guardian",
                "description": "Remote parental control — lock, camera, mic, speaker, files.",
                "version": "1.0.0",
                "tools": TOOLS,
            })
        elif path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._auth():
            self._send_json(401, {"error": "Unauthorized. Set Authorization: Bearer decdrv"})
            return

        path = urlparse(self.path).path

        length  = int(self.headers.get("Content-Length", 0))
        body    = self.rfile.read(length)

        try:
            payload = json.loads(body) if body else {}
        except Exception:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        if path in ("/mcp", "/call", "/tools/call"):
            tool_name = payload.get("name") or payload.get("tool")
            tool_args = payload.get("arguments") or payload.get("input") or {}
            if not tool_name:
                self._send_json(400, {"error": "Missing 'name' field"})
                return
            result = execute_tool(tool_name, tool_args)
            self._send_json(200, {"result": result})
        else:
            self._send_json(404, {"error": "Not found"})


# ── SERVER ────────────────────────────────────────────────────────────────────

def run_mcp_server():
    server = HTTPServer(("0.0.0.0", MCP_PORT), MCPHandler)
    logger.info(f"MCP server running on port {MCP_PORT}")
    print(f"\n✓ MCP server running on http://localhost:{MCP_PORT}")
    print(f"  Token: {MCP_TOKEN}")
    print(f"  Tunnel with: ngrok http {MCP_PORT}")
    print(f"  Then add https://xxxx.ngrok.io as custom MCP in Claude\n")
    server.serve_forever()


def start_mcp_thread():
    t = threading.Thread(target=run_mcp_server, daemon=True, name="MCPServer")
    t.start()


if __name__ == "__main__":
    # Standalone test mode — no guardian systems
    print("Running MCP server in standalone test mode.")
    print("Guardian systems not loaded — start via main.py for full functionality.")
    run_mcp_server()
