from flask import Blueprint, request, jsonify, session
import json
import os
import time
import traceback
import requests

api_bp = Blueprint("api", __name__)


def _get_openai_key():
    return os.getenv("OPENAI_API_KEY", "").strip()


def _get_gemini_key():
    return os.getenv("GEMINI_API_KEY", "").strip()


def _extract_error_message(payload):
    if isinstance(payload, dict):
        error = payload.get("error", {})
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return str(message)
        return str(payload)
    return str(payload)


def _is_rate_limit_error(status_code, error_message):
    message = (error_message or "").lower()
    return status_code == 429 or "rate limit" in message or "quota" in message or "resource_exhausted" in message or "too many requests" in message


def _build_gemini_prompt(message, history, course_context):
    conversation_text = "\n\n".join(
        [f"{item.get('role', 'user').title()}: {item.get('content', '')}" for item in history[-8:]]
    )
    return f"""You are EduBot, a helpful AI tutor for the Skill Verse platform.
Answer the user's latest question directly and naturally.
Use the conversation history for context when relevant.
Do not use hardcoded templates or canned replies.
Support any topic, including coding, debugging, software testing, interviews, math, writing, general knowledge, and motivation.
If the user asks for courses or learning paths, recommend them clearly and helpfully.
Respond in complete, detailed, natural language with markdown formatting when useful.

Conversation history:
{conversation_text}

Current user message:
{message}

Course context:
{course_context}"""


def _build_course_context():
    try:
        from models.course import Course
        courses = Course.all()[:12]
    except Exception:
        return ""

    if not courses:
        return ""

    course_lines = []
    for course in courses:
        title = course.get("title", "")
        category = course.get("category", "")
        difficulty = course.get("difficulty", "")
        if title:
            course_lines.append(f"- {title} ({category}, {difficulty})")

    if not course_lines:
        return ""

    return "Platform course catalog:\n" + "\n".join(course_lines)


def _build_user_context(message, history):
    parts = [message]
    for item in history[-6:]:
        if isinstance(item, dict):
            content = item.get("content", "")
            if content:
                parts.append(str(content))
    return " ".join(part for part in parts if part).strip()


def _call_gemini_api(gemini_key, system_prompt, message, messages):
    if not gemini_key:
        return None, "Invalid or missing Gemini API key."

    conversation_text = "\n\n".join(
        [f"{item.get('role', 'user').title()}: {item.get('content', '')}" for item in messages]
    )
    gemini_payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\nConversation:\n{conversation_text}\n\nUser: {message}"}]
        }],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500},
    }

    for attempt in range(3):
        try:
            print(f"Gemini request payload (attempt {attempt + 1}/3): {json.dumps(gemini_payload, ensure_ascii=False)}")
            gemini_resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json=gemini_payload,
                timeout=30,
            )

            print(f"Gemini response status (attempt {attempt + 1}/3): {gemini_resp.status_code}")
            print(f"Gemini response body (attempt {attempt + 1}/3): {gemini_resp.text}")

            if gemini_resp.status_code == 200:
                gemini_result = gemini_resp.json()
                candidates = gemini_result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    reply = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                    if reply:
                        return reply, None

            try:
                gemini_error = gemini_resp.json()
            except ValueError:
                gemini_error = {"error": {"message": gemini_resp.text}}

            error_message = _extract_error_message(gemini_error)
            print(f"Gemini API error (attempt {attempt + 1}/3): {gemini_resp.status_code} - {error_message}")

            if gemini_resp.status_code in {400, 401, 403, 404}:
                return None, "Invalid or missing Gemini API key."

            if _is_rate_limit_error(gemini_resp.status_code, error_message):
                if attempt < 2:
                    wait_time = 2 ** attempt
                    print(f"Gemini rate-limit hit. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                return None, "The AI service is temporarily unavailable. Please try again in a few minutes."

            if gemini_resp.status_code >= 500:
                return None, "The AI service is temporarily unavailable. Please try again in a few minutes."

            return None, f"The Gemini service returned an error: {error_message}"
        except requests.Timeout as exc:
            print(f"Gemini API timeout (attempt {attempt + 1}/3): {exc}")
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return None, "The AI service is temporarily unavailable. Please try again in a few minutes."
        except requests.RequestException as exc:
            print(f"Gemini API request exception (attempt {attempt + 1}/3): {exc}")
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return None, "The AI service is temporarily unavailable. Please try again in a few minutes."
        except Exception as exc:
            print(f"Unexpected Gemini error (attempt {attempt + 1}/3): {exc}")
            traceback.print_exc()
            return None, "The AI service is temporarily unavailable. Please try again in a few minutes."

    return None, "The AI service is temporarily unavailable. Please try again in a few minutes."


def _call_openai_api(openai_key, system_prompt, message, messages):
    if not openai_key:
        return None, "Invalid or missing OpenAI API key."

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": system_prompt}] + [
            {"role": item.get("role", "user"), "content": item.get("content", "")} for item in messages
        ],
        "temperature": 0.7,
        "max_tokens": 500,
    }

    try:
        print(f"OpenAI request payload: {json.dumps(payload, ensure_ascii=False)}")
        openai_resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai_key}",
            },
            json=payload,
            timeout=30,
        )
        print(f"OpenAI response status: {openai_resp.status_code}")
        print(f"OpenAI response body: {openai_resp.text}")

        if openai_resp.status_code == 200:
            openai_result = openai_resp.json()
            choices = openai_result.get("choices", [])
            if choices:
                reply = choices[0].get("message", {}).get("content", "")
                if reply:
                    return reply, None

        try:
            error_payload = openai_resp.json()
        except ValueError:
            error_payload = {"error": {"message": openai_resp.text}}
        error_message = _extract_error_message(error_payload)
        print(f"OpenAI API error: {openai_resp.status_code} - {error_message}")

        if openai_resp.status_code in {400, 401, 403, 404}:
            return None, "Invalid or missing OpenAI API key."
        if _is_rate_limit_error(openai_resp.status_code, error_message):
            return None, "The AI service is temporarily unavailable. Please try again in a few minutes."
        if openai_resp.status_code >= 500:
            return None, "The AI service is temporarily unavailable. Please try again in a few minutes."
        return None, f"The OpenAI service returned an error: {error_message}"
    except requests.Timeout as exc:
        print(f"OpenAI API timeout: {exc}")
        return None, "The AI service is temporarily unavailable. Please try again in a few minutes."
    except requests.RequestException as exc:
        print(f"OpenAI API request exception: {exc}")
        return None, "The AI service is temporarily unavailable. Please try again in a few minutes."
    except Exception as exc:
        print(f"Unexpected OpenAI error: {exc}")
        traceback.print_exc()
        return None, "The AI service is temporarily unavailable. Please try again in a few minutes."


# Debug endpoint to verify the server is configured without exposing the key
@api_bp.route("/debug-keys", methods=["GET"])
def debug_keys():
    return jsonify({
        "openai_configured": bool(_get_openai_key()),
        "gemini_configured": bool(_get_gemini_key())
    })


@api_bp.route("/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return jsonify({"reply": "Please log in to use the chatbot."}), 401

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"reply": "Please enter a message."}), 400

    course_context = _build_course_context()
    system_prompt = _build_gemini_prompt(message, history, course_context)

    print(f"Chat request received: {message}")
    print(f"Chat history length: {len(history)}")
    messages = history + [{"role": "user", "content": message}]
    gemini_key = _get_gemini_key()
    openai_key = _get_openai_key()

    if not gemini_key and not openai_key:
        return jsonify({"reply": "The Gemini API is not configured. Please set GEMINI_API_KEY or OPENAI_API_KEY before using the chatbot."}), 503

    try:
        reply = None
        error_message = None
        if gemini_key:
            reply, error_message = _call_gemini_api(gemini_key, system_prompt, message, messages)
        elif openai_key:
            reply, error_message = _call_openai_api(openai_key, system_prompt, message, messages)

        if reply:
            print(f"Chatbot reply generated: {reply}")
            return jsonify({"reply": reply}), 200
        if error_message:
            print(f"Chatbot error response: {error_message}")
            return jsonify({"reply": error_message}), 200
        return jsonify({"reply": "Gemini did not return any content."}), 200
    except Exception as exc:
        print(f"Chatbot unexpected error: {exc}")
        traceback.print_exc()
        return jsonify({"reply": str(exc)}), 500
