# -*- coding: utf-8 -*-

# app.py
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template
import locale

ADD_TEST_USERS = False

# Sett norsk språkdrakt for datoer
try:
    locale.setlocale(locale.LC_TIME, "nb_NO.utf8")   # Linux/Mac
except:
    try:
        locale.setlocale(locale.LC_TIME, "Norwegian_Norway.1252")  # Windows
    except:
        print("⚠️ Norsk locale ikke tilgjengelig, faller tilbake til engelsk.")

app = Flask(__name__)

# --- TEST users ---
users = {
    "1111111111": "Alice",
    "2222222222": "Bob",
    "3333333333": "Charlie"
}

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    # Drop tables if they exist
    # c.execute("DROP TABLE IF EXISTS attendance")
    # c.execute("DROP TABLE IF EXISTS users")

    # Attendance table
    c.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT,
        timestamp TEXT
    )
    """)

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        tag TEXT PRIMARY KEY,
        name TEXT
    )
    """)

    if ADD_TEST_USERS:
        # Insert TEST users if not already present
        for tag, name in users.items():
            c.execute("INSERT OR IGNORE INTO users (tag, name) VALUES (?, ?)", (tag, name))
            # Add test attendance records for the past few days
            test_tags = list(users.keys())
            now = datetime.now()
            for i in range(5):
                day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                for tag in test_tags:
                    timestamp = f"{day} 09:00:00"
                    c.execute("INSERT INTO attendance (tag, timestamp) VALUES (?, ?)", (tag, timestamp))
    conn.commit()
    conn.close()


# --- Flask Route ---
@app.route('/data')
def get_data():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Join attendance with users table to get names
    c.execute("""
        SELECT a.id, a.tag, u.name, a.timestamp
        FROM attendance a
        LEFT JOIN users u ON a.tag = u.tag
        ORDER BY a.timestamp DESC
    """)
    rows = c.fetchall()
    data = [dict(row) for row in rows]
    conn.close()
    return jsonify(data)

@app.route('/weekly')
def weekly_attendance():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    week_days = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    week_data = {day: {"day_name": "", "records": []} for day in week_days}

    c.execute("""
        SELECT date(a.timestamp) AS day, a.tag, u.name
        FROM attendance a
        LEFT JOIN users u ON a.tag = u.tag
        WHERE date(a.timestamp) >= ?
        GROUP BY day, a.tag
        ORDER BY day ASC
    """, (week_days[0],))
    
    for day in week_days:
        day_date = datetime.strptime(day, "%Y-%m-%d").date()
        week_data[day]["day_name"] = day_date.strftime("%a")  # Norwegian if locale is set

    rows = c.fetchall()
    for row in rows:
        day = row['day']
        if day in week_data:
            week_data[day]["records"].append({"tag": row["tag"], "name": row["name"] or "Unknown"})

    conn.close()
    return jsonify(week_data)

@app.route('/stats')
def stats():
    conn = sqlite3.connect("attendance.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())  # Monday=0
    week_days = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    # Earliest attendance each day
    c.execute("""
        SELECT date(a.timestamp) AS day, MIN(a.timestamp) AS first_scan, u.name, a.tag
        FROM attendance a
        LEFT JOIN users u ON a.tag = u.tag
        WHERE date(a.timestamp) >= ?
        GROUP BY day
        ORDER BY day ASC
    """, (week_days[0],))
    earliest_rows = c.fetchall()

    earliest_by_day = {}
    for row in earliest_rows:
        day_date = datetime.strptime(row["day"], "%Y-%m-%d").date()
        day_name = day_date.strftime("%A")  # Blir norsk hvis locale er satt
        earliest_by_day[day_name] = {
            "time": row["first_scan"][11:16],
            "name": row["name"] or "Ukjent",
            "tag": row["tag"]
        }

    # Attendance count per user (number of unique days present this week)
    c.execute("""
        SELECT u.name, a.tag, COUNT(DISTINCT date(a.timestamp)) as days_present
        FROM attendance a
        LEFT JOIN users u ON a.tag = u.tag
        WHERE date(a.timestamp) >= ?
        GROUP BY a.tag
    """, (week_days[0],))
    attendance_rows = c.fetchall()

    perfect_attendance = []
    for row in attendance_rows:
        if row["days_present"] == today.weekday() + 1:  # e.g. Wed = 3 days so far
            perfect_attendance.append(row["name"] or "Ukjent")

    conn.close()

    return jsonify({
        "earliest_by_day": earliest_by_day,
        "perfect_attendance": perfect_attendance
    })


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/list-view')
def list_view():
    return render_template('list.html')

@app.route('/weekly-view')
def weekly_view():
    return render_template('weekly.html')



# --- Background RFID Simulation ---
def rfid_listener():
    print("RFID listener started. Type tags manually to simulate scans.")
    while True:
        tag = input("Scan RFID tag: ").strip()
        if not tag:
            continue
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect("attendance.db")
        c = conn.cursor()
        c.execute("INSERT INTO attendance (tag, timestamp) VALUES (?, ?)", (tag, now))
        conn.commit()
        conn.close()

        name = users.get(tag, "Unknown")
        print(f"[{now}] {name} ({tag}) scanned.")


if __name__ == "__main__":
    init_db()

    # Start RFID listener in background thread
    listener_thread = threading.Thread(target=rfid_listener, daemon=True)
    listener_thread.start()

    # Run Flask app
    app.run(debug=True)
