from app import create_app
from models.user import User
app = create_app(seed_data_flag=False)
with app.app_context():
    students = User.all_students()
    print('total students', len(students))
    counts = {}
    for s in students:
        k = (s.get('email'), s.get('name'))
        counts[k] = counts.get(k, 0) + 1
    dups = [(k,v) for k,v in counts.items() if v>1]
    print('duplicates', dups)
    for idx, s in enumerate(students, start=1):
        if s.get('name','').startswith('Smoke Tester'):
            print('smoke', idx, s.get('_id'), s.get('email'), s.get('name'), s.get('totalScore'))
