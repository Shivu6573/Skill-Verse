import os
os.chdir(r'C:\Users\shivu\OneDrive\Desktop\Skill Verse')
from app import create_app

app = create_app(seed_data_flag=False)
client = app.test_client()
with client.session_transaction() as sess:
    sess['user_id'] = 'test-user'

rv = client.post('/api/chat', json={'message': 'Help me with web development', 'history': []})
print('status', rv.status_code)
print(rv.get_data(as_text=True))
