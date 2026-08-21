from app import create_app

app = create_app(seed_data_flag=False)
client = app.test_client()

paths = ['/login', '/register', '/admin/leaderboard', '/dashboard', '/courses', '/leaderboard']
for p in paths:
    r = client.get(p, follow_redirects=False)
    print(p, '->', r.status_code, 'Location:' , r.headers.get('Location'))
