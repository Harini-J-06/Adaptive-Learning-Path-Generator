import sqlite3
conn = sqlite3.connect("learning.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM progress")
print(cursor.fetchall())
cursor.execute("ALTER TABLE users ADD COLUMN goal TEXT")
conn.commit()
conn.close()
print("Goal column added successfully!")
