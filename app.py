from flask import Flask, render_template, request, redirect, url_for, session, abort, send_file, jsonify
import csv, io, os
DATABASE= "learning.db"
from database import init_db, get_db, mark_module_complete
import sqlite3
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
init_db()

@app.route("/")
def home():
    username="Harini"
    project_name="Adaptive Learning Path Generator"
    return render_template("home_page.html",username=username,project_name=project_name)

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not username or not email or not password:
            return "Please provide name, email and password", 400

        conn = get_db()
        try:
            existing = conn.execute("SELECT user_id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                conn.close()
                return "Email already registered. Please login.", 400

            cur = conn.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, password)
            )
            conn.commit()
            last_id = cur.lastrowid
            print(f"[SIGNUP] Inserted user_id={last_id} username={username} email={email}")
            conn.close()
            return redirect(url_for("login"))
        except Exception as e:
            print("[SIGNUP] Error inserting user:", e)
            try:
                conn.rollback()
                conn.close()
            except:
                pass
            return "Internal error during signup. Check terminal.", 500
    return render_template("sign_up.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session["user_id"] = user["user_id"] 
            goal= user["goal"]
            session["goal"]= goal
            #session["skill_level"] = user["skill_level"] if "skill_level" in user.keys() else None
            #session["study_hours"] = user["study_hours"]
            if not goal:
                return redirect(url_for("assessment"))
            else:
                return redirect(url_for("generate_path"))
        else:
            return "Invalid login"
    return render_template("login.html")

@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")

@app.route("/assessment", methods=["GET","POST"])
def assessment():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        goal = request.form.get("goal")
        skill_level = request.form.get("skill_level")
        study_hours = request.form.get("study_hours")
        # save choices to session
        session["goal"] = goal
        session.pop("modules", None)
        session["skill_level"] = skill_level
        session["study_hours"] = study_hours
        user_id= session["user_id"]
        conn= get_db()
        conn.execute("UPDATE users SET goal=? WHERE user_id=?", (goal, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for("generate_path"))
    return render_template("assessment.html")

@app.route("/learning_path")
def learning_path():
    # require login
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db()
    try:
        user_row = conn.execute("SELECT goal FROM users WHERE user_id=?", (user_id,)).fetchone()
        db_goal = user_row["goal"] if user_row and "goal" in user_row.keys() else None
    except Exception:
        db_goal = None
    goal = (db_goal or session.get("goal") or "").strip()
    goal_norm = goal.lower()

    if goal_norm == "web development":
        canonical_modules = [
            {"module_id": 1, "title": "HTML Fundamentals", "description": "Learn the structure of web pages, semantic tags, and basic layouts.", "hours": 6},
            {"module_id": 2, "title": "CSS Fundamentals", "description": "Style your pages with colors, layout and box-model.", "hours": 5},
            {"module_id": 3, "title": "JavaScript Basics", "description": "Understand variables, functions and simple DOM interactions.", "hours": 7},
            {"module_id": 4, "title": "Mini Project", "description": "Build a responsive website using HTML, CSS, and JavaScript.", "hours": 10},
        ]
    else:
        canonical_modules = [
            {"module_id": 1, "title": "Python Fundamentals", "description": "Syntax, variables, data types and loops.", "hours": 3},
            {"module_id": 2, "title": "Functions in python", "description": "Learn how to create reusable code using Python functions.", "hours": 4},
            {"module_id": 3, "title": "OOP Basics", "description": "Classes, objects, and inheritance.", "hours": 4},
            {"module_id": 4, "title": "Mini Project", "description": "Build a Python-based mini project using functions and OOP.", "hours": 10},
        ]
    try:
        conn.execute("DELETE FROM modules")
        insert_rows = [(m["module_id"], m["title"], m.get("description",""), m.get("hours",0)) for m in canonical_modules]
        conn.executemany("INSERT INTO modules (module_id, title, description, hours) VALUES (?, ?, ?, ?)", insert_rows)
        conn.commit()
    except Exception as e:
        print("Warning: could not persist modules table:", e)
    try:
        completed_rows = conn.execute("SELECT module_id FROM progress WHERE user_id=? AND completed=1", (user_id,)).fetchall()
        completed_modules = [int(r["module_id"]) for r in completed_rows]
        session["completed_modules"]= completed_modules
        session.modified= True
    except Exception:
        completed_modules = []

    conn.close()
    return render_template("learning_path.html",
         modules=canonical_modules, completed_modules=completed_modules, goal=goal or "None",
        skill_level=session.get("skill_level", "Beginner"), study_hours=session.get("study_hours", "2"))

@app.route("/progress")
def progress():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id= session["user_id"]
    conn= get_db()
    completed_rows= conn.execute("SELECT module_id, score FROM progress WHERE user_id=? AND completed=1", (user_id,)).fetchall()
    completed= [int(row["module_id"]) for row in completed_rows]
    total_row= conn.execute("SELECT COUNT(*) AS total FROM modules").fetchone()
    total= total_row["total"] if total_row else 0
    scores= [int(row["score"]) for row in completed_rows if row["score"] is not None]
    if scores:
        average_score= int(sum(scores) / len(scores))
    else:
        average_score= 0
        conn.close()
    if total>0:
        progress_percent=int((len(completed)/total)*100)
    else:
        progress_percent=0
    return render_template("progress.html", completed=completed, total=total, progress_percent=progress_percent,
        current_level= session.get("skill_level", "Beginner"), average_score=average_score)

@app.route("/learn_module/<int:module_id>")
def learn_module(module_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id= session["user_id"]
    conn=get_db()
    module_row=conn.execute("SELECT module_id, title, description, hours FROM modules WHERE module_id=?", (module_id,)).fetchone()
    progress=conn.execute(
        "SELECT score, completed FROM progress WHERE user_id=? AND module_id=?", (user_id, module_id)).fetchone()
    conn.close()
    if not module_row:
        return "Module not found", 404
    session_modules = session.get("modules", [])
    session_module = next((m for m in session_modules if int(m.get("id", m.get("module_id", 0))) == module_id), None)
    # build a combined module dict for template:
    module = {
        "id": module_row["module_id"],
        "module_id": module_row["module_id"],
        "title": module_row["title"],
        "description": module_row["description"],
        "hours": module_row["hours"],
        "video_url": (session_module.get("video_url") if session_module else ""),
        "questions": (session_module.get("questions") if session_module else [])
    }
    progress_percentage= progress["score"] if progress else 0
    is_completed=progress["completed"] if progress else 0
    practice= session.pop("last_practice_result", None)
    return render_template("learn_module.html", module=module, progress_percentage=progress_percentage, 
        is_completed=is_completed, practice=practice)

@app.route("/generate_path", methods=["GET","POST"])
def generate_path():
    goal = session.get("goal")
    skill_level = session.get("skill_level")
    study_hours = session.get("study_hours")
    session["goal"] = goal
    session.pop("modules", None)
    session["skill_level"] = skill_level
    session["study_hours"] = study_hours
    if "user_id" in session and goal:
        try:
            conn = get_db()
            conn.execute("UPDATE users SET goal=? WHERE user_id=?", (goal, session["user_id"]))
            conn.commit()
            conn.close()
        except Exception as e:
            print("Failed to update user goal in generate_path:", e)
    if goal =="Web Development":
          session_modules = [
              {"id": 1, "title": "HTML Fundamentals", "hours": 6,
             "description": "Learn the structure of web pages, semantic tags, and basic layouts.",
             "video_url": "https://www.youtube.com/embed/HD13eq_Pmp8", "questions": [
                 {"text":"What does HTML stands for?", "options":{"A":"Hyper Text Markup Language",
                    "B":"High Text Machine Language", "C":"Hyperlinks Text Mark Language"}, "answer":"A"},
                 {"text":"Which tag is used for the largest heading?", "options":{"A":"h6",
                    "B":"head", "C":"h1"}, "answer":"C"}]},
              {"id": 2, "title": "CSS Fundamentals", "hours": 5,
             "description": "Style your pages with colors, layout and box-model.",
             "video_url": "https://www.youtube.com/embed/wRNinF7YQqQ", "questions": [
                 {"text":"Which property is used to change text color?", "options":{"A":"font-color",
                    "B":"color", "C":"text-color"}, "answer":"B"},
                 {"text":"Which CSS property controls the box model's inner spacing?", "options":{"A":"margin",
                    "B":"border", "C":"padding"}, "answer":"C"}]},
              {"id": 3, "title": "JavaScript Basics", "hours": 7,
             "description": "Understand variables, functions and simple DOM interactions.",
             "video_url": "https://www.youtube.com/embed/hdI2bqOjy3c", "questions": [
                 {"text":"Which keyword declares a variable in modern JS?", "options":{"A":"let",
                    "B":"var", "C":"dim"}, "answer":"A"},
                 {"text":"Which method logs to console?", "options":{"A":"print()",
                    "B":"console.log()", "C":"echo()"}, "answer":"B"}]},
              {"id": 4, "title": "Mini Project", "hours": 10,
             "description": "Build a responsive website using HTML, CSS, and JavaScript.",
             "video_url": "https://www.youtube.com/embed/JkeyKeK3V24", "questions": [] }
        ]
            
    else:
            session_modules = [
                {"id": 1, "title": "Python Fundamentals", "hours": 3,
                 "description": "Syntax, variables, data types and loops.", 
                 "video_url":"https://www.youtube.com/embed/kqtD5dpn9C8", "questions": [
                 {"text":"Which symbol begins a comment in Python?", "options":{"A":"#",
                    "B":"//", "C":"--"}, "answer":"A"},
                 {"text":"Which is a Python list literal?", "options":{"A":"{1,2}",
                    "B":"[1,2]", "C":"(1,2)"}, "answer":"B"}] },
                {"id": 2, "title": "Functions in python", "hours": 4,
                 "description":"Learn how to create reusable code using Python functions.",
                  "video_url": "https://www.youtube.com/embed/u-OmVr_fT4s", "questions": [
                 {"text":"Which keyword is used to define a functions in Python?", "options":{"A":"function",
                    "B":"func", "C":"def"}, "answer":"C"},
                 {"text":"What is the purpose of the return statement in a function?", "options":{"A":"Stop the program",
                    "B":"Send a value back to where the function was called", "C":"Print output"}, "answer":"B"}] },
                {"id": 3, "title": "OOP Basics", "hours": 4,
                 "description":"Classes, objects, and inheritance.", 
                  "video_url": "https://www.youtube.com/embed/IbMDCwVm63M", "questions": [
                 {"text":"What keyword is used to create a class?", "options":{"A":"class",
                    "B":"def", "C":"object"}, "answer":"A"},
                 {"text":"Which statement imports a module?", "options":{"A":"include",
                    "B":"import", "C":"input"}, "answer":"B"}] },
                {"id":4, "title":"Mini Project", "hours":10, 
                 "description": "Build a Python-based mini project using functions and OOP.", 
                  "video_url": "https://www.youtube.com/embed/4wGuB3oAKc4", "questions": [] }
            ]
    conn = get_db()
    conn.execute("DELETE FROM modules")
    insert_rows = [(m["id"], m["title"], m.get("description",""), m.get("hours",0)) for m in session_modules]
    conn.executemany("INSERT INTO modules (module_id, title, description, hours) VALUES (?, ?, ?, ?)", insert_rows)
    conn.commit()
    conn.close()
    session["modules"]= session_modules
    session["completed_modules"]=[]
    session["scores"]={}
    return redirect(url_for("learning_path"))

@app.route("/complete_module/<int:module_id>", methods=["POST"])
def complete_module(module_id):
    modules= session.get("modules", [])
    module= next((m for m in modules if int(m["id"])==module_id), None)
    if not module:
        return "Module not found", 404
    completed= session.get("completed_modules", [])
    completed = [int(x) for x in completed]
    unlocked= False
    if module_id==1:
        unlocked= True
    elif (module_id-1) in completed:
        unlocked= True
    if not unlocked:
        return redirect(url_for("learning_path"))
    if module_id not in completed:
        completed.append(module_id)
    session["completed_modules"] = completed
    session.modified= True
    conn= get_db()
    conn.execute("INSERT OR REPLACE INTO progress(user_id, module_id, score, completed) VALUES(?,?,?,?)",
        (session["user_id"], module_id, 100, 1))
    conn.commit()
    conn.close()
    sync_completed_modules()
    print("Completed modules:", session.get("completed_modules", []))
    return redirect(url_for("progress"))

def sync_completed_modules():
    if "user_id" not in session:
        return
    conn = get_db()
    rows = conn.execute(
        "SELECT module_id FROM progress WHERE user_id=? AND completed=1",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    session["completed_modules"] = [int(r["module_id"]) for r in rows]
    session.modified = True

@app.route("/submit_practice/<int:module_id>", methods=["POST"])
def submit_practice(module_id):
    modules = session.get("modules", [])
    module = next((m for m in modules if m["id"] == module_id), None)
    if not module:
        return "Module not found", 404
    conn = get_db()
    completed = [int(r["module_id"]) for r in conn.execute("SELECT module_id FROM progress WHERE user_id=? AND completed=1",
    (session["user_id"],)).fetchall()]
    conn.close()
    if not(module_id==1 or (module_id-1) in completed):
        return redirect(url_for("learning_path"))
    questions= module.get("questions", [])
    total_q= len(questions)
    if total_q == 0:
        session["last_practice_result"] = {
            "module": module_id,
            "score": 0,
            "passed": False,
            "message": "No practice is configured for this module."
        }
        return redirect(url_for("learn_module", module_id=module_id))
    # calculate score
    score_count = 0
    for idx, q in enumerate(questions, start=1):
        user_ans = request.form.get(f"q{idx}", "")
        correct= q.get("answer")
        if user_ans == correct:
            score_count += 1
    percent = int((score_count / total_q) * 100)
    scores = session.get("scores", {})
    scores[str(module_id)] = percent
    session["scores"] = scores
    passed = percent >= 50 
    # store feedback to show on learn_module page
    session["last_practice_result"] = {
        "module": module_id,
        "score": percent,
        "passed": passed,
        "message": f"You scored {percent}%. {'Passed' if passed else 'Not passed'}."
    }
    if passed:
        user_id= session["user_id"]
        mark_module_complete(user_id, module_id, percent)
        sync_completed_modules()
        if module_id not in completed:
            completed.append(module_id)
            session["completed_modules"]=completed
        return redirect(url_for("progress"))
    return redirect(url_for("learn_module", module_id=module_id))

def get_progress(user_id, goal_id):
    conn = get_db()
    progress = conn.execute(
        "SELECT * FROM progress WHERE user_id=? AND goal_id=?",
        (user_id, goal_id)
    ).fetchone()
    conn.close()
    return progress

@app.route("/admin")
def admin_dashboard():
    # Optional: restrict admin access (uncomment to enable)
    # if "user_id" not in session or session["user_id"] != 1:
    #     abort(403)
    q_text = request.args.get("q", "").strip()  # search text
    conn = get_db()
    # Base query (aggregates progress per user)
    base_sql = """
    SELECT
      u.user_id,
      u.username,
      u.email,
      COALESCE(u.goal, '') AS goal,
      COALESCE(SUM(CASE WHEN p.completed=1 THEN 1 ELSE 0 END), 0) AS completed_count,
      (SELECT COUNT(*) FROM modules) AS total_modules,
      ROUND(
        CASE
          WHEN (SELECT COUNT(*) FROM modules) = 0 THEN 0
          ELSE 100.0 * COALESCE(SUM(CASE WHEN p.completed=1 THEN 1 ELSE 0 END), 0) / (SELECT COUNT(*) FROM modules)
        END, 0
      ) AS progress_percent,
      COALESCE(ROUND(AVG(p.score)), 0) as avg_score
    FROM users u
    LEFT JOIN progress p ON p.user_id = u.user_id
    """

    params = []
    if q_text:
        # search in username, email, or goal
        base_sql += " WHERE u.username LIKE ? OR u.email LIKE ? OR u.goal LIKE ? "
        like = f"%{q_text}%"
        params.extend([like, like, like])

    base_sql += """
    GROUP BY u.user_id, u.username, u.email, u.goal
    ORDER BY u.user_id;
    """

    rows = conn.execute(base_sql, params).fetchall()
    conn.close()

    return render_template("admin.html", rows=rows, q=q_text)


@app.route("/admin/export")
def admin_export_csv():
    q_text = request.args.get("q", "").strip()
    conn = get_db()

    base_sql = """
    SELECT
      u.user_id,
      u.username,
      u.email,
      COALESCE(u.goal, '') AS goal,
      COALESCE(SUM(CASE WHEN p.completed=1 THEN 1 ELSE 0 END), 0) AS completed_count,
      (SELECT COUNT(*) FROM modules) AS total_modules,
      ROUND(
        CASE
          WHEN (SELECT COUNT(*) FROM modules) = 0 THEN 0
          ELSE 100.0 * COALESCE(SUM(CASE WHEN p.completed=1 THEN 1 ELSE 0 END), 0) / (SELECT COUNT(*) FROM modules)
        END, 0
      ) AS progress_percent,
      COALESCE(ROUND(AVG(p.score)), 0) as avg_score
    FROM users u
    LEFT JOIN progress p ON p.user_id = u.user_id
    """

    params = []
    if q_text:
        base_sql += " WHERE u.username LIKE ? OR u.email LIKE ? OR u.goal LIKE ? "
        like = f"%{q_text}%"
        params.extend([like, like, like])

    base_sql += """
    GROUP BY u.user_id, u.username, u.email, u.goal
    ORDER BY u.user_id;
    """
    rows = conn.execute(base_sql, params).fetchall()
    conn.close()
    # write CSV to memory
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(["user_id", "username", "email", "goal", "completed_count", "total_modules", "progress_percent", "avg_score"])
    for r in rows:
        writer.writerow([
            r["user_id"], r["username"], r["email"], r["goal"],
            r["completed_count"], r["total_modules"], r["progress_percent"], r["avg_score"]
        ])

    mem = io.BytesIO()
    mem.write(si.getvalue().encode("utf-8"))
    mem.seek(0)
    si.close()
    return send_file(mem, as_attachment=True, download_name="admin_export.csv", mimetype="text/csv")

@app.route("/debug/users")
def debug_users():
    """Return a quick JSON list of users (for debugging)."""
    conn = get_db()
    rows = conn.execute("SELECT user_id, username, email, password, COALESCE(goal, '') AS goal FROM users").fetchall()
    conn.close()
    users = [{"user_id": r["user_id"], "username": r["username"], "email": r["email"], "password": r["password"], "goal": r["goal"]} for r in rows]
    return jsonify(users)


@app.route("/debug/pwd")
def debug_pwd():
    """Show the current working directory so we know where learning.db lives."""
    return {"cwd": os.getcwd(), "db_path": os.path.abspath(DATABASE) if 'DATABASE' in globals() else "unknown"}

@app.route("/reset")
def reset():
    session.clear()
    return "Session cleared!"

if __name__=="__main__":
    app.run(debug=True)
