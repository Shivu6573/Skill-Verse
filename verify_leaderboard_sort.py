from app import create_app
from routes.leaderboard_sort import get_leaderboard_rank
from models.user import User

app = create_app(seed_data_flag=False)
with app.app_context():
    students = User.all_students()
    ranked = get_leaderboard_rank(students)
    for i, u in enumerate(ranked[:10], 1):
        name = u.get('name', '<unknown>')
        xp = u.get('totalScore', 0)
        courses = len(u.get('completedCourses', []) or [])
        print(i, name, xp, courses)
