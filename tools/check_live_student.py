"""Read-only post-deploy check: renders student pages through the Flask test client.

Run on the server from the project root:

    ~/.virtualenvs/edu-math/bin/python tools/check_live_student.py

Sessions are created directly in the test client (no passwords, no writes).
"""
import os
import sys
from pathlib import Path

HOME = Path.home()
ROOT = HOME / "edu-math"
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SECRET_KEY", "check-only")

from app import app  # noqa: E402
from database import query_one  # noqa: E402

student = query_one(
    "SELECT id, first_name, last_name FROM users WHERE role = 'student' ORDER BY id LIMIT 1"
)
if not student:
    print("NO_STUDENT")
    raise SystemExit(2)


def path_for(endpoint: str) -> str:
    return str(next(rule for rule in app.url_map.iter_rules() if rule.endpoint == endpoint))


with app.test_client() as client:
    with client.session_transaction() as sess:
        sess["user_id"] = int(student["id"])
        sess.permanent = True

    for endpoint, marker in (
        ("student.dashboard", "от "),
        ("student.works", "от "),
        ("student.schedule", "<"),
        ("notifications.page", "Уведомления"),
    ):
        try:
            path = path_for(endpoint)
        except StopIteration:
            print(endpoint, "NO_ROUTE")
            continue
        response = client.get(path)
        html = response.get_data(as_text=True)
        print(
            endpoint,
            path,
            "status=" + str(response.status_code),
            "len=" + str(len(html)),
            "has_teacher=" + str("от учителя" in html),
            "has_parent=" + str("от родителя" in html),
            "marker=" + str(marker in html),
        )
