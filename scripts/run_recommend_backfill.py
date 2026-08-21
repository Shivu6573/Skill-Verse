"""Run recommendation backfill for a single user.

Usage:
  python scripts/run_recommend_backfill.py --user <user_id>

Requires: set GEMINI_API_KEY and GEMINI_MODEL env vars when calling real Gemini.
This script will call the same backfill used by the web endpoints and print results.
"""
import os
import sys
import argparse

from app import create_app  # ensure factory exists or import app directly
from models.user import User

def main(user_id):
    # Import inside function to avoid top-level app import side-effects
    try:
        from routes import student as student_routes
    except Exception:
        import routes.student as student_routes

    app = create_app() if hasattr(__import__('app'), 'create_app') else __import__('app').app
    with app.app_context():
        user = User.find_by_id(user_id)
        if not user:
            print("User not found:", user_id)
            return 1
        print("Running backfill for user:", user.get('name') or user_id)
        new_recs, errors = student_routes._generate_missing_course_recommendations(user)
        print("New recommendations generated:", len(new_recs))
        for r in new_recs:
            print("-", r.get('title'))
        if errors:
            print("Errors:")
            for cid, msg in errors.items():
                print(f" {cid}: {msg}")
        else:
            print("No errors reported.")
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', required=True, help='User id to run backfill for')
    args = parser.parse_args()
    sys.exit(main(args.user))
