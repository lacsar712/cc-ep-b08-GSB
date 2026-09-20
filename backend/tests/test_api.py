import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import router
from app.database import Base, get_db
from app.main import app


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, compiler, **kw):
    return "JSON"


@pytest.fixture()
def client():
    import app.main as main_mod

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    # lifespan 中 create_all 用的是 main 模块导入时绑定的 engine
    original_engine = main_mod.engine
    main_mod.engine = engine

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        main_mod.engine = original_engine
        engine.dispose()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture()
def researcher_token(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "researcher", "password": "lab123456"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture()
def auditor_token(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "auditor", "password": "audit123456"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _body(name: str, dataset_seed: str = "ds") -> dict:
    return {
        "project": "p1",
        "name": name,
        "dataset_content_sha256": sha(dataset_seed),
        "code_commit_sha": "abc1234",
        "description": None,
        "expected_version": 0,
    }


def test_duplicate_running_name_returns_409(client, researcher_token):
    headers = {"Authorization": f"Bearer {researcher_token}"}
    resp1 = client.post("/api/runs", json=_body("dup", "a"), headers=headers)
    assert resp1.status_code == 201

    resp2 = client.post("/api/runs", json=_body("dup", "b"), headers=headers)
    assert resp2.status_code == 409
    assert "dup" in resp2.json()["detail"]


def test_same_name_reuse_after_complete_returns_201(client, researcher_token):
    headers = {"Authorization": f"Bearer {researcher_token}"}
    resp1 = client.post("/api/runs", json=_body("reuse", "a"), headers=headers)
    run_id = resp1.json()["id"]
    version = resp1.json()["version"]

    done = client.post(
        f"/api/runs/{run_id}/complete",
        json={"result_summary": "done", "expected_version": version},
        headers=headers,
    )
    assert done.status_code == 200

    resp2 = client.post("/api/runs", json=_body("reuse", "b"), headers=headers)
    assert resp2.status_code == 201
    assert resp2.json()["id"] != run_id


def test_auditor_cannot_create_run(client, auditor_token):
    headers = {"Authorization": f"Bearer {auditor_token}"}
    resp = client.post("/api/runs", json=_body("x"), headers=headers)
    assert resp.status_code == 403


def test_unauthenticated_cannot_create_run(client):
    resp = client.post("/api/runs", json=_body("x"))
    assert resp.status_code == 401
