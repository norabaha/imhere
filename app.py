# -*- coding: utf-8 -*-

# app.py
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template
import locale
import csv
import logging

ADD_TEST_USERS = False

# Sett norsk språkdrakt for datoer
try:
    locale.setlocale(locale.LC_TIME, "nb_NO.utf8")   # Linux/Mac
except:
    try:
        locale.setlocale(locale.LC_TIME, "Norwegian_Norway.1252")  # Windows
    except:
        print("Norsk locale ikke tilgjengelig, faller tilbake til engelsk.")

app = Flask(__name__)

DB_NAME = "attendance.db"

def add_user(tag, name):
    """Add a user to the users table if not already present."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (tag, name) VALUES (?, ?)", (tag, name))
    conn.commit()
    conn.close()
    
def add_attendance(tag, timestamp=None):
    """Add an attendance record for a given tag and optional timestamp."""
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO attendance (tag, timestamp) VALUES (?, ?)", (tag, timestamp))
    conn.commit()
    conn.close()

def import_users_from_file(filename):
    """Import users from a text or CSV file into the users table."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    with open(filename, encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue  # skip invalid lines
            tag, name = row[0].strip(), row[1].strip()
            if tag and name:
                c.execute("INSERT OR IGNORE INTO users (tag, name) VALUES (?, ?)", (tag, name))
    conn.commit()
    conn.close()

def get_name(tag):
    """Fetch the name for a given tag from the users table, or return 'Unknown'."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name FROM users WHERE tag = ?", (tag,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else "Unknown"

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
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
        users = {
        "1111111111": "Alice",
        "2222222222": "Bob",
        "3333333333": "Charlie"
        }
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

    # Import users from file
    import_users_from_file("users.csv")


# --- Flask Route ---
@app.route('/data')
def get_data():
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
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
# def rfid_listener():
#     print("RFID listener started. Type tags manually to simulate scans, finish with ENTER.")
#     while True:
#         tag = input("Scan RFID tag: ").strip()
#         if not tag:
#             continue
#         now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         add_attendance(tag, now)
#         name = users.get(tag, "Unknown")
#         print(f"[{now}] {name} ({tag}) scanned.")

def terminal_menu():
    while True:
        print("Welcome to the RFID system!")
        print("1: Start RFID listener (scan tags)")
        print("2: Add new user")
        # print("3: Exit")

        choice = input("Choose an option (1-3): ").strip()
        if choice == "1":
            print("RFID listener started. Enter tag manually, press ENTER to register.")
            while True:
                tag = input("Scan RFID tag (or 'q' to quit to menu): ").strip()
                if tag.lower() == 'q':
                    print("Exiting RFID listener.")
                    break
                if not tag:
                    continue
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                add_attendance(tag, now)
                name = get_name(tag)
                print(f"[{now}] {name} ({tag}) registered.")

        elif choice == "2":
            tag = input("Enter RFID tag: ").strip()
            name = input("Enter name: ").strip()
            if tag and name:
                add_user(tag, name)
                print(f"User '{name}' with tag '{tag}' added.")
            else:
                print("Tag and name must be filled out.")

        # elif choice == "3":
        #     print("Exiting program.")
        #     break
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    # Suppress Flask debug logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    init_db()

    # # Start RFID listener in background thread
    # listener_thread = threading.Thread(target=rfid_listener, daemon=True)
    # listener_thread.start()

    # Start terminal menu in background thread
    menu_thread = threading.Thread(target=terminal_menu, daemon=True)
    menu_thread.start()

    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
