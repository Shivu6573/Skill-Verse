from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.user import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/")
def index():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("student.dashboard"))
    return redirect(url_for("auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.find_by_email(email)
        if user and User.verify_password(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["name"] = user["name"]
            session["email"] = user["email"]
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("student.dashboard"))
        flash("Invalid email or password", "error")
    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        interests = request.form.get("interests", "")
        skills = request.form.get("skills", "")
        goals = request.form.get("goals", "")
        user = User.create(name, email, password, "student", interests, skills, goals)
        if user:
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("auth.login"))
        flash("Email already exists", "error")
    return render_template("register.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
