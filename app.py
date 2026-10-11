import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stays.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'guest');
CREATE TABLE IF NOT EXISTS rooms (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT,
  price INTEGER NOT NULL, capacity INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS reservations (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, room_id INTEGER NOT NULL,
  check_in TEXT NOT NULL, check_out TEXT NOT NULL, guests INTEGER NOT NULL,
  notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (room_id) REFERENCES rooms(id));
"""


def init_db():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM users").fetchone():
        con.executemany(
            "INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
            [("Host Admin", "admin@stay.test", generate_password_hash("admin123"), "admin"),
             ("Sample Guest", "guest@stay.test", generate_password_hash("guest123"), "guest")])
        con.executemany(
            "INSERT INTO rooms (name,description,price,capacity) VALUES (?,?,?,?)",
            [("Garden Studio", "Cozy studio with a garden view and kitchenette.", 2200, 2),
             ("Family Loft", "Two-bedroom loft with a balcony and free parking.", 3800, 5),
             ("Barkada Villa", "Whole villa with a pool, good for big groups.", 6500, 10)])
    con.commit()
    con.close()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone() if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


@app.route("/")
def index():
    rooms = db().execute("SELECT * FROM rooms").fetchall()
    return render_template("index.html", rooms=rooms)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        if not name or "@" not in email or len(pw) < 6:
            flash("Enter a name, a valid email, and a password of 6+ characters.", "error")
        elif db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash("That email is already registered.", "error")
        else:
            db().execute("INSERT INTO users (name,email,password_hash) VALUES (?,?,?)",
                         (name, email, generate_password_hash(pw)))
            db().commit()
            flash("Account created. Please log in.", "ok")
            return redirect(url_for("login"))
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"] = user["id"]
            return redirect(url_for("reservations"))
        flash("Wrong email or password.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- Reservations (CRUD) ----------

def get_reservation(rid):
    r = db().execute("SELECT * FROM reservations WHERE id=?", (rid,)).fetchone()
    if r is None:
        abort(404)
    if g.user["role"] != "admin" and r["user_id"] != g.user["id"]:
        abort(403)  # guests may only touch their own bookings
    return r


def validate(form, rid=None):
    errors, data = [], {}
    room = db().execute("SELECT * FROM rooms WHERE id=?", (form.get("room_id", ""),)).fetchone()
    if not room:
        errors.append("Choose a room.")
    try:
        cin = date.fromisoformat(form.get("check_in", ""))
        cout = date.fromisoformat(form.get("check_out", ""))
        if cin < date.today():
            errors.append("Check-in cannot be in the past.")
        if cout <= cin:
            errors.append("Check-out must be after check-in.")
    except ValueError:
        errors.append("Enter valid check-in and check-out dates.")
        cin = cout = None
    try:
        guests = int(form.get("guests", ""))
        if guests < 1 or (room and guests > room["capacity"]):
            errors.append("Guests must be between 1 and the room capacity.")
    except ValueError:
        errors.append("Guests must be a number.")
        guests = None
    if room and cin and cout and not errors:
        clash = db().execute(
            "SELECT 1 FROM reservations WHERE room_id=? AND id!=? AND check_in<? AND check_out>?",
            (room["id"], rid or 0, cout.isoformat(), cin.isoformat())).fetchone()
        if clash:
            errors.append("That room is already booked for those dates.")
    if not errors:
        data = dict(room_id=room["id"], check_in=cin.isoformat(), check_out=cout.isoformat(),
                    guests=guests, notes=form.get("notes", "").strip()[:300])
    return data, errors


@app.route("/reservations")
@login_required
def reservations():
    sql = ("SELECT r.*, rooms.name AS room, rooms.price, users.name AS guest "
           "FROM reservations r JOIN rooms ON rooms.id=r.room_id "
           "JOIN users ON users.id=r.user_id ")
    if g.user["role"] == "admin":
        rows = db().execute(sql + "ORDER BY r.check_in").fetchall()
    else:
        rows = db().execute(sql + "WHERE r.user_id=? ORDER BY r.check_in", (g.user["id"],)).fetchall()
    items = []
    for r in rows:
        nights = (date.fromisoformat(r["check_out"]) - date.fromisoformat(r["check_in"])).days
        items.append((r, nights, nights * r["price"]))
    return render_template("reservations.html", items=items)


@app.route("/reservations/new", methods=["GET", "POST"])
@login_required
def create():
    rooms = db().execute("SELECT * FROM rooms").fetchall()
    if request.method == "POST":
        data, errors = validate(request.form)
        if not errors:
            db().execute("INSERT INTO reservations (user_id,room_id,check_in,check_out,guests,notes) "
                         "VALUES (?,?,?,?,?,?)",
                         (g.user["id"], data["room_id"], data["check_in"], data["check_out"],
                          data["guests"], data["notes"]))
            db().commit()
            flash("Reservation created.", "ok")
            return redirect(url_for("reservations"))
        for e in errors:
            flash(e, "error")
    return render_template("form.html", rooms=rooms, r=request.form, title="Book a stay")


@app.route("/reservations/<int:rid>/edit", methods=["GET", "POST"])
@login_required
def edit(rid):
    res = get_reservation(rid)
    rooms = db().execute("SELECT * FROM rooms").fetchall()
    if request.method == "POST":
        data, errors = validate(request.form, rid)
        if not errors:
            db().execute("UPDATE reservations SET room_id=?,check_in=?,check_out=?,guests=?,notes=? "
                         "WHERE id=?", (data["room_id"], data["check_in"], data["check_out"],
                                        data["guests"], data["notes"], rid))
            db().commit()
            flash("Reservation updated.", "ok")
            return redirect(url_for("reservations"))
        for e in errors:
            flash(e, "error")
        res = request.form
    return render_template("form.html", rooms=rooms, r=res, title="Edit reservation")


@app.route("/reservations/<int:rid>/delete", methods=["POST"])
@login_required
def delete(rid):
    get_reservation(rid)
    db().execute("DELETE FROM reservations WHERE id=?", (rid,))
    db().commit()
    flash("Reservation deleted.", "ok")
    return redirect(url_for("reservations"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
