import os
import sys
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import requests
except ImportError:
    print('ERROR: requests library is required. Install with: pip install requests')
    sys.exit(1)

search_terms = [
    ('Cloud Computing with AWS', 'AWS full course 2024'),
    ('Software Testing Fundamentals', 'software testing fundamentals full course'),
    ('Selenium with Java Automation Testing', 'Selenium Java full course'),
    ('Data Analytics with Excel & Power BI', 'Power BI full course Excel data analytics'),
    ('Microsoft Power BI Dashboard Development', 'Power BI dashboard tutorial full course'),
    ('IT Technical Support Fundamentals', 'IT support fundamentals full course'),
    ('Computer Networking (CCNA Basics)', 'CCNA basics full course'),
    ('Cyber Security Essentials', 'cyber security fundamentals full course'),
    ('DevOps with Docker & Jenkins', 'DevOps Docker Jenkins full course'),
    ('Microsoft Azure Fundamentals (AZ-900)', 'Azure fundamentals AZ-900 full course')
]

ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

print('Searching YouTube and validating candidate video IDs...')
print()

for label, query in search_terms:
    print('===', label, '===')
    encoded = requests.utils.requote_uri(query)
    search_url = f'https://www.youtube.com/results?search_query={encoded}'
    try:
        r = requests.get(search_url, headers={'User-Agent': ua}, timeout=20)
        html = r.text
        ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
        seen = []
        for vid in ids:
            if vid not in seen:
                seen.append(vid)
            if len(seen) >= 10:
                break
        for vid in seen:
            check_url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json'
            try:
                check = requests.get(check_url, headers={'User-Agent': ua}, timeout=15)
                status = check.status_code
                title = None
                if status == 200:
                    title = check.json().get('title')
                print(f'  {vid} -> {status} {"OK" if status == 200 else "BAD"}', title if title else '')
            except Exception as exc:
                print(f'  {vid} -> EXCEPTION {exc}')
    except Exception as exc:
        print('  search failed:', exc)
    print()
