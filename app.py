from flask import Flask
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_session import Session
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

mongo = PyMongo()
bcrypt = Bcrypt()

def create_app(seed_data_flag=True):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "skillverse-secret-key-2024")
    app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/skillverse")
    app.config["SESSION_TYPE"] = "filesystem"

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
    app = create_app()
    app.run(debug=True, port=5000)
