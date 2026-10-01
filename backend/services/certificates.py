import base64
import os
import random
from datetime import datetime
from io import BytesIO

import qrcode


def generate_certificate_id():
    return f"SV-{random.randint(0, 9999999999):010d}"


def _format_completion_datetime(completion_datetime):
    if not completion_datetime:
        return {"date": datetime.utcnow().strftime("%Y-%m-%d"), "time": datetime.utcnow().strftime("%H:%M:%S")}
    if isinstance(completion_datetime, str):
        parsed = datetime.fromisoformat(completion_datetime.replace("Z", "+00:00"))
    else:
        parsed = completion_datetime
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return {"date": parsed.strftime("%Y-%m-%d"), "time": parsed.strftime("%H:%M:%S")}


def build_certificate_context(user, course, percentage=None, completion_datetime=None, issue_date=None, verification_url=None, instructor_name="Prof. Maya Chen", certificate_id=None):
    completed = _format_completion_datetime(completion_datetime)
    certificate_id_value = certificate_id or generate_certificate_id()
    issue_date_value = issue_date or datetime.utcnow().strftime("%Y-%m-%d")
    base_url = os.getenv("APP_BASE_URL") or "https://skillverse.example"
    verification_url_value = verification_url or f"{base_url.rstrip('/')}/certificate/verify/{certificate_id_value}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verification_url_value)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="#1f3b6d", back_color="white")
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")
    qr_code_data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "studentName": user.get("name") or "Learner",
        "courseName": course.get("title") or "Completed Course",
        "courseDuration": course.get("duration") or "Self-paced",
        "completionDate": completed["date"],
        "completionTime": completed["time"],
        "percentage": int(percentage) if percentage is not None else 100,
        "certificateId": certificate_id_value,
        "issueDate": issue_date_value,
        "instructorName": instructor_name,
        "verificationUrl": verification_url_value,
        "qrCodeDataUrl": qr_code_data_url,
    }
