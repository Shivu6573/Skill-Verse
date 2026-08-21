from app import mongo, bcrypt, create_app
from datetime import datetime
from bson import ObjectId

class User:
    @staticmethod
    def create(name, email, password, role="student", interests="", skills="", goals=""):
        if mongo.db.users.find_one({"email": email}):
            return None
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        user = {
            "name": name,
            "email": email,
            "password": hashed,
            "role": role,
            "interests": interests,
            "skills": skills,
            "goals": goals,
            "enrolledCourses": [],
            "completedCourses": [],
            "bookmarks": [],
            "quizScores": [],
            "totalScore": 0,
            "joinedAt": datetime.utcnow().strftime("%Y-%m-%d"),
        }
        result = mongo.db.users.insert_one(user)
        user["_id"] = result.inserted_id
        return user

    @staticmethod
    def find_by_email(email):
        return mongo.db.users.find_one({"email": email})

    @staticmethod
    def find_by_id(user_id):
        return mongo.db.users.find_one({"_id": ObjectId(user_id)})

    @staticmethod
    def all_students():
        return list(mongo.db.users.find({"role": "student"}))

    @staticmethod
    def update(user_id, data):
        mongo.db.users.update_one({"_id": ObjectId(user_id)}, {"$set": data})

    @staticmethod
    def delete(user_id):
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})

    @staticmethod
    def verify_password(stored, provided):
        return bcrypt.check_password_hash(stored, provided)

    @staticmethod
    def seed_demo_users():
        if mongo.db is None:
            app = create_app(seed_data_flag=False)
            with app.app_context():
                return User.seed_demo_users()

        users = [
            ("Admin User", "admin@edu.com", "admin123", "admin", "", "", ""),
            ("Johnson", "alice@edu.com", "alice123", "student", "AI,Machine Learning,Data Science", "Python,Data Analysis", "Become a Data Scientist"),
            ("Bob Smith", "bob@edu.com", "bob123", "student", "Web Development,React,Node.js", "JavaScript,HTML", "Full Stack Developer"),
            ("Carol Williams", "carol@edu.com", "carol123", "student", "Data Science,Machine Learning,Visualization", "R,SQL", "Data Analyst"),
            ("David Lee", "david@edu.com", "david123", "student", "Backend Development,APIs,Cloud", "Python,Java", "Backend Engineer"),
            ("Eva Martinez", "eva@edu.com", "eva123", "student", "AI,Databases,Analytics", "SQL,Python", "AI Engineer"),
        ]
        for name, email, pwd, role, interests, skills, goals in users:
            if not mongo.db.users.find_one({"email": email}):
                User.create(name, email, pwd, role, interests, skills, goals)
