from services.certificates import build_certificate_context, generate_certificate_id


def test_generate_certificate_id_has_expected_format():
    certificate_id = generate_certificate_id()
    assert certificate_id.startswith("SV-")
    assert len(certificate_id.split("-")[1]) == 10
    assert certificate_id.split("-")[1].isdigit()


def test_build_certificate_context_populates_certificate_fields():
    user = {"name": "Alice Johnson"}
    course = {"title": "Python for Data Science", "duration": "6 hours"}

    context = build_certificate_context(
        user,
        course,
        percentage=96,
        completion_datetime="2026-07-25 14:35:20",
        issue_date="2026-07-25",
        verification_url="https://skillverse.example/certificate/verify/SV-1234567890",
    )

    assert context["studentName"] == "Alice Johnson"
    assert context["courseName"] == "Python for Data Science"
    assert context["courseDuration"] == "6 hours"
    assert context["percentage"] == 96
    assert context["completionDate"] == "2026-07-25"
    assert context["completionTime"] == "14:35:20"
    assert context["certificateId"].startswith("SV-")
    assert context["qrCodeDataUrl"].startswith("data:image/png;base64,")
