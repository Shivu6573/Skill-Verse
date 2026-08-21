import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import requests
except ImportError:
    print('ERROR: requests library is required. Install with: pip install requests')
    sys.exit(1)

from models.course import COURSE_DATA

print(f'Checking {len(COURSE_DATA)} course video IDs...')
print()

results = []
for idx, (title, category, difficulty, duration, description, youtube_id) in enumerate(COURSE_DATA, 1):
    url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={youtube_id}&format=json'
    try:
        response = requests.get(url, timeout=15)
        status = response.status_code
        if status == 200:
            data = response.json()
            valid = True
            error = None
            video_title = data.get('title')
        else:
            valid = False
            error = response.text.strip()[:200]
            video_title = None
    except Exception as exc:
        valid = False
        error = repr(exc)
        video_title = None

    results.append({
        'index': idx,
        'course_title': title,
        'youtube_id': youtube_id,
        'valid': valid,
        'status': status if valid else None,
        'video_title': video_title,
        'error': error,
    })

for result in results:
    print(f"{result['index']:02d}. {result['course_title']} ({result['youtube_id']}) -> {'OK' if result['valid'] else 'BROKEN'}")
    if result['valid']:
        print(f"    video_title: {result['video_title']}")
    else:
        print(f"    error: {result['error']}")

broken = [r for r in results if not r['valid']]
print()
print(f'Total courses checked: {len(results)}')
print(f'Broken videos: {len(broken)}')
if broken:
    print('Broken course IDs:')
    for r in broken:
        print(f"  - {r['course_title']}: {r['youtube_id']} -> {r['error']}")
