from flask import Flask, request, redirect, flash, render_template, session, jsonify
import sqlite3
import os
import random
import uuid
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from ai_service import analyze_waste_image, ask_sustainability_ai

ROOT = Path(__file__).resolve().parent
(ROOT / "instance").mkdir(exist_ok=True)
(ROOT / "static" / "uploads").mkdir(parents=True, exist_ok=True)

DB = ROOT / "instance" / "ecoloop.db"
app = Flask(__name__)
app.secret_key = os.environ.get("ECOLOOP_SECRET_KEY", "local-demo-only-change-before-deployment")

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def now(): 
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def week(): 
    return datetime.now().strftime("%G-W%V")

def get_eco_level(pts: int) -> str:
    if pts >= 500: return "🏆 Planet Guardian"
    if pts >= 250: return "⭐ Earth Hero"
    if pts >= 100: return "🌟 Eco Master"
    if pts >= 30:  return "🌱 Green Hero"
    return "🌿 Seed Starter"

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created TEXT);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,title TEXT,description TEXT,price INTEGER,seller TEXT,image TEXT,status TEXT DEFAULT 'Available');
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,title TEXT,description TEXT,date TEXT,location TEXT,organizer TEXT,points INTEGER);
        CREATE TABLE IF NOT EXISTS joins(id INTEGER PRIMARY KEY,event_id INTEGER,username TEXT,status TEXT DEFAULT 'Joined',UNIQUE(event_id,username));
        CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY,username TEXT,body TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS points(id INTEGER PRIMARY KEY,username TEXT,amount INTEGER,reason TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS quizzes(id INTEGER PRIMARY KEY,username TEXT,week TEXT,score INTEGER,UNIQUE(username,week));
        CREATE TABLE IF NOT EXISTS pickups(id INTEGER PRIMARY KEY,username TEXT,items_summary TEXT,weight REAL,points INTEGER,pickup_date TEXT,time_slot TEXT,address TEXT,status TEXT DEFAULT 'Scheduled',created TEXT);
        """)
        if not c.execute("SELECT 1 FROM products").fetchone():
            c.execute("INSERT INTO products(title,description,price,seller,image,status) VALUES(?,?,?,?,?,?)",
                      ("Upcycled Glass Bottle Planter", "Handcrafted indoor planter made from repurposed glass bottles.", 20, "EcoStudio", "", "Available"))
        if not c.execute("SELECT 1 FROM events").fetchone():
            c.execute("INSERT INTO events(title,description,date,location,organizer,points) VALUES(?,?,?,?,?,?)",
                      ("Campus & Neighbourhood Clean Drive", "Join fellow students to segregate and recycle local park waste.", "2026-11-20", "Phagwara Main Gate", "GreenClub", 50))

def user_balance(user):
    if not user:
        return 40
    with connect() as c:
        res = c.execute("SELECT COALESCE(SUM(amount),0) FROM points WHERE username=?", (user,)).fetchone()
        return res[0] if res else 40

def award_points(user, amount, reason):
    if not user:
        user = "Guest"
    with connect() as c:
        c.execute("INSERT INTO points(username,amount,reason,created) VALUES(?,?,?,?)", (user, amount, reason, now()))
    session['points'] = user_balance(user)
    return True

@app.route("/")
def home():
    with connect() as c:
        p = c.execute("SELECT COUNT(*) FROM products WHERE status='Available'").fetchone()[0]
        e = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    current_user = session.get("user")
    pts = user_balance(current_user) if current_user else session.get('points', 40)
    stats = {"products": p, "events": e, "ecopoints": pts}
    return render_template("index.html", product_count=p, event_count=e, stats=stats)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    username = request.form.get("username", "").strip()
    session["user"] = username
    session["points"] = user_balance(username)
    flash(f"Welcome back, {username}!")
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    username = request.form.get("username", "").strip()
    session["user"] = username
    session["points"] = user_balance(username)
    flash("Registration successful! Welcome to EcoLoop AI.")
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect("/")

@app.route('/scanner', methods=['GET', 'POST'])
def scanner():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            filename = secure_filename(file.filename)
            if not filename:
                flash("Invalid file name. Please upload a valid image.")
                return redirect(request.url)

            # Validate the extension to avoid non-image / unsafe uploads.
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            allowed = {"png", "jpg", "jpeg", "webp", "gif"}
            if ext not in allowed:
                flash("Unsupported image format. Allowed: PNG, JPG, JPEG, WEBP, GIF.")
                return redirect(request.url)

            # Prefix with a uuid so same-named uploads never overwrite each other
            # and secure_filename already strips path-traversal segments.
            upload_dir = ROOT / "static" / "uploads"
            safe_name = f"{uuid.uuid4().hex}_{filename}"
            file_path = upload_dir / safe_name
            file.save(str(file_path))

            # Analyze waste image via Groq vision model.
            analysis_result = analyze_waste_image(str(file_path))

            # If analysis failed, surface the error instead of calling the guidance AI.
            if isinstance(analysis_result, str) and analysis_result.startswith("⚠️"):
                return render_template('scanner_result.html', result=analysis_result, guidance=None)

            # Automatically generate structured guidance.
            guidance_prompt = (
                f"Based on this waste analysis:\n{analysis_result}\n\n"
                "Provide a clear, step-by-step guidance plan for the user telling them exactly what they should do "
                "with this product (how to clean it, where to store it, how to dispose or upcycle it safely)."
            )
            ai_guidance = ask_sustainability_ai([{"role": "user", "content": guidance_prompt}])

            return render_template('scanner_result.html', result=analysis_result, guidance=ai_guidance)

    return render_template('scanner.html')
@app.route("/pickups", methods=["GET", "POST"])
def pickups():
    user = session.get("user", "Guest")
    if request.method == "POST":
        date = request.form.get("pickup_date")
        slot = request.form.get("time_slot")
        address = request.form.get("address")
        with connect() as c:
            c.execute("INSERT INTO pickups(username,items_summary,weight,points,pickup_date,time_slot,address,created) VALUES(?,?,?,?,?,?,?,?)",
                      (user, "Multi-Material Recyclables", 1.25, 25, date, slot, address, now()))
        award_points(user, 25, "Scheduled Doorstep Recycling Pickup")
        flash("Doorstep pickup scheduled! +25 EcoPoints awarded.")
        return redirect("/pickups")
    return render_template("pickups.html")

@app.route("/solar", methods=["GET", "POST"])
def solar():
    solar_result = None
    if request.method == "POST":
        try:
            cap = float(request.form["capacity"])
            sun = float(request.form["sun"])
            use = float(request.form["usage"])
            tariff = float(request.form["tariff"])
            gen = round(cap * sun * 0.85, 2)
            matched = min(gen, use)
            daily_savings = round(matched * tariff, 2)
            solar_result = {
                "gen": gen,
                "ratio": round((matched / use * 100) if use else 0, 1),
                "monthly_savings": round(daily_savings * 30, 2),
                "summary": f"Your {cap} kW system covers {round((matched / use * 100) if use else 0, 1)}% of your daily household demand."
            }
        except (ValueError, KeyError):
            flash("Please enter valid numeric values.")
    return render_template("solar.html", solar_result=solar_result)

@app.route("/market", methods=["GET"])
def market():
    with connect() as c:
        products = c.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("market.html", products=products)

@app.route("/market/list", methods=["GET", "POST"])
def market_list():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        desc = request.form.get("description", "").strip()
        price = int(request.form.get("price", 20))
        seller = session.get("user", "EcoCreator")
        with connect() as c:
            c.execute("INSERT INTO products(title,description,price,seller,image,status) VALUES(?,?,?,?,?,?)",
                      (title, desc, price, seller, "", "Available"))
        flash("Product listed successfully!")
        return redirect("/market")
    return render_template("market_list.html")

@app.route("/market/buy/<int:pid>", methods=["POST"])
def market_buy(pid):
    user = session.get("user", "Guest")
    with connect() as c:
        prod = c.execute("SELECT * FROM products WHERE id=? AND status='Available'", (pid,)).fetchone()
    if prod:
        award_points(user, -prod["price"], f"Redeemed: {prod['title']}")
        with connect() as c:
            c.execute("UPDATE products SET status='Redeemed' WHERE id=?", (pid,))
        flash(f"Successfully redeemed '{prod['title']}'!")
    return redirect("/market")

@app.route("/events", methods=["GET", "POST"])
def events():
    if request.method == "POST":
        user = session.get("user", "Guest")
        eid = int(request.form["eid"])
        with connect() as c:
            ev = c.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
        if ev:
            award_points(user, ev["points"], f"Joined Event: {ev['title']}")
        flash("Successfully joined event and earned EcoPoints!")
        return redirect("/events")
    with connect() as c:
        events_list = c.execute("SELECT * FROM events").fetchall()
    return render_template("events.html", events=events_list)

QUESTION_POOL = [
    ("Which item is usually suitable for paper recycling if clean and dry?", ["Clean newspaper", "Used battery", "Broken bulb", "Food waste"], 0, "Clean dry paper is commonly recyclable."),
    ("What is a good first step before throwing away a working shirt?", ["Burn it", "Donate or reuse it", "Throw it in a river", "Mix it with food scraps"], 1, "Reuse or donation extends a product's life."),
    ("When do solar panels generally produce electricity?", ["At midnight", "During daylight", "Only at night", "Only during rain"], 1, "Panels generate electricity from sunlight."),
    ("Which of these materials takes the longest time to naturally decompose in a landfill?", ["Plastic bottle", "Banana peel", "Paper napkin", "Cardboard box"], 0, "Plastics take hundreds of years to break down.")
]

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    user = session.get("user", "Guest")
    wk = week()
    if "current_quiz" not in session or (request.method == "POST" and "submit_quiz" in request.form):
        if request.method == "POST" and "submit_quiz" in request.form:
            score = 3
            pts = 15
            award_points(user, pts, f"Kids EcoPlay Quiz Weekly Score: {score}/4")
            flash(f"Quiz submitted! You scored {score}/4 and earned +{pts} EcoPoints.")
            session.pop("current_quiz", None)
            return redirect("/quiz")
        session["current_quiz"] = random.sample(QUESTION_POOL, 4)
    with connect() as c:
        completed = c.execute("SELECT 1 FROM quizzes WHERE username=? AND week=?", (user, wk)).fetchone() is not None
    return render_template("quiz.html", questions=session["current_quiz"], completed=completed)

@app.route("/dashboard")
def dashboard():
    user = session.get("user", "Guest")
    with connect() as c:
        pts_history = c.execute("SELECT * FROM points WHERE username=? ORDER BY id DESC LIMIT 15", (user,)).fetchall()
        pickups = c.execute("SELECT * FROM pickups WHERE username=? ORDER BY id DESC", (user,)).fetchall()
        total_pts = user_balance(user)
    level = get_eco_level(total_pts)
    return render_template("dashboard.html", pts_history=pts_history, pickups=pickups, total_pts=total_pts, level=level)

@app.route("/community", methods=["GET", "POST"])
def community():
    if request.method == "POST":
        user = session.get("user", "Guest")
        body = request.form.get("body", "").strip()
        if body:
            with connect() as c:
                c.execute("INSERT INTO posts(username,body,created) VALUES(?,?,?)", (user, body, now()))
        flash("Post shared with community!")
        return redirect("/community")
    with connect() as c:
        posts = c.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    return render_template("community.html", posts=posts)

@app.route("/assistant", methods=["GET", "POST"])
def assistant():
    answer = None
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            answer = ask_sustainability_ai(question)
    return render_template("assistant.html", answer=answer)

# --- ADD THE NEW API ROUTE HERE ---
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json() or {}
    messages = data.get("messages", [])
    
    if not messages:
        return jsonify({"reply": "Please ask a question."}), 400
        
    reply = ask_sustainability_ai(messages)
    return jsonify({"reply": reply})

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)