"""同一 project 下禁止并存多条未结束（非终态）的同名 Run。"""

import hashlib

import pytest

from app.cqrs import ConflictError, abort_run, complete_run, start_run


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _start(db, project="p1", name="n1"):
    return start_run(
        db,
        actor="researcher",
        project=project,
        name=name,
        dataset_content_sha256=sha(f"ds-{project}-{name}"),
        code_commit_sha="abc1234",
        description=None,
    )


def test_duplicate_name_rejected_while_running(db):
    _start(db, project="p1", name="n1")
    with pytest.raises(ConflictError) as exc_info:
        _start(db, project="p1", name="n1")
    assert exc_info.value.status_code == 409
    assert "同名" in exc_info.value.message


def test_same_name_allowed_after_complete(db):
    run = _start(db, project="p1", name="n1")
    complete_run(
        db,
        run_id=run.id,
        actor="researcher",
        result_summary="done",
        expected_version=run.version,
    )
    again = _start(db, project="p1", name="n1")
    assert again.id != run.id
    assert again.status == "running"


def test_same_name_allowed_after_abort(db):
    run = _start(db, project="p1", name="n1")
    abort_run(
        db,
        run_id=run.id,
        actor="researcher",
        reason="give up",
        expected_version=run.version,
    )
    again = _start(db, project="p1", name="n1")
    assert again.id != run.id
    assert again.status == "running"


def test_same_name_allowed_in_other_project(db):
    _start(db, project="p1", name="n1")
    other = _start(db, project="p2", name="n1")
    assert other.project == "p2"
    assert other.status == "running"


def test_different_name_same_project_allowed(db):
    _start(db, project="p1", name="n1")
    other = _start(db, project="p1", name="n2")
    assert other.name == "n2"
    assert other.status == "running"


def test_terminal_duplicate_does_not_block_new_terminal(db):
    """历史里可存在多条同名终态记录，仅未结束的同名互斥。"""
    run1 = _start(db, project="p1", name="n1")
    complete_run(
        db,
        run_id=run1.id,
        actor="researcher",
        result_summary="done",
        expected_version=run1.version,
    )
    run2 = _start(db, project="p1", name="n1")
    complete_run(
        db,
        run_id=run2.id,
        actor="researcher",
        result_summary="done again",
        expected_version=run2.version,
    )
    run3 = _start(db, project="p1", name="n1")
    assert run3.status == "running"
