import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.classify import classify, detect_language, detect_role, resolve_role

KIND_CASES = [
    ("Write a function that reverses a linked list.", "coding"),
    ("Can you write a SQL query to find the second highest salary?", "coding"),
    ("Given a string s, return true if it is a palindrome.", "coding"),
    ("What is the difference between a list and a tuple in Python?", "technical"),
    ("How does Docker differ from a virtual machine?", "technical"),
    ("How would you design a URL shortener for millions of users?", "system_design"),
    ("Tell me about a time you had a conflict with a coworker.", "behavioral"),
    ("How do you handle tight deadlines?", "behavioral"),
    ("Tell me about yourself.", "general"),
    ("Why do you want to work here?", "general"),
]

ROLE_CASES = [
    ("Anna Lee (CTO) 10:31 AM", "cto"),
    ("Mark - Technical Lead", "tech_lead"),
    ("Sarah, Talent Acquisition", "recruiter"),
    ("John Smith", None),
]

LANGUAGE_CASES = [
    ("Write a function in Java to sort an array.", "Java"),
    ("Solve it in JavaScript.", "JavaScript"),
    ("Write a SQL query for the top 3 users.", "SQL"),
    ("Implement a stack in C++.", "C++"),
    ("Reverse a string.", None),
]


def run(verbose=True):
    failures = []
    for text, expected in KIND_CASES:
        got = classify(text)
        if got != expected:
            failures.append(f"type: {text!r} -> {got} (expected {expected})")
    for text, expected in ROLE_CASES:
        got = detect_role(text)
        if got != expected:
            failures.append(f"role: {text!r} -> {got} (expected {expected})")
    for text, expected in LANGUAGE_CASES:
        got = detect_language(text)
        if got != expected:
            failures.append(f"language: {text!r} -> {got} (expected {expected})")
    if resolve_role("auto", "coding") != "tech_lead" or resolve_role("auto", "system_design") != "cto":
        failures.append("resolve_role auto mapping is wrong")
    if resolve_role("auto", "coding", "recruiter") != "recruiter" or resolve_role("cto", "general") != "cto":
        failures.append("resolve_role priority is wrong")
    if verbose:
        for f in failures:
            print("FAIL", f)
        total = len(KIND_CASES) + len(ROLE_CASES) + len(LANGUAGE_CASES) + 2
        print(f"{total - len(failures)}/{total} passed")
    return failures


def test_classify():
    assert run(verbose=False) == []


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
