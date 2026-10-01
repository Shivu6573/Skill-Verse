# Skill Verse

Skill Verse is an AI-powered learning platform. MongoDB access, authentication, Flask routes, business logic, and AI integrations remain in `backend/`. Existing Jinja templates, CSS, JavaScript, and images are in `frontend/`.

## Current UI Architecture

The existing interface is server-rendered Jinja, not a static single-page frontend. To preserve the current features without rewriting all screens, Flask loads templates and static assets from `frontend/`. `frontend/index.html` is the static local entry point and sends the browser to the Flask sign-in page. The browser API URL is configured in `frontend/static/js/api-config.js`.

This is a physical frontend/backend separation, but not yet a Vercel-static UI: the current pages require Jinja and data from Flask. Before Vercel can serve the UI independently, the Jinja pages must be converted to static HTML/JavaScript views and Flask page/form routes must be exposed as JSON APIs. No deployment has been performed.

## Local Run

Start MongoDB locally, or set `MONGO_URI` to your MongoDB Atlas connection string in `backend/.env`.

Backend, in PowerShell from the project root:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Keep the existing `backend/.env` when present. For a new checkout only, create it with `Copy-Item .env.example .env`, then set `MONGO_URI`, `SECRET_KEY`, and any AI keys. Flask listens on `http://localhost:5000`.

Frontend, in a second PowerShell terminal from the project root:

```powershell
cd frontend
python -m http.server 5173
```

Open `http://localhost:5173`; the static entry page forwards to the current Flask-rendered sign-in screen. The UI will then be at `http://localhost:5000`.

## Configuration and Data Flow

`frontend/static/js/api-config.js` contains the one browser-facing `SKILLVERSE_API_BASE_URL`. Set it to the HTTPS Render URL when testing a directly hosted backend. The frontend contains no MongoDB URI, Flask secret, or AI API key.

The browser sends login, registration, form, and page requests to Flask. EduBot chat and course progress/completion use the configured API URL with session credentials. Flask verifies the session, executes the existing models/routes, and reads/writes the existing MongoDB collections. Gemini/OpenAI calls are made only by backend code using `GEMINI_API_KEY` or `OPENAI_API_KEY`.

CORS allows the local frontend origins by default. For a deployed frontend, set `FRONTEND_ORIGINS` on the backend to its exact origin. For cookie authentication across different sites, browsers may block third-party cookies; a same-origin reverse proxy or a later token-based API is needed for dependable Vercel-to-Render authentication.

## Existing Routes and Integrations

The Flask page/form routes remain in `backend/routes/auth.py`, `student.py`, and `admin.py`. JSON endpoints used by browser JavaScript are `POST /api/chat`, `POST /course/<course_id>/progress`, and `POST /course/<course_id>/complete`; `GET /api/debug-keys` reports whether AI keys are configured without returning them. Student course/recommendation, quiz, certificate, leaderboard, and admin behavior remains in the existing Flask routes.

MongoDB is initialized in `backend/app.py` from `MONGO_URI`; models in `backend/models/` use that backend-only connection. Existing collection names and document shapes are unchanged.

## Hosting the Current App

The current HTML files are Jinja templates rendered by Flask. Host the frontend and backend together as one Render web service for now; deploying `frontend/` by itself to Vercel will not serve the Jinja pages or Flask form routes.

1. Rotate the MongoDB, OpenAI, and Gemini credentials previously shared, then use the new credentials only in hosting environment settings. Keep `backend/.env` out of Git.
2. Push the repository to GitHub. Before pushing, check that `backend/.env` is ignored and is not included in the files being committed.
3. In MongoDB Atlas, create a database user and allow network access from Render. Copy the Atlas connection string; use the `skillverse` database. The app adds `/skillverse` if the URI has no database path.
4. In Render, create a Web Service connected to the GitHub repository. Leave Root Directory blank so both `backend/` and `frontend/` are available.
5. Set the Render build command to `pip install -r backend/requirements.txt`.
6. Set the Render start command to `cd backend && gunicorn --workers 1 --bind 0.0.0.0:$PORT 'app:create_app()'`.
7. Add these environment variables in Render: `MONGO_URI`, `SECRET_KEY`, `APP_BASE_URL`, `SESSION_COOKIE_SECURE=true`, `SESSION_COOKIE_SAMESITE=Lax`, `FLASK_DEBUG=false`, `GEMINI_API_KEY`, `GEMINI_MODEL`, and `OPENAI_API_KEY` if used. Set `APP_BASE_URL` to the HTTPS Render URL after Render assigns it. Generate a strong secret key locally; do not share it or commit it.
8. Deploy, then test registration/login, courses, quizzes, progress, certificates, chatbot, and admin pages on the Render HTTPS URL. Check Render logs if a workflow fails.

`frontend/static/js/api-config.js` uses `http://localhost:5000` locally and the current HTTPS origin in production, so this one-service Render setup keeps cookie authentication same-origin. Set `FRONTEND_ORIGINS` to the exact frontend origin only if you later serve it from a different domain.

Before moving the frontend to Vercel, convert the Jinja templates and Flask form/page workflows into standalone HTML/JavaScript and JSON API routes, then decide on cross-domain authentication. Also note that Render's filesystem is ephemeral: profile photo uploads and filesystem-backed sessions will not survive every restart/deploy unless persistent storage/session storage is configured.
