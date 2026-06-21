import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Chat
from google import genai

# =====================
# APP CONFIG
# =====================
app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# =====================
# GEMINI CLIENT
# =====================
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)

# =====================
# USER LOADER
# =====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# =====================
# CREATE DB
# =====================
with app.app_context():
    db.create_all()

# =====================
# ROUTES
# =====================
@app.route("/")
def home():
    if current_user.is_authenticated:
        return render_template("chat.html")
    return redirect(url_for("login"))

# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            return "User already exists"

        user = User(
            username=username,
            password=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("home"))

        return "Invalid credentials"

    return render_template("login.html")

# ---------- LOGOUT ----------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------- CHAT ----------
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.json
    message = data.get("message")

    if not message:
        return jsonify({"error": "Empty message"}), 400

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=message
        )

        reply = response.text

        # save chat
        chat = Chat(
            user_id=current_user.id,
            message=message,
            response=reply
        )

        db.session.add(chat)
        db.session.commit()

        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"response": str(e)})

# ---------- HEALTH ----------
@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(debug=True)
