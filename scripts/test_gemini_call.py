import os, json, sys
from flask import Flask

# Ensure workspace root is on sys.path so `routes` imports resolve
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# load .env manually
env_path = r'C:\Users\shivu\OneDrive\Desktop\Skill Verse\.env'
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k,v=line.split('=',1)
            os.environ.setdefault(k.strip(), v.strip())

from routes import student as s
app = Flask(__name__)
# call function inside app context
prompt = [
    {"role": "system", "content": "You are an expert project recommender. Return EXACTLY one small, practical project as JSON."},
    {"role": "user", "content": "Course: Example Course. Course skills: Python, Flask. Student skills: Python, HTML."}
]
with app.app_context():
    try:
        result = s._call_gemini_api(prompt)
        print('SUCCESS')
        print(json.dumps(result, indent=2))
    except Exception as e:
        print('ERROR', repr(e))
