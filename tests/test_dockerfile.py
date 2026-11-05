"""Container hygiene the Dockerfile must keep.

These read the Dockerfile, so they run without Docker. CI's docker job checks the same things
on a running container (uid, health status, a write to the SQLite database).
"""

import re
from pathlib import Path

DOCKERFILE = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
# One entry per instruction: comments dropped, "\" continuation lines joined as Docker does.
LINES = [
    line.strip() for line in re.sub(r"\\\n", " ", DOCKERFILE).splitlines() if line.strip() and not line.lstrip().startswith("#")
]


def instructions(name: str) -> list[str]:
    return [line.split(None, 1)[1] for line in LINES if line.split(None, 1)[0] == name]


def test_final_user_is_numeric_and_not_root():
    # A numeric uid:gid lets Kubernetes' runAsNonRoot verify the image; a name like "app" can't be checked.
    uid, _, gid = instructions("USER")[-1].partition(":")
    assert uid.isdigit() and int(uid) != 0
    assert gid.isdigit() and int(gid) != 0


def test_user_is_switched_after_everything_that_needs_root():
    last_user = max(i for i, line in enumerate(LINES) if line.startswith("USER "))
    last_run = max(i for i, line in enumerate(LINES) if line.startswith("RUN "))
    assert last_run < last_user


def test_the_database_directory_belongs_to_the_runtime_user():
    uid_gid = instructions("USER")[-1]
    assert re.search(rf"chown\s+{re.escape(uid_gid)}\s+/app/data\b", DOCKERFILE)
    assert "DATABASE_PATH=/app/data/" in DOCKERFILE


def test_healthcheck_calls_the_health_endpoint_with_a_start_period():
    (check,) = instructions("HEALTHCHECK")
    assert "/health" in check
    assert "--start-period=" in check and "--timeout=" in check
