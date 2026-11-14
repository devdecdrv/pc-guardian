"""
PC Guardian — Web Dashboard
Local web panel at http://localhost:8080
Password protected, shows status/logs/controls
"""

import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify
from logs.logger import get_today_events, get_all_events

logger = logging.getLogger("dashboard")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

_lock_engine = None
_cfg = None
_activity = None


def init_dashboard(cfg, lock_engine, activity):
    global _lock_engine, _cfg, _activity
    _lock_engine = lock_engine
    _cfg = cfg
    _activity = activity


def run_dashboard(cfg, lock_engine, activity, port: int = 8080):
    init_dashboard(cfg, lock_engine, activity)
    logger.info(f"Dashboard running at http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if _cfg and pw == _cfg.web_dashboard.get("password", ""):
            session["auth"] = True
            return redirect("/")
        return render_template("login.html", error="Wrong password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


def require_auth(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("auth"):
            return redirect("/login")
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
@require_auth
def index():
    status = _lock_engine.status if _lock_engine else "unknown"
    events = get_today_events()[-10:]
    top_apps = _activity.get_top_apps_today() if _activity else []
    return render_template(
        "index.html",
        status=status,
        events=events,
        top_apps=top_apps,
        child_name=_cfg.child_name if _cfg else "Child",
        now=datetime.now().strftime("%H:%M %d %b")
    )


@app.route("/api/lock", methods=["POST"])
@require_auth
def api_lock():
    if _lock_engine:
        _lock_engine.lock()
    return jsonify({"status": "locked"})


@app.route("/api/unlock", methods=["POST"])
@require_auth
def api_unlock():
    if _lock_engine:
        _lock_engine.unlock()
    return jsonify({"status": "unlocked"})


@app.route("/api/status")
@require_auth
def api_status():
    return jsonify({
        "lock": _lock_engine.status if _lock_engine else "unknown",
        "session": _activity.get_session_duration() if _activity else "—",
        "top_app": _activity.get_active_apps_summary() if _activity else "—",
    })


@app.route("/api/events")
@require_auth
def api_events():
    return jsonify(get_today_events())
