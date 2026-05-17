#!/usr/bin/env python3
"""
Jarvis reminder dashboard — local network only.

Run on the Pi:
  cd ~/jarvis-assistant
  ./venv/bin/python dashboard/app.py

From your Mac (same Wi-Fi):
  http://PI_IP_ADDRESS:5000
"""

import os
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_timezone, now_local
from services.reminders.store import (
    Reminder,
    delete_reminder,
    list_all_reminders,
    mark_sent,
)

app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "change-me-in-env")


def _password_configured() -> bool:
    return bool(os.getenv("DASHBOARD_PASSWORD", "").strip())


def _status(reminder: Reminder) -> str:
    if reminder.sent:
        return "Completed"
    due = datetime.fromisoformat(reminder.due_at).astimezone(get_timezone())
    if due <= now_local():
        return "Overdue"
    return "Scheduled"


def _format_due(reminder: Reminder) -> str:
    due = datetime.fromisoformat(reminder.due_at).astimezone(get_timezone())
    return due.strftime("%a %b %d, %Y · %I:%M %p")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _password_configured():
            flash("Set DASHBOARD_PASSWORD in .env on the Pi, then restart.", "error")
            return redirect(url_for("login"))
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if not _password_configured():
        return render_template("login.html", password_missing=True)

    if request.method == "POST":
        password = request.form.get("password", "")
        expected = os.getenv("DASHBOARD_PASSWORD", "")
        if password and password == expected:
            session["logged_in"] = True
            session.permanent = True
            dest = request.args.get("next") or url_for("index")
            return redirect(dest)
        flash("Wrong password.", "error")

    return render_template("login.html", password_missing=False)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    rows = []
    for reminder in list_all_reminders():
        rows.append(
            {
                "id": reminder.id,
                "text": reminder.text,
                "due": _format_due(reminder),
                "status": _status(reminder),
                "source": reminder.source or "—",
                "sent": reminder.sent,
            }
        )
    return render_template("index.html", reminders=rows)


@app.post("/reminder/<reminder_id>/complete")
@login_required
def complete_reminder(reminder_id: str):
    mark_sent(reminder_id)
    flash("Marked complete.", "ok")
    return redirect(url_for("index"))


@app.post("/reminder/<reminder_id>/delete")
@login_required
def remove_reminder(reminder_id: str):
    if delete_reminder(reminder_id):
        flash("Reminder deleted.", "ok")
    else:
        flash("Reminder not found.", "error")
    return redirect(url_for("index"))


def main() -> None:
    if not _password_configured():
        print(
            "Warning: DASHBOARD_PASSWORD is not set in .env.\n"
            "Add it on the Pi, then restart the dashboard.",
            file=sys.stderr,
        )

    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"Jarvis dashboard: http://{host}:{port}  (use the Pi's LAN IP from your Mac)")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
