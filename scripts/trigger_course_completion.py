import os, sys, json
# load .env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k,v=line.split('=',1)
            os.environ.setdefault(k.strip(), v.strip())

# ensure project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from models.user import User
from models.course import Course
import routes.student as student

app = create_app()  # seed data by default so demo users and courses exist
with app.test_request_context():
    # find or create a demo student
    user = User.find_by_email('alice@edu.com')
    if not user:
        user = User.create('Alice Demo', 'alice@edu.com', 'alice123', 'student', 'AI,Machine Learning', 'Python,Data Analysis', '')
    # pick a course
    courses = Course.all()
    if not courses:
        print('No courses found; ensure DB is seeded')
        sys.exit(1)
    course = courses[0]
    course_id = str(course.get('_id'))

    print('Marking course complete for user', user.get('email'), 'course:', course.get('title'))
    try:
        # Ensure the course is not already marked completed for this user so we trigger recommendation generation
        cc = user.get('completedCourses', []) or []
        if course_id in cc:
            cc = [c for c in cc if c != course_id]
            User.update(str(user.get('_id')), {'completedCourses': cc})
            # also remove any existing recommendation for this course
            ai_list = user.get('aiRecommendations', []) or []
            ai_list = [r for r in ai_list if str(r.get('courseId')) != course_id]
            User.update(str(user.get('_id')), {'aiRecommendations': ai_list})
            # reload user
            user = User.find_by_email(user.get('email'))

        result = student._mark_course_complete(str(user.get('_id')), course_id, payload={'progress': 100})
        print('Result:', json.dumps(result, indent=2))
        # fetch updated user
        updated = User.find_by_email(user.get('email'))
        print('AI Recommendations stored:', json.dumps(updated.get('aiRecommendations', [])[:3], indent=2))
    except Exception as e:
        print('ERROR during completion:', repr(e))
