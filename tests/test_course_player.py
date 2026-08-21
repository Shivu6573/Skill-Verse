from services.course_player import extract_youtube_video_id, should_complete_lesson


def test_extract_youtube_video_id_from_watch_url():
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=abc123ABC12") == "abc123ABC12"


def test_extract_youtube_video_id_from_embed_url():
    assert extract_youtube_video_id("https://www.youtube.com/embed/xyz789XYZ12") == "xyz789XYZ12"


def test_should_complete_lesson_requires_full_progress_or_video_end():
    assert should_complete_lesson(1.0, 12, False) is True
    assert should_complete_lesson(0.99, 20, False) is False
    assert should_complete_lesson(0.90, 12, False) is False
    assert should_complete_lesson(0.50, 5, True) is True
