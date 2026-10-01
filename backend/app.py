from flask import Flask
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_session import Session
from flask_cors import CORS
import os
import secrets
import sys
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

mongo = PyMongo()
bcrypt = Bcrypt()

def create_app(seed_data_flag=True):
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    app = Flask(
        __name__,
        template_folder=os.path.join(frontend_dir, "templates"),
        static_folder=os.path.join(frontend_dir, "static"),
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    mongo_uri = os.getenv("MONGO_URI") or "mongodb://localhost:27017/skillverse"
    parsed_mongo_uri = urlsplit(mongo_uri)
    if parsed_mongo_uri.path in ("", "/"):
        mongo_uri = urlunsplit(parsed_mongo_uri._replace(path="/skillverse"))
    app.config["MONGO_URI"] = mongo_uri
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE") or "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

    configured_origins = os.getenv("FRONTEND_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173"
    allowed_origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    CORS(app, origins=allowed_origins, supports_credentials=True)

    mongo.init_app(app)
    bcrypt.init_app(app)
    Session(app)

    # Custom Jinja2 filters
    @app.template_filter('enumerate')
    def jinja_enumerate(iterable, start=0):
        return enumerate(iterable, start)

    @app.template_filter('average')
    def jinja_average(lst):
        return sum(lst) / len(lst) if lst else 0

    from routes.auth import auth_bp
    from routes.student import student_bp
    from routes.admin import admin_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    if seed_data_flag:
        # Seed data on first run
        with app.app_context():
            seed_data()

    return app

def seed_data():
    from models.user import User
    from models.course import Course
    from models.quiz import Quiz

    User.seed_demo_users()
    Course.seed_courses()
    Quiz.seed_quizzes()

if __name__ == "__main__":
    sys.modules["app"] = sys.modules[__name__]
    app = create_app()
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
    )
