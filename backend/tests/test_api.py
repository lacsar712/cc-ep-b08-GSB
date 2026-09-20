"""API 层：创建接口的鉴权（审计员/未登录拒绝）与同名未结束 Run 冲突（409）。"""

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import router
from app.database import Base, get_db


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _login(client: TestClient, username: str, password: str) -> dict:
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _payload(project="p1", name="n1") -> dict:
    return {
        "project": project,
        "name": name,
        "dataset_content_sha256": sha(f"ds-{project}-{name}"),
        "code_commit_sha": "abc1234",
        "description": None,
        "expected_version": 0,
    }


def test_auditor_cannot_create_run(client):
    headers = _login(client, "auditor", "audit123456")
    res = client.post("/api/runs", json=_payload(), headers=headers)
    assert res.status_code == 403


def test_unauthenticated_create_rejected(client):
    res = client.post("/api/runs", json=_payload())
    assert res.status_code == 401


def test_duplicate_running_name_conflict_then_reuse_after_complete(client):
    headers = _login(client, "researcher", "lab123456")

    created = client.post("/api/runs", json=_payload(), headers=headers)
    assert created.status_code == 201
    run = created.json()

    # 进行中：同名再建 → 409，且响应里带原因
    dup = client.post("/api/runs", json=_payload(), headers=headers)
    assert dup.status_code == 409
    assert "同名" in dup.json()["detail"]

    # 旧记录完成后：同名可再建
    done = client.post(
        f"/api/runs/{run['id']}/complete",
        json={"result_summary": "ok", "expected_version": run["version"]},
        headers=headers,
    )
    assert done.status_code == 200

    again = client.post("/api/runs", json=_payload(), headers=headers)
    assert again.status_code == 201
    assert again.json()["id"] != run["id"]


def test_duplicate_running_name_conflict_then_reuse_after_abort(client):
    headers = _login(client, "researcher", "lab123456")

    created = client.post("/api/runs", json=_payload(), headers=headers)
    assert created.status_code == 201
    run = created.json()

    dup = client.post("/api/runs", json=_payload(), headers=headers)
    assert dup.status_code == 409

    aborted = client.post(
        f"/api/runs/{run['id']}/abort",
        json={"reason": "no longer needed", "expected_version": run["version"]},
        headers=headers,
    )
    assert aborted.status_code == 200

    again = client.post("/api/runs", json=_payload(), headers=headers)
    assert again.status_code == 201
    assert again.json()["id"] != run["id"]


def test_auditor_can_still_read_runs(client):
    researcher = _login(client, "researcher", "lab123456")
    created = client.post("/api/runs", json=_payload(), headers=researcher)
    assert created.status_code == 201

    auditor = _login(client, "auditor", "audit123456")
    res = client.get("/api/runs", headers=auditor)
    assert res.status_code == 200
    assert len(res.json()) == 1
