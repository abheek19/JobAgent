import pytest
import os
import json
from datetime import datetime, timezone
import csv
from pydantic import ValidationError

from schemas import DiscoveredJob, FilteredJob, ResearchedJob, generate_job_id, PipelineRecord
from database import JobRepository

@pytest.fixture
def test_db():
    db_path = "test_job_hunt.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    repo = JobRepository(db_path=db_path)
    yield repo
    if os.path.exists(db_path):
        repo._get_conn().close()
        try:
            os.remove(db_path)
            if os.path.exists(db_path + "-wal"):
                os.remove(db_path + "-wal")
            if os.path.exists(db_path + "-shm"):
                os.remove(db_path + "-shm")
        except Exception:
            pass

def test_discovered_job_schema_valid():
    job_data = {
        "company": "Google",
        "role": "Senior Engineer",
        "location": "Remote",
        "remote_hybrid": "Remote",
        "posted_timestamp": "2026-09-17T00:00:00Z",
        "salary": "$200k",
        "url": "https://careers.google.com/jobs/123",
        "required_experience": "5+ years",
        "major_skills": ["Python", "System Design"],
        "source": "Google Careers"
    }
    job = DiscoveredJob(**job_data)
    assert job.company == "Google"
    assert job.posted_timestamp.tzinfo is not None
    assert job.id == generate_job_id("https://careers.google.com/jobs/123/") or job.id == generate_job_id("https://careers.google.com/jobs/123")

def test_discovered_job_schema_invalid():
    with pytest.raises(ValidationError):
        DiscoveredJob(company="Google")

def test_db_idempotent_insert(test_db):
    job = DiscoveredJob(
        company="Google",
        role="Senior Engineer",
        location="Remote",
        remote_hybrid="Remote",
        posted_timestamp="2026-09-17T00:00:00Z",
        url="https://careers.google.com/jobs/123",
        required_experience="5+ years",
        major_skills=["Python"],
        source="Direct"
    )
    assert test_db.insert_discovered_job(job) is True
    assert test_db.insert_discovered_job(job) is False
    
    conn = test_db._get_conn()
    count = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
    assert count == 1

def test_db_state_transitions(test_db):
    job = DiscoveredJob(
        company="Apple",
        role="Architect",
        location="Cupertino",
        remote_hybrid="Hybrid",
        posted_timestamp="2026-09-17T00:00:00Z",
        url="https://apple.com/jobs/456",
        required_experience="10+ years",
        major_skills=["Swift", "Architecture"],
        source="Apple Careers"
    )
    test_db.insert_discovered_job(job)
    
    test_db.update_job_status(job.id, "SCREENED")
    pending = test_db.get_pending_jobs("SCREENED")
    assert len(pending) == 1
    assert pending[0]['status'] == "SCREENED"
    
    with pytest.raises(ValueError):
        test_db.update_job_status(job.id, "APPLIED")
        
    test_db.update_job_status(job.id, "HIGH_MATCH")
    test_db.update_job_status(job.id, "APP_READY")
    test_db.update_job_status(job.id, "APPROVED")
    test_db.update_job_status(job.id, "APPLIED")
    test_db.update_job_status(job.id, "INTERVIEW")
    test_db.update_job_status(job.id, "OFFER")

def test_db_sync_to_csv(test_db):
    csv_path = "test_export.csv"
    if os.path.exists(csv_path):
        os.remove(csv_path)
        
    job = DiscoveredJob(
        company="Netflix",
        role="Data Engineer",
        location="Los Gatos",
        remote_hybrid="On-site",
        posted_timestamp="2026-09-17T00:00:00Z",
        url="https://netflix.com/jobs/789",
        required_experience="3+ years",
        major_skills=["Python", "Spark"],
        source="LinkedIn"
    )
    test_db.insert_discovered_job(job)
    test_db.update_job_status(job.id, "SCREENED", payload={"classification": "High Match"})
    
    test_db.sync_to_csv(csv_path)
    
    assert os.path.exists(csv_path)
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]['company'] == "Netflix"
        assert rows[0]['status'] == "SCREENED"
        assert rows[0]['classification'] == "High Match"
        assert 'url' in rows[0]
        
    if os.path.exists(csv_path):
        os.remove(csv_path)
