import sqlite3

DATABASE = "learning.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        goal TEXT
    )
    """)

    # Progress table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        module_id INTEGER,
        score INTEGER,
        completed INTEGER DEFAULT 0
    )
    """)

    # Modules table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS modules (
        module_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        hours INTEGER
    )
    """)
    conn.commit()
    conn.close()

# get completed modules
def get_completed_modules():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT module_id FROM progress WHERE completed = 1
        """)
    rows = cursor.fetchall()
    conn.close()
    return [row["module_id"] for row in rows]

def mark_module_complete(user_id,module_id,score):
    conn=get_db()
    cursor=conn.cursor()
    cursor.execute("""
        SELECT * FROM progress WHERE user_id=? AND module_id=?
        """, (user_id, module_id))
    existing= cursor.fetchone()
    if existing:
        cursor.execute("""
            UPDATE progress SET score=?, completed=1 WHERE user_id=? AND module_id=?
            """, (score, user_id, module_id))
    else:
        cursor.execute("""
            INSERT INTO progress (user_id, module_id, score, completed) VALUES(?,?,?,1)
            """, (user_id, module_id, score))
    conn.commit()
    conn.close()
        