"""Workforce Monitor - single-file edition (portal server).

Everything (database, routes, API, HTML templates) is in this one file so it is
trivial to upload. Run locally:  python app.py   On Render:  gunicorn app:app
"""
import os
import functools
import sqlite3
import secrets
from datetime import datetime, timezone, timedelta
from flask import (Flask, request, redirect, url_for, render_template,
                   session, flash, abort, jsonify)
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash

TEMPLATES = {
"base.html": "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>{% block title %}Workforce Monitor{% endblock %}</title>\n<style>\n  :root{--bg:#f5f6f8;--card:#fff;--ink:#1a1d24;--muted:#6b7280;--line:#e5e7eb;\n        --brand:#2563eb;--good:#16a34a;--warn:#d97706;--bad:#dc2626;}\n  *{box-sizing:border-box}\n  body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;\n       background:var(--bg);color:var(--ink)}\n  a{color:var(--brand);text-decoration:none} a:hover{text-decoration:underline}\n  header{background:var(--card);border-bottom:1px solid var(--line);padding:0 20px;\n         display:flex;align-items:center;gap:22px;height:56px;position:sticky;top:0;z-index:5}\n  header .brand{font-weight:700} header nav{display:flex;gap:18px;flex:1;flex-wrap:wrap}\n  header .me{color:var(--muted);font-size:13px}\n  .wrap{max-width:1000px;margin:24px auto;padding:0 16px}\n  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;\n        padding:20px;margin-bottom:18px}\n  h1{font-size:22px;margin:.2em 0 .6em} h2{font-size:17px;margin:0 0 12px}\n  table{width:100%;border-collapse:collapse} th,td{text-align:left;padding:10px 8px;\n        border-bottom:1px solid var(--line);font-size:14px} th{color:var(--muted);font-weight:600}\n  .pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600}\n  .on{background:#dcfce7;color:var(--good)} .off{background:#f3f4f6;color:var(--muted)}\n  label{display:block;font-size:13px;color:var(--muted);margin:10px 0 4px}\n  input,select{width:100%;padding:9px 10px;border:1px solid var(--line);border-radius:8px;font:inherit}\n  .row{display:flex;gap:14px;flex-wrap:wrap} .row>div{flex:1;min-width:180px}\n  .check{display:flex;align-items:center;gap:8px;margin:10px 0} .check input{width:auto}\n  button,.btn{background:var(--brand);color:#fff;border:0;padding:10px 16px;border-radius:8px;\n         font:inherit;font-weight:600;cursor:pointer;margin-top:14px}\n  .flash{padding:10px 14px;border-radius:8px;margin-bottom:14px;font-size:14px}\n  .flash.ok{background:#dcfce7;color:#166534} .flash.error{background:#fee2e2;color:#991b1b}\n  .muted{color:var(--muted);font-size:13px}\n  .badge{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);\n         border:1px solid var(--line);border-radius:6px;padding:2px 7px}\n</style>\n</head>\n<body>\n{% if user %}\n<header>\n  <span class=\"brand\">Workforce&nbsp;Monitor</span>\n  <nav>\n    <a href=\"{{ url_for('dashboard') }}\">Live board</a>\n    {% if user.role in ['owner','admin'] %}<a href=\"{{ url_for('employees') }}\">Employees</a>{% endif %}\n    {% if user.role in ['owner','admin'] %}<a href=\"{{ url_for('company') }}\">Company</a>{% endif %}\n    {% if user.role != 'employee' %}<a href=\"{{ url_for('reports') }}\">Reports</a>{% endif %}\n    <a href=\"{{ url_for('profile') }}\">My profile</a>\n  </nav>\n  <span class=\"me\">{{ user.name }} · <span class=\"badge\">{{ user.role }}</span>\n    · <a href=\"{{ url_for('logout') }}\">Log out</a></span>\n</header>\n{% endif %}\n<div class=\"wrap\">\n  {% with msgs = get_flashed_messages(with_categories=true) %}\n    {% for cat,msg in msgs %}<div class=\"flash {{ cat }}\">{{ msg }}</div>{% endfor %}\n  {% endwith %}\n  {% block body %}{% endblock %}\n</div>\n</body>\n</html>\n",
"company.html": "{% extends \"base.html\" %}\n{% block title %}Company · Workforce Monitor{% endblock %}\n{% block body %}\n<h1>Company & monitoring settings</h1>\n{% if companies is not none %}\n<div class=\"card\">\n  <form method=\"get\">\n    <label>Choose a company (owner view)</label>\n    <select name=\"id\" onchange=\"this.form.submit()\">\n      {% for c in companies %}\n      <option value=\"{{ c.id }}\" {{ 'selected' if comp and c.id==comp.id }}>{{ c.name }}</option>\n      {% endfor %}\n    </select>\n  </form>\n</div>\n{% endif %}\n\n{% if comp %}\n<div class=\"card\" style=\"max-width:640px\">\n  <form method=\"post\">\n    <input type=\"hidden\" name=\"company_id\" value=\"{{ comp.id }}\">\n    <h2>Details</h2>\n    <div class=\"row\">\n      <div><label>Company name</label><input name=\"name\" value=\"{{ comp.name }}\"></div>\n      <div><label>Timezone</label><input name=\"timezone\" value=\"{{ comp.timezone }}\"></div>\n    </div>\n    <label>Logo URL</label><input name=\"logo_url\" value=\"{{ comp.logo_url or '' }}\">\n    <div class=\"row\">\n      <div><label>Work start</label><input name=\"work_start\" value=\"{{ comp.work_start }}\"></div>\n      <div><label>Work end</label><input name=\"work_end\" value=\"{{ comp.work_end }}\"></div>\n    </div>\n\n    <h2 style=\"margin-top:22px\">Monitoring</h2>\n    <div class=\"check\"><input type=\"checkbox\" name=\"screenshots_enabled\" id=\"ss\"\n         {{ 'checked' if comp.screenshots_enabled }}>\n      <label for=\"ss\" style=\"margin:0\">Enable screenshots (Phase 2)</label></div>\n    <label>Screenshot interval (minutes)</label>\n    <input name=\"screenshot_interval_min\" type=\"number\" value=\"{{ comp.screenshot_interval_min }}\">\n    <div class=\"check\"><input type=\"checkbox\" name=\"webcam_enabled\" id=\"wc\"\n         {{ 'checked' if comp.webcam_enabled }}>\n      <label for=\"wc\" style=\"margin:0\">Enable webcam — opt-in, requires written consent (Phase 4)</label></div>\n    <label>Keep captured data for (days)</label>\n    <input name=\"retention_days\" type=\"number\" value=\"{{ comp.retention_days }}\">\n\n    <h2 style=\"margin-top:22px\">Reports</h2>\n    <div class=\"check\"><input type=\"checkbox\" name=\"share_reports_with_seller\" id=\"sr\"\n         {{ 'checked' if comp.share_reports_with_seller }}>\n      <label for=\"sr\" style=\"margin:0\">Let Sellers/Clients see reports for their assigned staff</label></div>\n\n    <button type=\"submit\">Save settings</button>\n  </form>\n</div>\n{% else %}\n<div class=\"card\"><p class=\"muted\">No company selected.</p></div>\n{% endif %}\n{% endblock %}\n",
"dashboard.html": "{% extends \"base.html\" %}\n{% block title %}Live board · Workforce Monitor{% endblock %}\n{% block body %}\n<h1>Live board</h1>\n<p class=\"muted\">Who is working right now. \"Online\" means the agent sent a heartbeat\nin the last {{ window }} seconds. This page auto-refreshes every 30 seconds.</p>\n<div class=\"card\">\n<table>\n  <tr>\n    <th>Employee</th>\n    {% if user.role == 'owner' %}<th>Company</th>{% endif %}\n    <th>Status</th><th>Current app</th><th>Clocked in</th>\n  </tr>\n  {% for p in people %}\n  <tr>\n    <td>{{ p.row.name }}<br><span class=\"muted\">{{ p.row.email }}</span></td>\n    {% if user.role == 'owner' %}<td>{{ p.row.company_name or '—' }}</td>{% endif %}\n    <td><span class=\"pill {{ 'on' if p.online else 'off' }}\">\n        {{ 'Online' if p.online else 'Offline' }}</span></td>\n    <td>{{ p.row.current_app or '—' }}</td>\n    <td class=\"muted\">{{ p.row.clock_in[11:16] if p.row.clock_in and not p.row.clock_out else '—' }}</td>\n  </tr>\n  {% else %}\n  <tr><td colspan=\"5\" class=\"muted\">No employees yet.</td></tr>\n  {% endfor %}\n</table>\n</div>\n<script>setTimeout(function(){location.reload()}, 30000);</script>\n{% endblock %}\n",
"employees.html": "{% extends \"base.html\" %}\n{% block title %}Employees · Workforce Monitor{% endblock %}\n{% block body %}\n<h1>Employees</h1>\n{% if companies is not none %}\n<div class=\"card\">\n  <form method=\"get\">\n    <label>Company (owner view)</label>\n    <select name=\"id\" onchange=\"this.form.submit()\">\n      {% for c in companies %}\n      <option value=\"{{ c.id }}\" {{ 'selected' if c.id==cid }}>{{ c.name }}</option>\n      {% endfor %}\n    </select>\n  </form>\n</div>\n{% endif %}\n\n<div class=\"card\">\n<table>\n  <tr><th>Name</th><th>Email</th><th>Pay</th><th>Assigned seller</th><th>Consent</th></tr>\n  {% for e in emps %}\n  <tr>\n    <td>{{ e.name }}</td><td>{{ e.email }}</td>\n    <td>{% if e.pay_type=='hourly' %}₹{{ e.pay_rate }}/hr{% else %}₹{{ e.pay_rate }}/mo{% endif %}</td>\n    <td>{% set s = (sellers|selectattr('id','equalto',e.seller_id)|list) %}\n        {{ s[0].name if s else '—' }}</td>\n    <td>{{ 'yes' if e.consent_given else 'no' }}</td>\n  </tr>\n  {% else %}\n  <tr><td colspan=\"5\" class=\"muted\">No employees yet.</td></tr>\n  {% endfor %}\n</table>\n</div>\n\n<div class=\"card\" style=\"max-width:640px\">\n  <h2>Add an employee</h2>\n  <form method=\"post\">\n    {% if companies is not none %}<input type=\"hidden\" name=\"company_id\" value=\"{{ cid }}\">{% endif %}\n    <div class=\"row\">\n      <div><label>Name</label><input name=\"name\" required></div>\n      <div><label>Email</label><input name=\"email\" type=\"email\" required></div>\n    </div>\n    <div class=\"row\">\n      <div><label>Temporary password</label><input name=\"password\" value=\"ChangeMe123!\"></div>\n      <div><label>Assign to seller</label>\n        <select name=\"seller_id\"><option value=\"\">— none —</option>\n          {% for s in sellers %}<option value=\"{{ s.id }}\">{{ s.name }}</option>{% endfor %}\n        </select></div>\n    </div>\n    <div class=\"row\">\n      <div><label>Pay type</label>\n        <select name=\"pay_type\"><option value=\"hourly\">Hourly (₹/hr)</option>\n          <option value=\"monthly\">Monthly (₹/mo)</option></select></div>\n      <div><label>Pay rate (₹)</label><input name=\"pay_rate\" type=\"number\" step=\"0.01\" value=\"0\"></div>\n    </div>\n    <div class=\"check\"><input type=\"checkbox\" name=\"consent_given\" id=\"cg\">\n      <label for=\"cg\" style=\"margin:0\">Employee has signed the monitoring consent policy</label></div>\n    <button type=\"submit\">Add employee</button>\n  </form>\n</div>\n{% endblock %}\n",
"login.html": "{% extends \"base.html\" %}\n{% block title %}Sign in · Workforce Monitor{% endblock %}\n{% block body %}\n<div class=\"card\" style=\"max-width:380px;margin:8vh auto\">\n  <h1>Workforce Monitor</h1>\n  <p class=\"muted\">Sign in to your portal.</p>\n  <form method=\"post\">\n    <label>Email</label>\n    <input name=\"email\" type=\"email\" autocomplete=\"username\" required autofocus>\n    <label>Password</label>\n    <input name=\"password\" type=\"password\" autocomplete=\"current-password\" required>\n    <button type=\"submit\">Sign in</button>\n  </form>\n  <p class=\"muted\" style=\"margin-top:14px\">New here?\n    <a href=\"{{ url_for('signup') }}\">Create a company portal</a>.</p>\n</div>\n{% endblock %}\n",
"profile.html": "{% extends \"base.html\" %}\n{% block title %}My profile · Workforce Monitor{% endblock %}\n{% block body %}\n<h1>My profile</h1>\n<p class=\"muted\">Everyone can edit their own details here.</p>\n<div class=\"card\" style=\"max-width:520px\">\n  <form method=\"post\">\n    <div class=\"row\">\n      <div><label>Name</label><input name=\"name\" value=\"{{ u.name }}\"></div>\n      <div><label>Phone</label><input name=\"phone\" value=\"{{ u.phone or '' }}\"></div>\n    </div>\n    <label>Photo URL</label>\n    <input name=\"photo_url\" value=\"{{ u.photo_url or '' }}\" placeholder=\"https://...\">\n    <label>Email (login) — ask an admin to change this</label>\n    <input value=\"{{ u.email }}\" disabled>\n    <label>New password (leave blank to keep current)</label>\n    <input name=\"new_password\" type=\"password\" autocomplete=\"new-password\">\n    <button type=\"submit\">Save profile</button>\n  </form>\n</div>\n{% if u.role == 'employee' %}\n<div class=\"card\" style=\"max-width:520px\">\n  <h2>Desktop agent</h2>\n  <p class=\"muted\">Paste this token into the desktop agent to connect it to your account.\n  Keep it private.</p>\n  <input value=\"{{ u.agent_token }}\" readonly onclick=\"this.select()\">\n  <p class=\"muted\" style=\"margin-top:10px\">Monitoring consent:\n    {{ 'given' if u.consent_given else 'not yet given — ask your admin' }}.</p>\n</div>\n{% endif %}\n{% endblock %}\n",
"reports.html": "{% extends \"base.html\" %}\n{% block title %}Reports · Workforce Monitor{% endblock %}\n{% block body %}\n<h1>Reports</h1>\n{% if blocked %}\n<div class=\"card\"><p class=\"muted\">Report sharing with sellers is turned off for this\ncompany. Ask the admin to enable it under Company settings.</p></div>\n{% else %}\n<p class=\"muted\">Worked hours today (time tracked by the agent, minus idle time).</p>\n<div class=\"card\">\n<table>\n  <tr><th>Employee</th><th>Company / role</th><th>Hours today</th></tr>\n  {% for d in data %}\n  <tr>\n    <td>{{ d.emp.name }}<br><span class=\"muted\">{{ d.emp.email }}</span></td>\n    <td class=\"muted\">{{ d.emp.pay_type }}</td>\n    <td>{{ d.hours_today }}</td>\n  </tr>\n  {% else %}\n  <tr><td colspan=\"3\" class=\"muted\">No data yet.</td></tr>\n  {% endfor %}\n</table>\n</div>\n<p class=\"muted\">Payroll (hours × pay rate) and CSV export arrive in Phase 3.</p>\n{% endif %}\n{% endblock %}\n",
"signup.html": "{% extends \"base.html\" %}\n{% block title %}Create your portal · Workforce Monitor{% endblock %}\n{% block body %}\n<div class=\"card\" style=\"max-width:440px;margin:6vh auto\">\n  <h1>Create your company portal</h1>\n  <p class=\"muted\">Start a free portal. You become the admin for your company.</p>\n  <form method=\"post\">\n    <label>Company name</label><input name=\"company\" required autofocus>\n    <label>Your name</label><input name=\"name\" required>\n    <label>Work email</label><input name=\"email\" type=\"email\" required>\n    <label>Password</label><input name=\"password\" type=\"password\" required>\n    <button type=\"submit\">Create portal</button>\n  </form>\n  <p class=\"muted\" style=\"margin-top:14px\">Already have an account?\n    <a href=\"{{ url_for('login') }}\">Sign in</a>.</p>\n</div>\n{% endblock %}\n"
}


# ---------- database ----------
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data.db"))

ROLES = ("owner", "admin", "seller", "employee")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    logo_url TEXT DEFAULT '',
    timezone TEXT DEFAULT 'Asia/Kolkata',
    work_start TEXT DEFAULT '09:00',
    work_end TEXT DEFAULT '18:00',
    screenshots_enabled INTEGER DEFAULT 0,
    screenshot_interval_min INTEGER DEFAULT 10,
    webcam_enabled INTEGER DEFAULT 0,
    retention_days INTEGER DEFAULT 60,
    share_reports_with_seller INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,              -- NULL for the platform owner
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,              -- owner | admin | seller | employee
    photo_url TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    pay_type TEXT DEFAULT 'hourly',  -- hourly | monthly
    pay_rate REAL DEFAULT 0,         -- per hour, or monthly salary
    seller_id INTEGER,               -- for employees: which seller/client they are assigned to
    consent_given INTEGER DEFAULT 0, -- employee agreed to monitoring policy
    agent_token TEXT,                -- secret the desktop agent uses to authenticate
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS work_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    clock_in TEXT NOT NULL,
    clock_out TEXT,
    last_heartbeat TEXT,
    current_app TEXT DEFAULT '',
    idle_seconds INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS api_tokens (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def column_missing(conn, table, col):
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
    return col not in cols


# ---------- user helpers ----------

def create_user(conn, company_id, email, password, name, role, **extra):
    assert role in ROLES, f"bad role {role}"
    token = secrets.token_urlsafe(24)
    conn.execute(
        """INSERT INTO users (company_id, email, password_hash, name, role,
               photo_url, phone, pay_type, pay_rate, seller_id, consent_given,
               agent_token, active, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
        (
            company_id, email.lower().strip(), generate_password_hash(password),
            name, role,
            extra.get("photo_url", ""), extra.get("phone", ""),
            extra.get("pay_type", "hourly"), extra.get("pay_rate", 0),
            extra.get("seller_id"), extra.get("consent_given", 0),
            token, now_iso(),
        ),
    )
    conn.commit()
    return conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()


def find_user_by_email(conn, email):
    return conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()


def verify_login(conn, email, password):
    u = find_user_by_email(conn, email)
    if u and u["active"] and check_password_hash(u["password_hash"], password):
        return u
    return None


# ---------- seed demo data ----------

def seed_if_empty():
    """Create a platform owner and one demo company with an admin, seller and two
    employees, so you can log in and see every role working on first run."""
    init_db()
    conn = get_db()
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] > 0:
        conn.close()
        return

    owner_email = os.environ.get("OWNER_EMAIL", "owner@dollaritservices.com")
    owner_pw = os.environ.get("OWNER_PASSWORD", "ChangeMe123!")
    create_user(conn, None, owner_email, owner_pw, "Platform Owner", "owner")

    conn.execute(
        """INSERT INTO companies (name, timezone, work_start, work_end, created_at)
           VALUES (?,?,?,?,?)""",
        ("Demo Client Pvt Ltd", "Asia/Kolkata", "09:00", "18:00", now_iso()),
    )
    conn.commit()
    cid = conn.execute("SELECT id FROM companies ORDER BY id DESC LIMIT 1").fetchone()["id"]

    admin = create_user(conn, cid, "admin@demo.com", "ChangeMe123!", "Asha Admin", "admin")
    seller = create_user(conn, cid, "seller@demo.com", "ChangeMe123!", "Sam Seller", "seller")
    create_user(conn, cid, "emp1@demo.com", "ChangeMe123!", "Ravi Kumar", "employee",
                pay_type="hourly", pay_rate=300, seller_id=seller["id"], consent_given=1)
    create_user(conn, cid, "emp2@demo.com", "ChangeMe123!", "Priya Nair", "employee",
                pay_type="monthly", pay_rate=45000, seller_id=seller["id"], consent_given=1)
    conn.close()

# ---------- web app ----------
from flask import (Flask, request, redirect, url_for, render_template,
                   session, flash, abort, jsonify)


app = Flask(__name__)
app.jinja_loader = DictLoader(TEMPLATES)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["ONLINE_WINDOW_SEC"] = 90  # heartbeat newer than this = "online"

seed_if_empty()


# ----------------------------------------------------------------------------
# auth helpers
# ----------------------------------------------------------------------------
def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id = ? AND active = 1", (uid,)).fetchone()
    conn.close()
    return u


def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if not current_user():
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def roles_required(*allowed):
    def deco(view):
        @functools.wraps(view)
        def wrapped(*a, **kw):
            u = current_user()
            if not u:
                return redirect(url_for("login"))
            if u["role"] not in allowed:
                abort(403)
            return view(*a, **kw)
        return wrapped
    return deco


@app.context_processor
def inject_user():
    return {"user": current_user()}


# ----------------------------------------------------------------------------
# auth routes
# ----------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_db()
        u = verify_login(conn, request.form.get("email", ""), request.form.get("password", ""))
        conn.close()
        if u:
            session["uid"] = u["id"]
            return redirect(url_for("dashboard"))
        flash("Wrong email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Public self-serve onboarding: creates a new client company + its first admin."""
    if request.method == "POST":
        f = request.form
        conn = get_db()
        if find_user_by_email(conn, f.get("email", "")):
            flash("That email is already registered.", "error")
            conn.close()
            return render_template("signup.html")
        conn.execute("""INSERT INTO companies (name, timezone, work_start, work_end, created_at)
                        VALUES (?,?,?,?,?)""",
                     (f.get("company", "My Company"), "Asia/Kolkata", "09:00", "18:00", now_iso()))
        conn.commit()
        cid = conn.execute("SELECT id FROM companies ORDER BY id DESC LIMIT 1").fetchone()["id"]
        create_user(conn, cid, f["email"], f.get("password", "ChangeMe123!"),
                    f.get("name", "Admin"), "admin")
        u = find_user_by_email(conn, f["email"])
        conn.close()
        session["uid"] = u["id"]
        flash("Welcome! Your company portal is ready.", "ok")
        return redirect(url_for("dashboard"))
    return render_template("signup.html")


# ----------------------------------------------------------------------------
# dashboard: live who's-online board
# ----------------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    u = current_user()
    conn = get_db()
    window = (datetime.now(timezone.utc) - timedelta(seconds=app.config["ONLINE_WINDOW_SEC"])).isoformat()

    # scope rows by role (company isolation)
    if u["role"] == "owner":
        rows = conn.execute("""
            SELECT u.*, c.name company_name,
                   ws.clock_in, ws.clock_out, ws.last_heartbeat, ws.current_app
            FROM users u LEFT JOIN companies c ON c.id = u.company_id
            LEFT JOIN work_sessions ws ON ws.id = (
                SELECT id FROM work_sessions w WHERE w.user_id = u.id ORDER BY id DESC LIMIT 1)
            WHERE u.role = 'employee' ORDER BY c.name, u.name""").fetchall()
    elif u["role"] in ("admin",):
        rows = conn.execute("""
            SELECT u.*, c.name company_name,
                   ws.clock_in, ws.clock_out, ws.last_heartbeat, ws.current_app
            FROM users u LEFT JOIN companies c ON c.id = u.company_id
            LEFT JOIN work_sessions ws ON ws.id = (
                SELECT id FROM work_sessions w WHERE w.user_id = u.id ORDER BY id DESC LIMIT 1)
            WHERE u.role = 'employee' AND u.company_id = ? ORDER BY u.name""", (u["company_id"],)).fetchall()
    elif u["role"] == "seller":
        rows = conn.execute("""
            SELECT u.*, c.name company_name,
                   ws.clock_in, ws.clock_out, ws.last_heartbeat, ws.current_app
            FROM users u LEFT JOIN companies c ON c.id = u.company_id
            LEFT JOIN work_sessions ws ON ws.id = (
                SELECT id FROM work_sessions w WHERE w.user_id = u.id ORDER BY id DESC LIMIT 1)
            WHERE u.role = 'employee' AND u.seller_id = ? ORDER BY u.name""", (u["id"],)).fetchall()
    else:  # employee: only self
        rows = conn.execute("""
            SELECT u.*, c.name company_name,
                   ws.clock_in, ws.clock_out, ws.last_heartbeat, ws.current_app
            FROM users u LEFT JOIN companies c ON c.id = u.company_id
            LEFT JOIN work_sessions ws ON ws.id = (
                SELECT id FROM work_sessions w WHERE w.user_id = u.id ORDER BY id DESC LIMIT 1)
            WHERE u.id = ?""", (u["id"],)).fetchall()
    conn.close()

    people = []
    for r in rows:
        online = bool(r["last_heartbeat"] and r["last_heartbeat"] >= window
                      and not r["clock_out"])
        people.append({"row": r, "online": online})
    return render_template("dashboard.html", people=people, window=app.config["ONLINE_WINDOW_SEC"])


# ----------------------------------------------------------------------------
# self-service: own profile (everyone)
# ----------------------------------------------------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    u = current_user()
    conn = get_db()
    if request.method == "POST":
        f = request.form
        fields = {"name": f.get("name", u["name"]), "phone": f.get("phone", ""),
                  "photo_url": f.get("photo_url", "")}
        conn.execute("UPDATE users SET name=?, phone=?, photo_url=? WHERE id=?",
                     (fields["name"], fields["phone"], fields["photo_url"], u["id"]))
        if f.get("new_password"):
            from werkzeug.security import generate_password_hash
            conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                         (generate_password_hash(f["new_password"]), u["id"]))
        conn.commit()
        conn.close()
        flash("Profile saved.", "ok")
        return redirect(url_for("profile"))
    conn.close()
    return render_template("profile.html", u=u)


# ----------------------------------------------------------------------------
# company + monitoring settings (admin / owner)
# ----------------------------------------------------------------------------
@app.route("/company", methods=["GET", "POST"])
@roles_required("owner", "admin")
def company():
    u = current_user()
    conn = get_db()
    # owner can pick a company via ?id=, admin is locked to their own
    cid = u["company_id"]
    if u["role"] == "owner":
        cid = request.args.get("id", type=int) or request.form.get("company_id", type=int) or cid
    companies = conn.execute("SELECT * FROM companies ORDER BY name").fetchall() if u["role"] == "owner" else None

    if request.method == "POST" and cid:
        f = request.form
        conn.execute("""UPDATE companies SET name=?, logo_url=?, timezone=?, work_start=?,
                        work_end=?, screenshots_enabled=?, screenshot_interval_min=?,
                        webcam_enabled=?, retention_days=?, share_reports_with_seller=?
                        WHERE id=?""",
                     (f.get("name"), f.get("logo_url", ""), f.get("timezone", "Asia/Kolkata"),
                      f.get("work_start", "09:00"), f.get("work_end", "18:00"),
                      1 if f.get("screenshots_enabled") else 0,
                      f.get("screenshot_interval_min", 10, type=int),
                      1 if f.get("webcam_enabled") else 0,
                      f.get("retention_days", 60, type=int),
                      1 if f.get("share_reports_with_seller") else 0, cid))
        conn.commit()
        flash("Company settings saved.", "ok")
        conn.close()
        return redirect(url_for("company", id=cid) if u["role"] == "owner" else url_for("company"))

    comp = conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() if cid else None
    conn.close()
    return render_template("company.html", comp=comp, companies=companies)


# ----------------------------------------------------------------------------
# employees list + add (admin / owner)
# ----------------------------------------------------------------------------
@app.route("/employees", methods=["GET", "POST"])
@roles_required("owner", "admin")
def employees():
    u = current_user()
    conn = get_db()
    cid = u["company_id"]
    if u["role"] == "owner":
        cid = request.args.get("id", type=int) or request.form.get("company_id", type=int) or cid

    if request.method == "POST" and cid:
        f = request.form
        if find_user_by_email(conn, f.get("email", "")):
            flash("That email is already registered.", "error")
        else:
            create_user(conn, cid, f["email"], f.get("password", "ChangeMe123!"),
                        f.get("name", "New Employee"), "employee",
                        pay_type=f.get("pay_type", "hourly"),
                        pay_rate=f.get("pay_rate", 0, type=float),
                        seller_id=f.get("seller_id", type=int),
                        consent_given=1 if f.get("consent_given") else 0)
            flash("Employee added.", "ok")

    emps = conn.execute("SELECT * FROM users WHERE role='employee' AND company_id=? ORDER BY name",
                        (cid,)).fetchall() if cid else []
    sellers = conn.execute("SELECT * FROM users WHERE role='seller' AND company_id=? ORDER BY name",
                           (cid,)).fetchall() if cid else []
    companies = conn.execute("SELECT * FROM companies ORDER BY name").fetchall() if u["role"] == "owner" else None
    conn.close()
    return render_template("employees.html", emps=emps, sellers=sellers,
                           companies=companies, cid=cid)


# ----------------------------------------------------------------------------
# reports (seller / admin / owner) + report preference
# ----------------------------------------------------------------------------
@app.route("/reports")
@login_required
def reports():
    u = current_user()
    if u["role"] == "employee":
        abort(403)
    conn = get_db()
    if u["role"] == "owner":
        emps = conn.execute("SELECT * FROM users WHERE role='employee' ORDER BY name").fetchall()
    elif u["role"] == "admin":
        emps = conn.execute("SELECT * FROM users WHERE role='employee' AND company_id=? ORDER BY name",
                            (u["company_id"],)).fetchall()
    else:  # seller
        comp = conn.execute("SELECT * FROM companies WHERE id=?", (u["company_id"],)).fetchone()
        if comp and not comp["share_reports_with_seller"]:
            conn.close()
            return render_template("reports.html", data=[], blocked=True)
        emps = conn.execute("SELECT * FROM users WHERE role='employee' AND seller_id=? ORDER BY name",
                            (u["id"],)).fetchall()

    today = datetime.now(timezone.utc).date().isoformat()
    data = []
    for e in emps:
        secs = conn.execute("""
            SELECT COALESCE(SUM(
                (julianday(COALESCE(clock_out, last_heartbeat, clock_in)) - julianday(clock_in)) * 86400
                - idle_seconds), 0) s
            FROM work_sessions WHERE user_id=? AND substr(clock_in,1,10)=?""",
            (e["id"], today)).fetchone()["s"]
        data.append({"emp": e, "hours_today": round(max(secs, 0) / 3600, 2)})
    conn.close()
    return render_template("reports.html", data=data, blocked=False)


# ----------------------------------------------------------------------------
# agent API (desktop app authenticates with its agent_token)
# ----------------------------------------------------------------------------
def agent_user():
    token = request.headers.get("X-Agent-Token")
    if not token:
        body = request.get_json(silent=True) or request.form
        token = body.get("token")
    if not token:
        return None
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE agent_token=? AND active=1", (token,)).fetchone()
    conn.close()
    return u


@app.route("/api/agent/clock-in", methods=["POST"])
def api_clock_in():
    u = agent_user()
    if not u:
        return jsonify(error="bad token"), 401
    conn = get_db()
    open_s = conn.execute(
        "SELECT * FROM work_sessions WHERE user_id=? AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
        (u["id"],)).fetchone()
    if open_s:
        conn.close()
        return jsonify(ok=True, session_id=open_s["id"], note="already clocked in")
    conn.execute("""INSERT INTO work_sessions (user_id, company_id, clock_in, last_heartbeat)
                    VALUES (?,?,?,?)""", (u["id"], u["company_id"], now_iso(), now_iso()))
    conn.commit()
    sid = conn.execute("SELECT id FROM work_sessions ORDER BY id DESC LIMIT 1").fetchone()["id"]
    conn.close()
    return jsonify(ok=True, session_id=sid)


@app.route("/api/agent/heartbeat", methods=["POST"])
def api_heartbeat():
    u = agent_user()
    if not u:
        return jsonify(error="bad token"), 401
    body = request.get_json(silent=True) or request.form
    conn = get_db()
    open_s = conn.execute(
        "SELECT * FROM work_sessions WHERE user_id=? AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
        (u["id"],)).fetchone()
    if not open_s:
        conn.close()
        return jsonify(error="not clocked in"), 409
    conn.execute("UPDATE work_sessions SET last_heartbeat=?, current_app=?, idle_seconds=? WHERE id=?",
                 (now_iso(), (body.get("current_app") or "")[:200],
                  int(body.get("idle_seconds") or 0), open_s["id"]))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@app.route("/api/agent/clock-out", methods=["POST"])
def api_clock_out():
    u = agent_user()
    if not u:
        return jsonify(error="bad token"), 401
    conn = get_db()
    open_s = conn.execute(
        "SELECT * FROM work_sessions WHERE user_id=? AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
        (u["id"],)).fetchone()
    if open_s:
        conn.execute("UPDATE work_sessions SET clock_out=? WHERE id=?", (now_iso(), open_s["id"]))
        conn.commit()
    conn.close()
    return jsonify(ok=True)


# ----------------------------------------------------------------------------
# Mobile JSON API (bearer token in X-Auth-Token). Used by the React Native app.
# ----------------------------------------------------------------------------
import secrets as _secrets


def _issue_token(conn, user_id):
    tok = _secrets.token_urlsafe(32)
    conn.execute("INSERT INTO api_tokens (token, user_id, created_at) VALUES (?,?,?)",
                 (tok, user_id, now_iso()))
    conn.commit()
    return tok


def api_user():
    tok = request.headers.get("X-Auth-Token")
    if not tok:
        return None
    conn = get_db()
    u = conn.execute("""SELECT u.* FROM users u JOIN api_tokens t ON t.user_id = u.id
                        WHERE t.token = ? AND u.active = 1""", (tok,)).fetchone()
    conn.close()
    return u


def _user_json(u):
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"],
            "company_id": u["company_id"], "phone": u["phone"] or "",
            "photo_url": u["photo_url"] or ""}


@app.route("/api/login", methods=["POST"])
def api_login():
    body = request.get_json(silent=True) or request.form
    conn = get_db()
    u = verify_login(conn, body.get("email", ""), body.get("password", ""))
    if not u:
        conn.close()
        return jsonify(error="Wrong email or password"), 401
    tok = _issue_token(conn, u["id"])
    conn.close()
    return jsonify(token=tok, user=_user_json(u))


@app.route("/api/me")
def api_me():
    u = api_user()
    if not u:
        return jsonify(error="unauthorized"), 401
    return jsonify(user=_user_json(u))


@app.route("/api/board")
def api_board():
    u = api_user()
    if not u:
        return jsonify(error="unauthorized"), 401
    conn = get_db()
    window = (datetime.now(timezone.utc) - timedelta(seconds=app.config["ONLINE_WINDOW_SEC"])).isoformat()
    base = """SELECT u.id, u.name, u.email, c.name company_name,
                     ws.clock_in, ws.clock_out, ws.last_heartbeat, ws.current_app
              FROM users u LEFT JOIN companies c ON c.id = u.company_id
              LEFT JOIN work_sessions ws ON ws.id = (
                  SELECT id FROM work_sessions w WHERE w.user_id = u.id ORDER BY id DESC LIMIT 1)
              WHERE u.role = 'employee' """
    if u["role"] == "owner":
        rows = conn.execute(base + "ORDER BY u.name").fetchall()
    elif u["role"] == "admin":
        rows = conn.execute(base + "AND u.company_id = ? ORDER BY u.name", (u["company_id"],)).fetchall()
    elif u["role"] == "seller":
        rows = conn.execute(base + "AND u.seller_id = ? ORDER BY u.name", (u["id"],)).fetchall()
    else:
        rows = conn.execute(base + "AND u.id = ?", (u["id"],)).fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({"id": r["id"], "name": r["name"], "email": r["email"],
                    "company": r["company_name"], "current_app": r["current_app"] or "",
                    "online": bool(r["last_heartbeat"] and r["last_heartbeat"] >= window and not r["clock_out"]),
                    "clock_in": r["clock_in"] if (r["clock_in"] and not r["clock_out"]) else None})
    return jsonify(board=out)


@app.route("/api/clock", methods=["POST"])
def api_clock():
    u = api_user()
    if not u:
        return jsonify(error="unauthorized"), 401
    action = (request.get_json(silent=True) or request.form).get("action")
    conn = get_db()
    open_s = conn.execute(
        "SELECT * FROM work_sessions WHERE user_id=? AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
        (u["id"],)).fetchone()
    if action == "in" and not open_s:
        conn.execute("INSERT INTO work_sessions (user_id, company_id, clock_in, last_heartbeat) VALUES (?,?,?,?)",
                     (u["id"], u["company_id"], now_iso(), now_iso()))
    elif action == "in" and open_s:
        conn.execute("UPDATE work_sessions SET last_heartbeat=? WHERE id=?", (now_iso(), open_s["id"]))
    elif action == "out" and open_s:
        conn.execute("UPDATE work_sessions SET clock_out=? WHERE id=?", (now_iso(), open_s["id"]))
    conn.commit()
    state = conn.execute(
        "SELECT * FROM work_sessions WHERE user_id=? AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
        (u["id"],)).fetchone()
    conn.close()
    return jsonify(ok=True, clocked_in=bool(state))


@app.route("/api/reports")
def api_reports():
    u = api_user()
    if not u:
        return jsonify(error="unauthorized"), 401
    if u["role"] == "employee":
        return jsonify(error="forbidden"), 403
    conn = get_db()
    if u["role"] == "owner":
        emps = conn.execute("SELECT * FROM users WHERE role='employee' ORDER BY name").fetchall()
    elif u["role"] == "admin":
        emps = conn.execute("SELECT * FROM users WHERE role='employee' AND company_id=? ORDER BY name",
                            (u["company_id"],)).fetchall()
    else:
        comp = conn.execute("SELECT * FROM companies WHERE id=?", (u["company_id"],)).fetchone()
        if comp and not comp["share_reports_with_seller"]:
            conn.close()
            return jsonify(reports=[], blocked=True)
        emps = conn.execute("SELECT * FROM users WHERE role='employee' AND seller_id=? ORDER BY name",
                            (u["id"],)).fetchall()
    today = datetime.now(timezone.utc).date().isoformat()
    out = []
    for e in emps:
        secs = conn.execute("""SELECT COALESCE(SUM(
            (julianday(COALESCE(clock_out, last_heartbeat, clock_in)) - julianday(clock_in)) * 86400
            - idle_seconds), 0) s FROM work_sessions WHERE user_id=? AND substr(clock_in,1,10)=?""",
            (e["id"], today)).fetchone()["s"]
        out.append({"id": e["id"], "name": e["name"], "email": e["email"],
                    "hours_today": round(max(secs, 0) / 3600, 2)})
    conn.close()
    return jsonify(reports=out, blocked=False)


@app.route("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
