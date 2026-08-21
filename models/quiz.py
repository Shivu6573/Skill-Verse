from app import mongo
from datetime import datetime
from bson import ObjectId

QUIZ_DATA = [
    ("AI Fundamentals Quiz", "AI", [
        {"question": "What does AI stand for?", "options": ["Automated Intelligence", "Artificial Intelligence", "Algorithmic Integration", "Applied Interface"], "answer": 1},
        {"question": "Which is a type of Machine Learning?", "options": ["Supervised", "Imagined", "Compiled", "Static"], "answer": 0},
        {"question": "What is a neural network modeled after?", "options": ["Computers", "The human brain", "DNA", "Solar systems"], "answer": 1},
        {"question": "NLP stands for?", "options": ["Network Layer Protocol", "Natural Language Processing", "Neural Learning Process", "None"], "answer": 1},
    ]),
    ("Web Development Quiz", "Web Development", [
        {"question": "What does HTML stand for?", "options": ["HyperText Markup Language", "HighText Machine Language", "HyperText Machine Language", "None"], "answer": 0},
        {"question": "Which tag is used for JavaScript in HTML?", "options": ["<js>", "<script>", "<javascript>", "<code>"], "answer": 1},
        {"question": "CSS stands for?", "options": ["Cascading Style Sheets", "Computer Style Sheets", "Creative Style System", "None"], "answer": 0},
        {"question": "Which is a JS framework?", "options": ["Django", "Flask", "React", "Laravel"], "answer": 2},
    ]),
    ("Data Science Quiz", "Data Science", [
        {"question": "What library is used for data manipulation in Python?", "options": ["NumPy", "Pandas", "Matplotlib", "Seaborn"], "answer": 1},
        {"question": "SQL stands for?", "options": ["Structured Query Language", "Simple Query Logic", "System Query Language", "None"], "answer": 0},
        {"question": "Which chart shows distribution?", "options": ["Bar chart", "Pie chart", "Histogram", "Line chart"], "answer": 2},
        {"question": "What is a DataFrame?", "options": ["A 2D table structure", "A graph", "A machine", "A protocol"], "answer": 0},
    ]),
]

class Quiz:
    @staticmethod
    def all():
        return list(mongo.db.quizzes.find())

    @staticmethod
    def find_by_id(quiz_id):
        return mongo.db.quizzes.find_one({"_id": ObjectId(quiz_id)})

    @staticmethod
    def create(title, category, questions=None):
        quiz = {
            "title": title,
            "category": category,
            "questions": questions or [],
            "createdAt": datetime.utcnow().strftime("%Y-%m-%d"),
        }
        result = mongo.db.quizzes.insert_one(quiz)
        return result.inserted_id

    @staticmethod
    def delete(quiz_id):
        mongo.db.quizzes.delete_one({"_id": ObjectId(quiz_id)})

    @staticmethod
    def seed_quizzes():
        if mongo.db.quizzes.count_documents({}) == 0:
            for title, category, questions in QUIZ_DATA:
                Quiz.create(title, category, questions)
