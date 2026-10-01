from flask import Blueprint, render_template, request, redirect, url_for, session
from models.user import User
from models.course import Course
from models.quiz import Quiz
from app import mongo
from routes.leaderboard_sort import get_leaderboard_rank
from services.course_player import extract_youtube_video_id
import functools

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "admin":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route("/")
@admin_required
def dashboard():
    user = User.find_by_id(session["user_id"])
    students = User.all_students()
    courses = Course.all()
    quizzes = Quiz.all()
    feedback = list(mongo.db.feedback.find())
    by_category = Course.by_category()
    return render_template("admin/dashboard.html", user=user,
        students=students, courses=courses, quizzes=quizzes,
        feedback=feedback, by_category=by_category)

@admin_bp.route("/users")
@admin_required
def manage_users():
    user = User.find_by_id(session["user_id"])
    students = User.all_students()
    return render_template("admin/manage_users.html", user=user, students=students)

@admin_bp.route("/users/delete/<user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    User.delete(user_id)
    return redirect(url_for("admin.manage_users"))

@admin_bp.route("/courses", methods=["GET", "POST"])
@admin_required
def manage_courses():
    user = User.find_by_id(session["user_id"])
    if request.method == "POST":
        title = request.form.get("title")
        category = request.form.get("category")
        difficulty = request.form.get("difficulty", "Beginner")
        duration = request.form.get("duration", "2 hours")
        description = request.form.get("description", "")
        content_url = request.form.get("content_url", "")
        youtube_id = extract_youtube_video_id(content_url)
        Course.create(title, category, difficulty, duration, description, youtube_id)
        return redirect(url_for("admin.manage_courses"))
    courses = Course.all()
    return render_template("admin/manage_courses.html", user=user, courses=courses)

@admin_bp.route("/courses/delete/<course_id>", methods=["POST"])
@admin_required
def delete_course(course_id):
    Course.delete(course_id)
    return redirect(url_for("admin.manage_courses"))

@admin_bp.route("/quizzes", methods=["GET", "POST"])
@admin_required
def manage_quizzes():
    user = User.find_by_id(session["user_id"])
    if request.method == "POST":
        title = request.form.get("title")
        category = request.form.get("category")
        Quiz.create(title, category)
        return redirect(url_for("admin.manage_quizzes"))
    quizzes = Quiz.all()
    return render_template("admin/manage_quizzes.html", user=user, quizzes=quizzes)

@admin_bp.route("/quizzes/delete/<quiz_id>", methods=["POST"])
@admin_required
def delete_quiz(quiz_id):
    Quiz.delete(quiz_id)
    return redirect(url_for("admin.manage_quizzes"))

@admin_bp.route("/courses/all")
@admin_required
def all_courses():
    user = User.find_by_id(session["user_id"])
    courses = Course.all()
    return render_template("admin/all_courses.html", user=user, courses=courses)

@admin_bp.route("/leaderboard")
@admin_required
def leaderboard():
    user = User.find_by_id(session["user_id"])
    students = User.all_students()
    ranked = get_leaderboard_rank(students)
    return render_template("leaderboard.html", user=user, ranked=ranked, is_admin=True)
