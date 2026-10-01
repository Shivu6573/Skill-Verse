from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, current_app, send_file
from models.user import User
from models.course import Course
from models.quiz import Quiz
from app import mongo
from bson import ObjectId
from datetime import datetime
from io import BytesIO
from werkzeug.utils import secure_filename
from routes.leaderboard_sort import get_leaderboard_rank
from services.course_player import extract_youtube_video_id, is_valid_youtube_id, should_complete_lesson
from services.certificates import build_certificate_context
import functools
import os
import json
import requests
import time
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

student_bp = Blueprint("student", __name__)

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        user = User.find_by_id(session["user_id"])
        if user is None:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    return User.find_by_id(session["user_id"])


def _serialize_course(course):
    serialized = dict(course)
    if "_id" in serialized:
        serialized["_id"] = str(serialized["_id"])
    return serialized


def _serialize_quiz_score(quiz_score):
    serialized = dict(quiz_score)
    quiz_id = serialized.get("quizId")
    if isinstance(quiz_id, ObjectId):
        serialized["quizId"] = str(quiz_id)
    elif quiz_id is not None:
        serialized["quizId"] = str(quiz_id)
    return serialized


def _get_course_progress(user, course_id):
    progress_state = user.get("courseProgress", {}) or {}
    if not isinstance(progress_state, dict):
        return {}
    return progress_state.get(course_id, {})


def _save_course_progress(user_id, course_id, payload):
    user = User.find_by_id(user_id)
    if not user:
        return None

    course_progress = user.get("courseProgress", {}) or {}
    if not isinstance(course_progress, dict):
        course_progress = {}

    existing = course_progress.get(course_id, {}) or {}
    merged = dict(existing)
    merged.update(payload)
    merged["updatedAt"] = datetime.utcnow().isoformat()
    course_progress[course_id] = merged
    User.update(user_id, {"courseProgress": course_progress})
    return course_progress[course_id]


def _mark_course_complete(user_id, course_id, payload=None):
    user = User.find_by_id(user_id)
    if not user:
        return {"completed": False, "message": "User not found"}

    completed = list(user.get("completedCourses", []) or [])
    already_completed = course_id in completed
    progress_payload = dict(payload or {})
    progress_payload.update({"completed": True, "completedAt": datetime.utcnow().isoformat()})

    course = Course.find_by_id(course_id)
    if course:
        try:
            percentage = int(round(float(progress_payload.get("progress", 100) or 100)))
        except (TypeError, ValueError):
            percentage = 100
        certificate_context = build_certificate_context(
            user,
            course,
            percentage=percentage,
            completion_datetime=progress_payload.get("completedAt"),
            issue_date=datetime.utcnow().strftime("%Y-%m-%d"),
        )
        progress_payload["certificateId"] = certificate_context["certificateId"]
        progress_payload["certificateVerificationUrl"] = certificate_context["verificationUrl"]
        progress_payload["certificateQrCodeDataUrl"] = certificate_context["qrCodeDataUrl"]

    _save_course_progress(user_id, course_id, progress_payload)

    update_fields = {}
    if not already_completed:
        completed.append(course_id)
        update_fields["completedCourses"] = completed
        current_score = int(user.get("totalScore", 0) or 0)
        update_fields["totalScore"] = current_score + 10
        user["completedCourses"] = completed
        user["totalScore"] = update_fields["totalScore"]

    if update_fields:
        User.update(user_id, update_fields)

    result = {"completed": True, "message": "Lesson completed successfully"}
    if course:
        result["certificateUrl"] = url_for("student.certificate", course_id=course_id)

    # Trigger course-specific Gemini recommendation only when the course reaches 100% and it wasn't already completed
    if not already_completed:
        try:
            try:
                percent_val = int(round(float(progress_payload.get("progress", 100) or 100)))
            except Exception:
                percent_val = 100
            if percent_val >= 100:
                try:
                    rec = _get_course_recommendation(user, course)
                    if rec:
                        # store recommendation on user record
                        ai_list = user.get("aiRecommendations", []) or []
                        ai_list.append(rec)
                        User.update(user_id, {"aiRecommendations": ai_list})
                        result["recommendations"] = [rec]
                except Exception as exc:
                    # Surface the actual Gemini error to the client
                    current_app.logger.error("Gemini recommendation failed: %s", repr(exc))
                    result["recommendationError"] = str(exc)
        except Exception as exc:
            current_app.logger.error("Failed to generate AI recommendation after completion: %s", repr(exc))
            print("Failed to generate AI recommendation after completion:", repr(exc))

    return result


@student_bp.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    courses = Course.all()
    quizzes = Quiz.all()
    enrolled_ids = user.get("enrolledCourses", [])
    enrolled_courses = [_serialize_course(c) for c in courses if str(c["_id"]) in enrolled_ids]
    completed_ids = user.get("completedCourses", [])
    quiz_scores = [_serialize_quiz_score(qs) for qs in user.get("quizScores", [])]
    notifications = _get_notifications(user)
    leaderboard_rank = _get_rank(user)
    recommended = [_serialize_course(c) for c in _get_recommendations(user, courses)[:5]]
    # Build user's certificates summary from courseProgress
    course_progress = user.get("courseProgress", {}) or {}
    certificates = []
    for cid, payload in course_progress.items():
        cert_id = payload.get("certificateId")
        if not cert_id:
            continue
        course = Course.find_by_id(cid)
        percentage = int(payload.get("progress", 100) or 100)
        certificates.append({
            "courseId": cid,
            "courseTitle": course.get("title") if course else "Unknown Course",
            "certificateId": cert_id,
            "issueDate": payload.get("issueDate") or payload.get("completedAt") or payload.get("updatedAt") or "",
            "percentage": percentage,
            "viewUrl": url_for("student.certificate", course_id=cid),
            "downloadUrl": url_for("student.download_certificate", course_id=cid),
            "verifyUrl": payload.get("certificateVerificationUrl"),
        })

    return render_template("dashboard.html",
        user=user, enrolled_courses=enrolled_courses,
        completed_ids=completed_ids, quiz_scores=quiz_scores,
        notifications=notifications, leaderboard_rank=leaderboard_rank,
        recommended=recommended, all_courses=courses,
        certificates=certificates, certificates_count=len(certificates))

def _get_notifications(user):
    notes = []
    for cid in user.get("enrolledCourses", []):
        course = Course.find_by_id(cid)
        if course:
            notes.append({"msg": f"You enrolled in: {course['title']}", "time": user.get("joinedAt","")})
    for cid in user.get("completedCourses", []):
        course = Course.find_by_id(cid)
        if course:
            notes.insert(0, {"msg": f"Congratulations! You completed: {course['title']} 🎉", "time": user.get("joinedAt","")})
    return notes[:5]

def _get_rank(user):
    students = User.all_students()
    ranked = get_leaderboard_rank(students)
    for i, s in enumerate(ranked):
        if str(s["_id"]) == str(user["_id"]):
            return i + 1
    return len(ranked)

def _get_recommendations(user, courses):
    interests = [i.strip().lower() for i in user.get("interests","").split(",") if i.strip()]
    enrolled_ids = user.get("enrolledCourses", [])
    recs = []
    for c in courses:
        if str(c["_id"]) not in enrolled_ids:
            cat = c.get("category","").lower()
            title = c.get("title","").lower()
            if any(i in cat or i in title for i in interests):
                recs.append(c)
    seen = set()
    unique = []
    for c in recs:
        t = c["title"]
        if t not in seen:
            seen.add(t)
            unique.append(c)
    return unique


def _build_recommendation_profile(user):
    # Only include completed courses, skills and interests per requirements
    completed_ids = [str(cid) for cid in user.get("completedCourses", []) or []]
    completed_courses = [Course.find_by_id(cid) for cid in completed_ids]
    completed_titles = [c["title"] for c in completed_courses if c]
    interests = [i.strip() for i in user.get("interests", "").split(",") if i.strip()]
    skills = [s.strip() for s in user.get("skills", "").split(",") if s.strip()]
    return {
        "name": user.get("name", "Learner"),
        "completed_courses": completed_titles,
        "interests": interests,
        "skills": skills,
    }


def _build_gemini_prompt(profile):
    # Build a compact prompt using only completed courses, skills and interests
    details = []
    if profile.get("completed_courses"):
        details.append("Completed Courses: " + ", ".join(profile["completed_courses"]))
    if profile.get("interests"):
        details.append("Interests: " + ", ".join(profile["interests"]))
    if profile.get("skills"):
        details.append("Skills: " + ", ".join(profile["skills"]))

    user_desc = "; ".join(details) if details else "No completed courses, skills, or interests provided."

    # Ask Gemini to return 3-5 practical, hands-on project recommendations.
    system_msg = "You are an AI project recommendation engine for an online learning platform."
    user_msg = (
        "Generate between 3 and 5 personalized, practical project recommendations for this learner. "
        "Base recommendations ONLY on the learner's completed courses, skills, and interests. "
        "Do NOT use quiz scores, progress, enrolled courses, or career goals. "
        "Each recommendation must be concise and include the fields: \"title\", \"description\", \"difficulty\" (Beginner|Intermediate|Advanced), \"requiredSkills\" (array), \"technologies\" (array), \"estimatedTime\" (string), \"reason\" (one-line why recommended), and \"learningOutcomes\" (array of 3–5 outcomes). "
        "Prefer beginner-friendly projects when the user has no data. "
        "Respond with valid JSON only using this schema:\n{\n  \"projectRecommendations\": [ { \"title\": \"...\", \"description\": \"...\", \"difficulty\": \"...\", \"requiredSkills\": [\"...\"], \"technologies\": [\"...\"], \"estimatedTime\": \"...\", \"reason\": \"...\", \"learningOutcomes\": [\"...\"] } ] }\n"
        "Do not include any explanatory text outside the JSON. "
        "Learner profile: " + user_desc
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]


def _call_gemini_api(prompt):
    # Use only GEMINI_API_KEY for recommendations per requirements
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    if not api_key:
        current_app.logger.error("Gemini API key not set (GEMINI_API_KEY)")
        raise RuntimeError("Gemini API key not configured on server (GEMINI_API_KEY)")

    # Basic model sanity check
    if not isinstance(model, str) or "gemini" not in model.lower():
        current_app.logger.warning("Unusual GEMINI_MODEL='%s' — ensure model name is correct", repr(model))

    # Convert the OpenAI-style prompt (list of messages) into a single system prompt and user message
    system_prompt = ""
    user_message_parts = []
    try:
        for msg in prompt:
            role = (msg.get("role") or "user").lower()
            content = msg.get("content", "")
            if role == "system":
                if system_prompt:
                    system_prompt += "\n" + content
                else:
                    system_prompt = content
            else:
                user_message_parts.append(content)
    except Exception:
        # Fallback: stringify prompt
        user_message_parts = [str(prompt)]

    user_message = "\n\n".join([p for p in user_message_parts if p])
    if not system_prompt:
        system_prompt = "You are an expert project recommender. Return EXACTLY one small, practical project as JSON."

    gemini_payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]
        }],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 1400}
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Retry on transient errors (rate limit / 5xx)
    backoff = 1.0
    max_attempts = 3
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=gemini_payload, timeout=30)

            # Log response for diagnostics
            current_app.logger.debug("Gemini response status (attempt %d): %s", attempt, resp.status_code)
            current_app.logger.debug("Gemini response body (attempt %d): %s", attempt, resp.text)

            if resp.status_code == 429:
                body = resp.text
                current_app.logger.warning("Gemini rate limited (429), attempt %d: %s", attempt, body)
                last_exc = RuntimeError(f"Gemini rate limit (429): {body}")
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise last_exc

            if resp.status_code in {400, 401, 403, 404}:
                # Invalid/unauthorized API key or bad request
                body = resp.text
                current_app.logger.error("Gemini API error %s: %s", resp.status_code, body)
                if resp.status_code in {401, 403}:
                    raise RuntimeError("Invalid or unauthorized Gemini API key.")
                if resp.status_code == 404:
                    raise RuntimeError("Gemini model not found for this API version or model; check GEMINI_MODEL.")
                raise RuntimeError(f"Gemini request failed: {resp.status_code} - {body}")

            if resp.status_code >= 500:
                current_app.logger.error("Gemini server error %s: %s", resp.status_code, resp.text)
                raise RuntimeError("The Gemini service is temporarily unavailable. Please try again in a few minutes.")

            resp.raise_for_status()

            gemini_result = resp.json()
            candidates = gemini_result.get("candidates", []) if isinstance(gemini_result, dict) else []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                reply = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                if not reply:
                    # last-resort: try other shapes
                    reply = candidates[0].get("content", {}).get("text") or resp.text
            else:
                # fallback to raw text
                reply = resp.text

            if not reply:
                current_app.logger.error("Gemini response missing content: %s", repr(gemini_result))
                raise RuntimeError(f"Gemini response missing content: {repr(gemini_result)}")

            # Strip fences and whitespace
            cleaned = reply.strip()
            if cleaned.startswith("```"):
                parts = cleaned.split("\n")
                if parts and parts[0].startswith("```"):
                    parts = parts[1:]
                if parts and parts[-1].startswith("```"):
                    parts = parts[:-1]
                cleaned = "\n".join(parts).strip()

            # Try to parse JSON from the response
            try:
                return json.loads(cleaned)
            except Exception as e:
                # Attempt to extract a JSON object from the text as a fallback
                try:
                    # Try to find the first '{' and take everything after it
                    m = re.search(r"\{[\s\S]*\Z", cleaned)
                    candidate = None
                    if m:
                        candidate = m.group(0)
                        # Try progressively trimming to the last closing brace to recover truncated JSON
                        last_brace = candidate.rfind('}')
                        if last_brace != -1:
                            trimmed = candidate[:last_brace+1]
                            try:
                                return json.loads(trimmed)
                            except Exception:
                                # try iterative trimming in case of nested issues
                                for i in range(len(trimmed), 0, -1):
                                    j = trimmed.rfind('}', 0, i)
                                    if j == -1:
                                        continue
                                    try:
                                        return json.loads(trimmed[:j+1])
                                    except Exception:
                                        continue

                        # If trimming didn't work, attempt simple repairs: balance quotes and braces
                        repaired = candidate
                        if repaired.count('"') % 2 != 0:
                            repaired = repaired + '"'
                        open_braces = repaired.count('{')
                        close_braces = repaired.count('}')
                        if open_braces > close_braces:
                            repaired = repaired + ('}' * (open_braces - close_braces))
                        try:
                            return json.loads(repaired)
                        except Exception:
                            current_app.logger.debug("Fallback JSON candidate failed to parse after repair; candidate=%.400s", repaired)
                    else:
                        current_app.logger.debug("No JSON-like block found in Gemini output")
                except Exception:
                    current_app.logger.debug("JSON extraction fallback failed")
                current_app.logger.error("Failed to parse Gemini JSON output: %s; raw=%s", repr(e), cleaned[:2000])
                raise RuntimeError(f"Failed to parse Gemini JSON output: {repr(e)}; raw={cleaned[:2000]}")

        except requests.exceptions.Timeout as te:
            current_app.logger.warning("Gemini request timed out (attempt %d): %s", attempt, repr(te))
            last_exc = te
            if attempt < max_attempts:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise RuntimeError(f"Gemini API timeout: {repr(te)}")
        except requests.exceptions.RequestException as re:
            current_app.logger.error("Gemini request exception (attempt %d): %s", attempt, repr(re))
            last_exc = re
            if attempt < max_attempts:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise RuntimeError(f"Gemini request failed: {repr(re)}")

    # If we exit loop unexpectedly
    raise RuntimeError(f"Gemini call failed after {max_attempts} attempts: {repr(last_exc)}")


def _parse_gemini_recommendations(result):
    if not isinstance(result, dict):
        return []
    recommendations = result.get("projectRecommendations") or []
    parsed = []
    for item in recommendations:
        if not isinstance(item, dict):
            continue
        parsed.append({
            "title": item.get("title", "AI Project Recommendation"),
            "description": item.get("description", "Build a practical project to level up your skills."),
            "difficulty": item.get("difficulty", "Beginner"),
            "requiredSkills": item.get("requiredSkills", []),
            "technologies": item.get("technologies", []),
            "estimatedTime": item.get("estimatedTime", "4-6 hours"),
            "reason": item.get("reason", "This project is tailored to your learning profile."),
            "learningOutcomes": item.get("learningOutcomes", []),
        })
        if len(parsed) >= 5:
            break
    # Ensure between 3 and 5 recommendations. If fewer than 3, return empty to trigger fallback.
    if len(parsed) < 3:
        current_app.logger.warning("Gemini returned fewer than 3 recommendations: %s", len(parsed))
        print("Gemini returned fewer than 3 recommendations:", len(parsed))
        return []
    return parsed


def _build_course_prompt(course, user):
    # Build a compact prompt focused on a single course completion
    course_name = course.get("title", "Course")
    course_skills = ", ".join(course.get("skills", []) if isinstance(course.get("skills"), list) else (course.get("skills") or "").split(","))
    student_skills = ", ".join([s.strip() for s in (user.get("skills") or "").split(",") if s.strip()])

    system_msg = "You are an expert project recommender. Return EXACTLY one small, practical project as JSON."
    user_msg = (
        "Given the completed course and the learner's skills, recommend ONE small, practical project tightly tied to the course. "
        "Do NOT return generic projects. Keep it beginner-friendly and actionable. "
        "Return JSON ONLY with a single object: { \"projectRecommendation\": { \"title\": \"...\", \"description\": \"...\", \"difficulty\": \"Beginner|Intermediate|Advanced\", \"requiredSkills\": [\"...\"], \"technologies\": [\"...\"], \"estimatedTime\": \"...\", \"reason\": \"one-line reason\", \"learningOutcomes\": [\"...\"] } }\n"
        "Course: " + course_name + ". "
        "Course skills: " + (course_skills or "none") + ". "
        "Student skills: " + (student_skills or "none") + "."
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]


def _parse_single_recommendation(result):
    if not isinstance(result, dict):
        return None
    item = result.get("projectRecommendation") or result.get("projectRecommendations")
    if isinstance(item, list) and item:
        item = item[0]
    if not isinstance(item, dict):
        return None
    # Normalize fields
    return {
        "title": item.get("title", "Project Recommendation"),
        "description": item.get("description", "A practical project to apply course skills."),
        "difficulty": item.get("difficulty", "Beginner"),
        "requiredSkills": item.get("requiredSkills", []),
        "technologies": item.get("technologies", []),
        "estimatedTime": item.get("estimatedTime", "2-6 hours"),
        "reason": item.get("reason", "Relevant to the completed course."),
        "learningOutcomes": item.get("learningOutcomes", [])
    }


def _get_course_recommendation(user, course):
    prompt = _build_course_prompt(course, user)
    raw = _call_gemini_api(prompt)
    if not raw:
        raise RuntimeError("Gemini API returned no response")
    parsed = _parse_single_recommendation(raw)
    if not parsed:
        raise RuntimeError("Failed to parse Gemini recommendation JSON")
    # Attach metadata linking to course and student
    parsed["courseId"] = str(course.get("_id") if course and course.get("_id") else "")
    parsed["courseTitle"] = course.get("title") if course else ""
    parsed["generatedAt"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return parsed


def _generate_missing_course_recommendations(user):
    """Generate and store Gemini recommendations for any completed courses
    that don't yet have a recommendation attached to the user's `aiRecommendations`.
    Returns the list of newly generated recommendations.
    """
    try:
        ai_list = user.get("aiRecommendations", []) or []
        existing_course_ids = {str(r.get("courseId")) for r in ai_list if r.get("courseId")}
        new_recs = []
        errors = {}
        completed_ids = [str(cid) for cid in user.get("completedCourses", []) or []]
        course_progress = user.get("courseProgress", {}) or {}

        for cid in completed_ids:
            if cid in existing_course_ids:
                continue
            payload = course_progress.get(cid, {}) or {}
            try:
                progress_val = int(payload.get("progress", 100) or 100)
            except Exception:
                progress_val = 100
            # Only generate for courses that reached 100% completion
            if progress_val < 100:
                continue
            course = Course.find_by_id(cid)
            try:
                rec = _get_course_recommendation(user, course)
                if rec:
                    new_recs.append(rec)
                    ai_list.append(rec)
            except Exception as exc:
                errors[cid] = str(exc)

        if new_recs:
            # Persist updated recommendations for the user
            try:
                User.update(session["user_id"], {"aiRecommendations": ai_list})
            except Exception:
                # fallback attempt: update by user _id string
                try:
                    User.update(str(user.get("_id") or session.get("user_id")), {"aiRecommendations": ai_list})
                except Exception as exc:
                    current_app.logger.error("Failed to persist AI recommendations: %s", repr(exc))
        return new_recs, errors
    except Exception as exc:
        current_app.logger.error("Error generating missing course recommendations: %s", repr(exc))
        return [], {"_fatal": str(exc)}


def _get_ai_project_recommendations(user, courses):
    completed_ids = [str(cid) for cid in user.get("completedCourses", []) or []]
    if not completed_ids:
        return []
    # Keep the on-demand bulk recommendation generation disabled: recommendations
    # are generated per-course at the moment of 100% completion and stored on the user.
    return []


def _save_ai_recommendations(user_id, recommendations):
    if not isinstance(recommendations, list):
        return
    User.update(user_id, {"aiRecommendations": recommendations})


def _generate_and_store_recommendations(user):
    courses = Course.all()
    recommendations = _get_ai_project_recommendations(user, courses)
    if recommendations:
        _save_ai_recommendations(session["user_id"], recommendations)
    return recommendations


def _fallback_recommendations(user):
    # Minimal fallback generator used only when Gemini fails or returns too few items
    # Tailor fallback lightly to user's skills/interests when available
    skills = [s for s in (user.get("skills") or "").split(",") if s.strip()]
    interests = [i for i in (user.get("interests") or "").split(",") if i.strip()]
    base_projects = [
        {
            "title": "Personal Portfolio Website",
            "description": "Create a responsive portfolio site showcasing projects and skills.",
            "difficulty": "Beginner",
            "requiredSkills": skills or ["HTML", "CSS", "JavaScript"],
            "technologies": ["HTML", "CSS", "JavaScript"],
            "estimatedTime": "4-8 hours",
            "reason": "Good starter project to showcase your work and practice web fundamentals.",
            "learningOutcomes": ["Build responsive layouts","Deploy a static site","Showcase projects"],
        },
        {
            "title": "To-Do Task Manager",
            "description": "Build a CRUD task manager with filtering, persistence, and simple auth.",
            "difficulty": "Beginner",
            "requiredSkills": skills or ["Python", "Flask", "HTML"],
            "technologies": ["Flask", "SQLite", "Bootstrap"],
            "estimatedTime": "6-10 hours",
            "reason": "Hands-on CRUD app to practice backend and frontend integration.",
            "learningOutcomes": ["Create REST endpoints","Persist data","Implement basic auth"],
        },
        {
            "title": "Simple Chat App (WebSocket)",
            "description": "Implement a real-time chat room using WebSockets for live messaging.",
            "difficulty": "Intermediate",
            "requiredSkills": skills or ["JavaScript", "WebSockets"],
            "technologies": ["Socket.IO", "Node.js or Flask-SocketIO"],
            "estimatedTime": "8-12 hours",
            "reason": "Introduces real-time communication and event-driven programming.",
            "learningOutcomes": ["Use WebSockets","Handle real-time events","Scale basic features"],
        },
    ]
    # Return 3 fallback projects
    return base_projects[:3]

@student_bp.route("/courses")
@login_required
def courses():
    user = get_current_user()
    all_courses = Course.all()
    enrolled_ids = user.get("enrolledCourses", [])
    completed_ids = user.get("completedCourses", [])
    seen = set(); unique = []
    for c in all_courses:
        t = c["title"]
        if t not in seen:
            seen.add(t); unique.append(c)
    return render_template("courses.html", user=user, courses=unique,
        enrolled_ids=enrolled_ids, completed_ids=completed_ids)

@student_bp.route("/enroll/<course_id>", methods=["POST"])
@login_required
def enroll(course_id):
    user = get_current_user()
    enrolled = user.get("enrolledCourses", [])
    if course_id not in enrolled:
        enrolled.append(course_id)
        User.update(session["user_id"], {"enrolledCourses": enrolled})
    return redirect(request.referrer or url_for("student.courses"))

@student_bp.route("/complete/<course_id>", methods=["POST"])
@login_required
def complete_course(course_id):
    user = get_current_user()
    completed = user.get("completedCourses", [])
    if course_id not in completed:
        completed.append(course_id)
        User.update(session["user_id"], {"completedCourses": completed})
    return redirect(url_for("student.certificate", course_id=course_id))

@student_bp.route("/bookmark/<course_id>", methods=["POST"])
@login_required
def bookmark(course_id):
    user = get_current_user()
    bookmarks = user.get("bookmarks", [])
    if course_id in bookmarks:
        bookmarks.remove(course_id)
    else:
        bookmarks.append(course_id)
    User.update(session["user_id"], {"bookmarks": bookmarks})
    return redirect(request.referrer or url_for("student.courses"))


@student_bp.route("/course/<course_id>")
@login_required
def course_player(course_id):
    user = get_current_user()
    course = Course.find_by_id(course_id)
    if not course:
        return redirect(url_for("student.courses"))

    enrolled_ids = [str(cid) for cid in (user.get("enrolledCourses", []) or [])]
    if str(course_id) not in enrolled_ids and str(course.get("_id")) not in enrolled_ids:
        return redirect(url_for("student.courses"))

    course_progress = _get_course_progress(user, str(course_id)) or {}
    completed_ids = user.get("completedCourses", [])
    is_completed = str(course_id) in completed_ids or bool(course_progress.get("completed"))

    video_id = None
    video_url = None
    if is_valid_youtube_id(course.get("youtubeId")):
        video_id = course.get("youtubeId")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        legacy_url = course.get("contentUrl") or course.get("youtubeUrl")
        video_id = extract_youtube_video_id(legacy_url)
        if video_id:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            mongo.db.courses.update_one(
                {"_id": course["_id"]},
                {"$set": {"youtubeId": video_id}, "$unset": {"contentUrl": "", "youtubeUrl": ""}}
            )
        else:
            video_url = None

    ordered_courses = []
    for enrolled_id in enrolled_ids:
        enrolled_course = Course.find_by_id(enrolled_id)
        if enrolled_course:
            ordered_courses.append(enrolled_course)

    current_index = next((index for index, item in enumerate(ordered_courses) if str(item.get("_id")) == str(course_id)), -1)
    next_course = ordered_courses[current_index + 1] if current_index >= 0 and current_index + 1 < len(ordered_courses) else None
    next_course_id = str(next_course.get("_id")) if next_course else None
    next_course_title = next_course.get("title") if next_course else None

    initial_position = float(course_progress.get("position", 0) or 0)
    initial_progress = float(course_progress.get("progress", 0) or 0)
    initial_state = course_progress.get("state", "paused")

    return render_template(
        "course_player.html",
        user=user,
        course=_serialize_course(course),
        video_id=video_id,
        video_url=video_url,
        initial_position=initial_position,
        initial_progress=initial_progress,
        initial_state=initial_state,
        is_completed=is_completed,
        next_course_id=next_course_id,
        next_course_title=next_course_title,
        course_progress=course_progress,
    )


@student_bp.route("/course/<course_id>/progress", methods=["POST"])
@login_required
def update_course_progress(course_id):
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    position = float(payload.get("position", 0) or 0)
    duration = float(payload.get("duration", 0) or 0)
    progress_value = float(payload.get("progress", 0) or 0)
    watched_seconds = int(payload.get("watchedSeconds", 0) or 0)
    state = payload.get("state", "paused")
    ended = bool(payload.get("ended", False))

    progress_payload = {
        "position": position,
        "duration": duration,
        "progress": progress_value,
        "watchedSeconds": watched_seconds,
        "state": state,
        "ended": ended,
    }

    saved_progress = _save_course_progress(session["user_id"], str(course_id), progress_payload)

    completion_ready = ended or should_complete_lesson(
        progress_value / 100.0 if progress_value else 0.0,
        watched_seconds,
        ended
    )

    response = {
        "saved": True,
        "completed": False,
        "completionReady": completion_ready,
        "progress": saved_progress,
        "message": "Progress saved",
    }
    return jsonify(response)


@student_bp.route("/course/<course_id>/complete", methods=["POST"])
@login_required
def complete_course_player(course_id):
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    position = float(payload.get("position", 0) or 0)
    progress_value = float(payload.get("progress", 0) or 0)
    watched_seconds = int(payload.get("watchedSeconds", 0) or 0)
    ended = bool(payload.get("ended", False))

    already_completed = str(course_id) in user.get("completedCourses", [])
    if already_completed:
        return jsonify({
            "completed": True,
            "message": "Lesson already completed.",
            "certificateUrl": url_for("student.certificate", course_id=course_id),
        })

    progress_ratio = progress_value / 100.0 if progress_value else 0.0
    if not should_complete_lesson(progress_ratio, watched_seconds, ended):
        return jsonify({
            "completed": False,
            "message": "You must watch the full lesson before marking it complete.",
        })

    complete_result = _mark_course_complete(session["user_id"], str(course_id), payload)
    return jsonify(complete_result)


@student_bp.route("/certificate/<course_id>")
@login_required
def certificate(course_id):
    user = get_current_user()
    course = Course.find_by_id(course_id)
    if not course:
        return redirect(url_for("student.courses"))

    completed_ids = [str(cid) for cid in (user.get("completedCourses", []) or [])]
    course_progress = _get_course_progress(user, str(course_id)) or {}
    if str(course_id) not in completed_ids and not bool(course_progress.get("completed")):
        return redirect(url_for("student.course_player", course_id=course_id))

    percentage = int(course_progress.get("progress", 100) or 100)
    if percentage > 100:
        percentage = 100

    certificate_context = build_certificate_context(
        user,
        course,
        percentage=percentage,
        completion_datetime=course_progress.get("completedAt") or course_progress.get("updatedAt"),
        issue_date=datetime.utcnow().strftime("%Y-%m-%d"),
        certificate_id=course_progress.get("certificateId"),
    )

    return render_template("certificate.html", user=user, course=course, certificate=certificate_context)


@student_bp.route("/certificate/<course_id>/download")
@login_required
def download_certificate(course_id):
    user = get_current_user()
    course = Course.find_by_id(course_id)
    if not course:
        return redirect(url_for("student.courses"))

    completed_ids = [str(cid) for cid in (user.get("completedCourses", []) or [])]
    course_progress = _get_course_progress(user, str(course_id)) or {}
    if str(course_id) not in completed_ids and not bool(course_progress.get("completed")):
        return redirect(url_for("student.course_player", course_id=course_id))

    percentage = int(course_progress.get("progress", 100) or 100)
    if percentage > 100:
        percentage = 100

    certificate_context = build_certificate_context(
        user,
        course,
        percentage=percentage,
        completion_datetime=course_progress.get("completedAt") or course_progress.get("updatedAt"),
        issue_date=datetime.utcnow().strftime("%Y-%m-%d"),
        certificate_id=course_progress.get("certificateId"),
    )

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    seal_path = os.path.join(current_app.static_folder, "images", "skill-verse-seal.png")
    if os.path.exists(seal_path):
        pdf.drawImage(seal_path, 180, 260, width=260, height=260, preserveAspectRatio=True)

    pdf.setTitle(f"Skill Verse Certificate - {course.get('title')}")
    pdf.setFillColor(colors.HexColor("#0A2540"))
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(width / 2, height - 90, "SKILL VERSE")
    pdf.setFillColor(colors.HexColor("#0F4C81"))
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(width / 2, height - 130, "CERTIFICATE OF COMPLETION")

    pdf.setFillColor(colors.HexColor("#0A2540"))
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(width / 2, 470, certificate_context["studentName"])
    pdf.setFillColor(colors.HexColor("#4E5F74"))
    pdf.setFont("Helvetica-Oblique", 13)
    pdf.drawCentredString(width / 2, 438, "has successfully completed the course")
    pdf.setFillColor(colors.HexColor("#0A2540"))
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(width / 2, 400, certificate_context["courseName"])

    pdf.setFillColor(colors.HexColor("#0A2540"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(width / 2 - 120, 330, "ISSUED")
    pdf.drawCentredString(width / 2 + 120, 330, "DURATION")

    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width / 2 - 120, 312, certificate_context["issueDate"])
    pdf.drawCentredString(width / 2 + 120, 312, certificate_context["courseDuration"])

    pdf.setFillColor(colors.HexColor("#D4AF37"))
    pdf.line(160, 280, width - 160, 280)

    pdf.setFillColor(colors.HexColor("#0A2540"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(width / 2 - 180, 230, "Instructor")
    pdf.drawCentredString(width / 2 + 180, 230, "Verified")
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width / 2 - 180, 210, certificate_context["instructorName"])
    pdf.drawCentredString(width / 2 + 180, 210, "Yes")

    pdf.setFillColor(colors.HexColor("#4E5F74"))
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width / 2, 160, f"Certificate ID: {certificate_context['certificateId']}")
    pdf.drawCentredString(width / 2, 145, "Skill Verse • Verified • Authentic • Certified")

    pdf.save()
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True,
                     download_name=f"skill-verse-certificate-{certificate_context['certificateId']}.pdf")


@student_bp.route("/certificate/verify/<certificate_id>")
def certificate_verification(certificate_id):
    for student in User.all_students():
        course_progress_state = student.get("courseProgress", {}) or {}
        for course_id, progress_payload in course_progress_state.items():
            if progress_payload.get("certificateId") == certificate_id:
                course = Course.find_by_id(course_id)
                if course:
                    certificate_context = build_certificate_context(
                        student,
                        course,
                        percentage=int(progress_payload.get("progress", 100) or 100),
                        completion_datetime=progress_payload.get("completedAt") or progress_payload.get("updatedAt"),
                        issue_date=datetime.utcnow().strftime("%Y-%m-%d"),
                        certificate_id=certificate_id,
                    )
                    return render_template("certificate.html", user=student, course=course, certificate=certificate_context, verified=True)

    return render_template("certificate_verification.html", certificate_id=certificate_id, found=False)


@student_bp.route("/certificates")
@login_required
def certificates():
    user = get_current_user()
    course_progress = user.get("courseProgress", {}) or {}
    certificates = []
    for cid, payload in course_progress.items():
        cert_id = payload.get("certificateId")
        if not cert_id:
            continue
        course = Course.find_by_id(cid)
        percentage = int(payload.get("progress", 100) or 100)
        ctx = build_certificate_context(
            user,
            course or {"title": "Unknown Course"},
            percentage=percentage,
            completion_datetime=payload.get("completedAt") or payload.get("updatedAt"),
            issue_date=payload.get("issueDate") or datetime.utcnow().strftime("%Y-%m-%d"),
            certificate_id=cert_id,
        )
        certificates.append({
            "courseId": cid,
            "courseTitle": course.get("title") if course else "Unknown Course",
            "certificateId": cert_id,
            "issueDate": ctx.get("issueDate"),
            "percentage": ctx.get("percentage"),
            "viewUrl": url_for("student.certificate", course_id=cid),
            "downloadUrl": url_for("student.download_certificate", course_id=cid),
            "verifyUrl": ctx.get("verificationUrl"),
        })

    return render_template("certificates.html", user=user, certificates=certificates)


@student_bp.route("/recommendations", methods=["GET"])
@login_required
def get_saved_recommendations():
    user = get_current_user()
    # Generate any missing recommendations for already-completed courses,
    # then return stored recommendations only.
    try:
        new_recs, errors = _generate_missing_course_recommendations(user)
    except Exception as exc:
        return jsonify({"recommended": [], "hasCompletedCourses": bool(user.get("completedCourses", [])), "errors": {"_fatal": str(exc)}}), 500

    user_fresh = User.find_by_id(session["user_id"]) or user
    recommendations = user_fresh.get("aiRecommendations", []) or []
    response = {"recommended": recommendations, "hasCompletedCourses": bool(user.get("completedCourses", []))}
    if errors:
        response["errors"] = errors
    return jsonify(response)


@student_bp.route("/recommend")
@login_required
def recommend():
    user = get_current_user()
    # Ensure recommendations exist for any previously completed courses
    try:
        new_recs, errors = _generate_missing_course_recommendations(user)
        if new_recs:
            user = User.find_by_id(session["user_id"]) or user
    except Exception as exc:
        errors = {"_fatal": str(exc)}

    recommendations = user.get("aiRecommendations", []) or []
    has_completed = bool(user.get("completedCourses", []))
    return render_template("recommend.html", user=user, recommended=recommendations, has_completed_courses=has_completed, gen_errors=(errors if 'errors' in locals() else {}))

@student_bp.route("/quiz")
@login_required
def quiz_list():
    user = get_current_user()
    quizzes = Quiz.all()
    attempted = [str(q["quizId"]) for q in user.get("quizScores", [])]
    return render_template("quiz_list.html", user=user, quizzes=quizzes, attempted=attempted)

@student_bp.route("/quiz/<quiz_id>", methods=["GET", "POST"])
@login_required
def take_quiz(quiz_id):
    user = get_current_user()
    quiz = Quiz.find_by_id(quiz_id)
    if not quiz:
        return redirect(url_for("student.quiz_list"))
    if request.method == "POST":
        questions = quiz.get("questions", [])
        correct = 0
        for i, q in enumerate(questions):
            ans = request.form.get(f"q{i}")
            if ans is not None and int(ans) == q["answer"]:
                correct += 1
        score = int((correct / len(questions)) * 100) if questions else 0
        quiz_scores = user.get("quizScores", [])
        quiz_scores = [qs for qs in quiz_scores if str(qs.get("quizId")) != quiz_id]
        quiz_scores.append({"quizId": str(quiz_id), "title": quiz["title"],
            "score": score, "total": len(questions), "correct": correct,
            "date": datetime.utcnow().strftime("%Y-%m-%d")})
        total_score = sum(qs.get("correct", 0) for qs in quiz_scores)
        User.update(session["user_id"], {"quizScores": quiz_scores, "totalScore": total_score})
        return redirect(url_for("student.quiz_result", quiz_id=quiz_id, score=score))
    return render_template("take_quiz.html", user=user, quiz=quiz)

@student_bp.route("/quiz/<quiz_id>/result")
@login_required
def quiz_result(quiz_id):
    user = get_current_user()
    quiz = Quiz.find_by_id(quiz_id)
    score = request.args.get("score", 0)
    return render_template("quiz_result.html", user=user, quiz=quiz, score=int(score))

@student_bp.route("/chatbot")
@login_required
def chatbot():
    user = get_current_user()
    return render_template("chatbot.html", user=user)

@student_bp.route("/leaderboard")
@login_required
def leaderboard():
    user = get_current_user()
    students = User.all_students()
    ranked = get_leaderboard_rank(students)
    return render_template("leaderboard.html", user=user, ranked=ranked)

@student_bp.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    user = get_current_user()
    if request.method == "POST":
        rating = int(request.form.get("rating", 5))
        text = request.form.get("feedback", "")
        mongo.db.feedback.insert_one({
            "userId": ObjectId(session["user_id"]),
            "userName": user["name"],
            "rating": rating,
            "text": text,
            "date": datetime.utcnow().strftime("%Y-%m-%d")
        })
        return redirect(url_for("student.dashboard"))
    return render_template("feedback.html", user=user)

@student_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    if request.method == "POST":
        update_data = {}
        name = request.form.get("name", user.get("name", ""))
        interests = request.form.get("interests", "")
        skills = request.form.get("skills", "")
        goals = request.form.get("goals", "")
        phone = request.form.get("phone", "")
        about_me = request.form.get("aboutMe", "")
        learning_category = request.form.get("learningCategory", "")
        difficulty = request.form.get("difficulty", "")
        learning_style = request.form.get("learningStyle", "")
        daily_goal = request.form.get("dailyGoal", "")

        update_data.update({
            "name": name,
            "interests": interests,
            "skills": skills,
            "goals": goals,
            "phone": phone,
            "aboutMe": about_me,
            "learningCategory": learning_category,
            "difficulty": difficulty,
            "learningStyle": learning_style,
            "dailyGoal": daily_goal,
        })

        photo = request.files.get("photo")
        if photo and photo.filename:
            upload_folder = os.path.join(current_app.static_folder, "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            filename = secure_filename(f"{session['user_id']}_{photo.filename}")
            photo_path = os.path.join(upload_folder, filename)
            photo.save(photo_path)
            update_data["profilePhoto"] = os.path.join("uploads", filename).replace("\\", "/")

        User.update(session["user_id"], update_data)
        session["name"] = name
        return redirect(url_for("student.profile"))
    return render_template("profile.html", user=user)
