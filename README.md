# Skill Verse - Personalized Learning Platform

A full-stack AI-powered learning platform built with Python (Flask), MongoDB, and vanilla HTML/CSS/JS.

## 📁 Project Structure

```
skill-verse/
├── app.py                    # Flask app factory + entry point
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── models/
│   ├── __init__.py
│   ├── user.py              # User model (CRUD + seeding)
│   ├── course.py            # Course model (CRUD + seeding)
│   └── quiz.py              # Quiz model (CRUD + seeding)
├── routes/
│   ├── __init__.py
│   ├── auth.py              # Login, Register, Logout
│   ├── student.py           # All student pages & actions
│   ├── admin.py             # Admin panel routes
│   └── api.py               # REST API (chatbot)
├── templates/
│   ├── base.html            # Base layout with sidebar
│   ├── nav_macros.html      # Sidebar nav macros
│   ├── login.html           # Sign in page
│   ├── register.html        # Create account page
│   ├── dashboard.html       # Student dashboard
│   ├── courses.html         # Browse courses
│   ├── recommend.html       # AI recommendations
│   ├── quiz_list.html       # Quiz center
│   ├── take_quiz.html       # Take a quiz
│   ├── quiz_result.html     # Quiz score result
│   ├── chatbot.html         # EduBot AI chat
│   ├── leaderboard.html     # Leaderboard (shared)
│   ├── feedback.html        # User feedback form
│   ├── profile.html         # My Profile
│   └── admin/
│       ├── dashboard.html   # Admin overview
│       ├── manage_users.html
│       ├── manage_courses.html
│       ├── manage_quizzes.html
│       └── all_courses.html
└── static/
    ├── css/
    │   └── main.css         # Complete dark theme styles
    └── js/
        └── main.js          # Animations + helpers
```

## 🚀 Setup

### 1. Install MongoDB
- Install [MongoDB Community](https://www.mongodb.com/try/download/community)
- Start: `mongod` or `brew services start mongodb-community`

### 2. Install Python dependencies
```bash
cd skill-verse
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with the API keys needed for chatbot and recommendations
```

### 4. Run the app
```bash
python app.py
```

Open http://localhost:5000

## ✨ Features

**Student:**
- Dashboard with stats, charts, progress
- Browse & enroll in 36 courses (AI, Data Science, ML, Web Dev)
- AI-powered personalized recommendations
- Quiz center with scoring
- EduBot AI chatbot (Claude-powered)
- Leaderboard rankings
- Feedback submission
- Profile management

**Admin:**
- Platform overview dashboard
- Manage users (view, delete)
- Manage courses (add, delete)
- Manage quizzes (add, delete)
- View all courses & leaderboard

## 🛠 Tech Stack
- **Backend:** Python, Flask, Flask-PyMongo, Flask-Bcrypt, Flask-Session
- **Database:** MongoDB
- **Frontend:** HTML5, CSS3 (custom dark theme), Vanilla JS
- **Charts:** Chart.js
- **AI:** Google Gemini and OpenAI APIs (chatbot and recommendations)
