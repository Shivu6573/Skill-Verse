from app import mongo
from datetime import datetime
from bson import ObjectId

def _normalize_title(title):
    return "".join(ch.lower() for ch in title if ch.isalnum())


def _is_valid_youtube_id(youtube_id):
    return bool(youtube_id and isinstance(youtube_id, str) and len(youtube_id) == 11 and all(ch.isalnum() or ch in {'_', '-'} for ch in youtube_id))


COURSE_UPDATE_DATES = [
    "May 08, 2026",
    "May 12, 2026",
    "May 15, 2026",
    "May 19, 2026",
    "May 22, 2026",
    "May 26, 2026",
    "May 29, 2026",
    "Jun 03, 2026",
    "Jun 07, 2026",
    "Jun 10, 2026",
    "Jun 14, 2026",
    "Jun 18, 2026",
    "Jun 21, 2026",
    "Jun 25, 2026",
    "Jun 28, 2026",
    "Jul 02, 2026",
    "Jul 06, 2026",
    "Jul 09, 2026",
    "Jul 12, 2026",
    "Jul 15, 2026",
    "Jul 18, 2026",
    "Jul 22, 2026",
    "Jul 25, 2026",
    "Jul 28, 2026",
    "Jul 31, 2026",
]

COURSE_DATA = [
    ("Python for Data Science", "Data Science", "Intermediate", "6 hours", "Master Python libraries for data analysis: NumPy, Pandas, Matplotlib.", "LHBE6Q9XlzI"),
    ("SQL & Database Design", "Data Science", "Beginner", "4 hours", "Relational databases, normalization and complex SQL queries.", "HXV3zeQKqGY"),
    ("Cloud Computing with AWS", "Data Science", "Intermediate", "5 hours", "Deploy scalable applications on AWS using EC2, S3 and Lambda.", "5gnoVjpfWxU"),
    ("Machine Learning Basics", "Machine Learning", "Beginner", "6 hours", "Learn supervised, unsupervised and reinforcement learning algorithms.", "GwIo3gDZCVQ"),
    ("Deep Learning with Python", "AI", "Intermediate", "8 hours", "Build neural networks using TensorFlow and Keras.", "aircAruvnKk"),
    ("Introduction to AI", "AI", "Beginner", "4 hours", "Master the foundational concepts of Artificial Intelligence.", "JMUxmLyrhSk"),
    ("Computer Vision", "AI", "Advanced", "6 hours", "Image classification, object detection using OpenCV and YOLO.", "oXlwWbU8l2o"),
    ("Statistics for Machine Learning", "Machine Learning", "Beginner", "4 hours", "Probability, distributions, hypothesis testing and Bayesian thinking.", "xxpc-HPKN28"),
    ("Data Structures & Algorithms", "Web Development", "Intermediate", "9 hours", "Essential DS&A for coding interviews and software engineering.", "RBSGKlAvoiM"),
    ("React & Frontend Development", "Web Development", "Intermediate", "7 hours", "Build dynamic UIs with React, hooks, and state management.", "bMknfKXIFA8"),
    ("Node.js Backend", "Web Development", "Intermediate", "6 hours", "Server-side JavaScript, REST APIs, Express and MongoDB.", "Oe421EPjeBE"),
    ("Natural Language Processing", "AI", "Advanced", "8 hours", "Text processing, transformers, BERT and GPT architectures.", "CMrHM8a3hqw"),
    ("Software Testing Fundamentals", "Software Testing", "Beginner", "6 Hours", "Learn the fundamentals of software testing and quality assurance.", "I7wZLN0mA88"),
    ("Selenium with Java Automation Testing", "Test Automation", "Intermediate", "8 Hours", "Build automated UI tests with Selenium and Java.", "FRn5J31eAMw"),
    ("Data Analytics with Excel & Power BI", "Data Analytics", "Beginner", "7 Hours", "Learn data analytics workflows using Excel and Power BI.", "pSAC3N1cFNI"),
    ("Microsoft Power BI Dashboard Development", "Business Intelligence", "Intermediate", "6 Hours", "Create professional business dashboards with Power BI.", "UXhGRVTndQA"),
    ("IT Technical Support Fundamentals", "Technical Support", "Beginner", "5 Hours", "Learn essential IT support skills and troubleshooting fundamentals.", "lJC_sJ6jhDo"),
    ("Computer Networking (CCNA Basics)", "Networking", "Beginner", "8 Hours", "Get started with networking concepts and CCNA basics.", "EPeFhfENuXA"),
    ("Cyber Security Essentials", "Cyber Security", "Beginner", "7 Hours", "Understand core cybersecurity concepts and best practices.", "lpa8uy4DyMo"),
    ("DevOps with Docker & Jenkins", "DevOps", "Intermediate", "8 Hours", "Learn modern DevOps workflows with Docker and Jenkins.", "uHNOqKdqQas"),
    ("Microsoft Azure Fundamentals (AZ-900)", "Cloud", "Intermediate", "6 Hours", "Build your foundation in Azure cloud services and architecture.", "NPEsD6n9A_I"),
    ("Android App Development with Kotlin", "Mobile App Development", "Beginner", "8 Hours", "Create Android apps using Kotlin and modern mobile development practices.", "F9UC9DY-vIU"),
    ("Python Programming", "Programming", "Beginner", "8 Hours", "Learn Python fundamentals, variables, loops, functions, OOP, file handling, and modules.", "rfscVS0vtbw"),
    ("Java Programming", "Programming", "Intermediate", "10 Hours", "Learn Java syntax, OOP, collections, exception handling, multithreading, and JDBC.", "grEKMHGYyns"),
    ("JavaScript Programming", "Programming", "Beginner", "8 Hours", "Learn JavaScript basics, DOM manipulation, ES6, asynchronous programming, and APIs.", "upDLs1sn7g4"),
]

class Course:
    @staticmethod
    def all():
        return list(mongo.db.courses.find())

    @staticmethod
    def find_by_id(course_id):
        return mongo.db.courses.find_one({"_id": ObjectId(course_id)})

    @staticmethod
    def create(title, category, difficulty, duration, description, youtube_id, created_at=None):
        course = {
            "title": title,
            "category": category,
            "difficulty": difficulty,
            "duration": duration,
            "description": description,
            "youtubeId": youtube_id,
            "createdAt": created_at or datetime.utcnow().strftime("%Y-%m-%d"),
        }
        result = mongo.db.courses.insert_one(course)
        return result.inserted_id

    @staticmethod
    def delete(course_id):
        mongo.db.courses.delete_one({"_id": ObjectId(course_id)})

    @staticmethod
    def by_category():
        pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
        return list(mongo.db.courses.aggregate(pipeline))

    @staticmethod
    def seed_courses():
        for index, (title, cat, diff, dur, desc, url) in enumerate(COURSE_DATA):
            updated_date = COURSE_UPDATE_DATES[index] if index < len(COURSE_UPDATE_DATES) else "Jul 31, 2026"
            existing = mongo.db.courses.find_one({"title": title})
            if not existing:
                normalized_title = _normalize_title(title)
                existing = next(
                    (
                        course
                        for course in mongo.db.courses.find()
                        if _normalize_title(course.get("title", "")) == normalized_title
                    ),
                    None,
                )
            youtube_id = url if _is_valid_youtube_id(url) else None
            if not youtube_id:
                youtube_id = extract_youtube_video_id(url)
            if existing:
                update_doc = {"youtubeId": youtube_id, "createdAt": updated_date}
                unset_doc = {"contentUrl": "", "youtubeUrl": ""}
                mongo.db.courses.update_one(
                    {"_id": existing["_id"]},
                    {"$set": update_doc, "$unset": unset_doc}
                )
            else:
                Course.create(title, cat, diff, dur, desc, youtube_id, created_at=updated_date)
