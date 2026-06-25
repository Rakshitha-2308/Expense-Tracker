from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import date, timedelta

app = Flask(__name__)

# ─── DATABASE ─────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect("expense_tracker.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        date TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS savings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        week TEXT NOT NULL,
        date TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()

def get_week_label(d=None):
    if d is None:
        d = date.today()
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"

def get_week_range(week_label):
    year, w = week_label.split("-W")
    year, w = int(year), int(w)
    jan4 = date(year, 1, 4)
    start = jan4 + timedelta(weeks=(w - jan4.isocalendar()[1]))
    start = start - timedelta(days=start.weekday())
    end = start + timedelta(days=6)
    return start, end

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

# ── Expenses
@app.route("/api/expenses")
def get_expenses():
    keyword   = request.args.get("keyword", "").strip()
    from_date = request.args.get("from_date", "").strip()
    to_date   = request.args.get("to_date", "").strip()

    conn = sqlite3.connect("expense_tracker.db")
    c = conn.cursor()
    query = "SELECT * FROM expenses WHERE 1=1"
    params = []
    if keyword:
        query += " AND LOWER(name) LIKE ?"
        params.append(f"%{keyword.lower()}%")
    if from_date:
        query += " AND date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND date <= ?"
        params.append(to_date)
    query += " ORDER BY date DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "name": r[1], "amount": r[2], "date": r[3]} for r in rows])

@app.route("/api/expenses/add", methods=["POST"])
def add_expense():
    data = request.json
    conn = sqlite3.connect("expense_tracker.db")
    c = conn.cursor()
    c.execute("INSERT INTO expenses (name, amount, date) VALUES (?,?,?)",
              (data["name"], float(data["amount"]), str(date.today())))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/expenses/delete/<int:exp_id>", methods=["DELETE"])
def delete_expense(exp_id):
    conn = sqlite3.connect("expense_tracker.db")
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id=?", (exp_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ── Calendar
@app.route("/api/calendar/<int:year>/<int:month>")
def get_calendar_data(year, month):
    conn = sqlite3.connect("expense_tracker.db")
    c = conn.cursor()
    c.execute("""SELECT date, SUM(amount) FROM expenses
                 WHERE strftime('%m',date)=? AND strftime('%Y',date)=?
                 GROUP BY date""",
              (f"{month:02d}", str(year)))
    rows = c.fetchall()
    conn.close()
    return jsonify([{"date": r[0], "total": r[1]} for r in rows])

@app.route("/api/calendar/day/<string:day>")
def get_day_expenses(day):
    conn = sqlite3.connect("expense_tracker.db")
    c = conn.cursor()
    c.execute("SELECT * FROM expenses WHERE date=? ORDER BY id DESC", (day,))
    rows = c.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "name": r[1], "amount": r[2], "date": r[3]} for r in rows])

# ── Savings
@app.route("/api/savings")
def get_savings():
    conn = sqlite3.connect("expense_tracker.db")
    c = conn.cursor()
    c.execute("SELECT * FROM savings ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    total = sum(r[1] for r in rows)
    return jsonify({
        "savings": [{"id": r[0], "amount": r[1], "week": r[2], "date": r[3]} for r in rows],
        "total": total
    })

@app.route("/api/savings/add", methods=["POST"])
def add_saving():
    data = request.json
    week = get_week_label()
    conn = sqlite3.connect("expense_tracker.db")
    c = conn.cursor()
    c.execute("INSERT INTO savings (amount, week, date) VALUES (?,?,?)",
              (float(data["amount"]), week, str(date.today())))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "week": week})

@app.route("/api/savings/week_check")
def week_check():
    week  = get_week_label()
    today = date.today()
    conn  = sqlite3.connect("expense_tracker.db")
    c     = conn.cursor()
    c.execute("SELECT COUNT(*) FROM savings WHERE week=?", (week,))
    exists = c.fetchone()[0] > 0
    start, end = get_week_range(week)
    c.execute("SELECT SUM(amount) FROM expenses WHERE date >= ? AND date <= ?",
              (str(start), str(end)))
    val = c.fetchone()[0] or 0
    conn.close()
    return jsonify({
        "is_sunday":   today.weekday() == 6,
        "week_exists": exists,
        "week_total":  val,
        "week_label":  week
    })

# ─── RUN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
