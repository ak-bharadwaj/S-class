import sys; sys.path.insert(0, '.'); sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from planner import MetaPlanner, WorkflowProfile
p = MetaPlanner()
for goal, expected in [
    ('Fix typo in README.md', 'MICRO'),
    ('Why is my build failing?', 'QUESTION'),
    ('Fix the login button not working on mobile', 'BUG_FIX'),
    ('Refactor the entire auth system', 'FULL'),
    ('Build a full e-commerce platform with payments', 'FULL'),
    ('Rename variable foo to bar in utils.py', 'MICRO'),
    ('Fix typo in login.py', 'MICRO'),
    ('Add CSRF token to forms', 'SMALL_FIX'),
    ('', 'QUESTION'),
]:
    result = p.classify_goal(goal)
    actual = result.profile.name
    status = 'PASS' if actual == expected else 'FAIL'
    print(f'[{status}] "{goal}" -> {actual} (expected {expected})')
