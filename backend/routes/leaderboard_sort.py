def get_leaderboard_rank(students):
    def sort_key(u):
        return (
            -u.get('totalScore', 0),
            -len(u.get('completedCourses', []) or []),
            u.get('name', '').lower()
        )
    return sorted(students, key=sort_key)
