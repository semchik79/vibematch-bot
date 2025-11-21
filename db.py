import sqlite3

def init_db():
    conn = sqlite3.connect("db.sqlite3")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        age INTEGER,
        city TEXT,
        bio TEXT,
        photo_id TEXT,
        step TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_from INTEGER,
        user_to INTEGER
    )
    """)

    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect("db.sqlite3")
