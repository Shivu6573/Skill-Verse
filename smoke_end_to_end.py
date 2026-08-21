import time
from app import create_app
from models.user import User
from models.course import Course
from models.quiz import Quiz

app = create_app(seed_data_flag=True)
client = app.test_client()

print('Using seeded app for smoke tests')

# Register a fresh user
email = f"testuser_{int(time.time())}@example.com"
password = "pass1234"
resp = client.post('/register', data={'name':'Smoke Tester','email':email,'password':password}, follow_redirects=False)
print('/register ->', resp.status_code, resp.headers.get('Location'))
if resp.status_code == 302 and '/login' in resp.headers.get('Location',''):
    print('Register redirect OK')
else:
    print('Register may have failed')

# Login as the newly created user
resp = client.post('/login', data={'email':email,'password':password}, follow_redirects=False)
print('/login ->', resp.status_code, resp.headers.get('Location'))
if resp.status_code == 302 and ('/dashboard' in resp.headers.get('Location','') or '/admin' in resp.headers.get('Location','')):
    print('Login redirect OK')
else:
    print('Login may have failed')

# Access student dashboard
resp = client.get('/dashboard')
print('/dashboard ->', resp.status_code)

# Access leaderboard (student)
resp = client.get('/leaderboard')
print('/leaderboard ->', resp.status_code)

# Update profile
resp = client.post('/profile', data={'name':'Smoke Tester Updated','interests':'Testing'}, follow_redirects=False)
print('/profile POST ->', resp.status_code, resp.headers.get('Location'))

# Logout
resp = client.get('/logout', follow_redirects=False)
print('/logout ->', resp.status_code, resp.headers.get('Location'))

# Admin flows: login as seeded admin
admin_email = 'admin@edu.com'
admin_pass = 'admin123'
resp = client.post('/login', data={'email':admin_email,'password':admin_pass}, follow_redirects=False)
print('Admin /login ->', resp.status_code, resp.headers.get('Location'))

# Access admin leaderboard
resp = client.get('/admin/leaderboard')
print('/admin/leaderboard ->', resp.status_code)

# Access admin manage users
resp = client.get('/admin/users')
print('/admin/users ->', resp.status_code)

print('Smoke tests completed')
