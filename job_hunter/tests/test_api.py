import pytest
from fastapi.testclient import TestClient
import os
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).parent.parent))

from api.main import app
from config import get_settings

client = TestClient(app)

def test_config_bootstrapping():
    settings = get_settings()
    assert settings.app_env in ["development", "production", "test"]
    assert settings.gemini_api_key is not None
    # Ensure os.environ has the key, this was done by the model_validator
    assert os.environ.get("GEMINI_API_KEY") == settings.gemini_api_key

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "default_model_pro" in data
    assert "database_connected" in data

def test_ingest_job():
    payload = {
        "url": "https://example.com/job123",
        "company": "TestCorp",
        "role": "Backend Engineer",
        "location": "Remote",
        "salary": "$150k",
        "major_skills": ["Python", "FastAPI"],
        "required_experience": "3+ years"
    }
    response = client.post("/api/v1/jobs/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "job_id" in data

    # Test duplicate ingestion
    response2 = client.post("/api/v1/jobs/ingest", json=payload)
    assert response2.status_code == 400

def test_run_pipeline():
    payload = {
        "lane": "fast_lane",
        "custom_keywords": ["python", "ai"]
    }
    response = client.post("/api/v1/pipeline/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert "thread_id" in data
    assert data["lane"] == "fast_lane"

def test_pending_approvals():
    response = client.get("/api/v1/approvals/pending")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_approval_decision():
    # We use a dummy thread_id since the graph might not have one active,
    # but the API should accept it.
    thread_id = "dummy-thread-123"
    payload = {
        "decision": "APPROVE",
        "feedback": "Looks good"
    }
    response = client.post(f"/api/v1/approvals/{thread_id}/decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["thread_id"] == thread_id
    assert data["decision"] == "APPROVE"

def test_approval_decision_invalid():
    thread_id = "dummy-thread-123"
    payload = {
        "decision": "INVALID_DECISION",
    }
    response = client.post(f"/api/v1/approvals/{thread_id}/decision", json=payload)
    assert response.status_code == 422 # Unprocessable Entity due to Pydantic validation
