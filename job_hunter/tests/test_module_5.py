import pytest
import asyncio
import json
import os
import sys
import sqlite3
import csv

# Add the parent directory to sys.path so we can import from the root module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import JobRepository
from schemas import DiscoveredJob, ResearchedJob, TailoredMaterial
from tailor.mock_tailor import MockApplicationTailor
from tailor.engine import TailoringEngine

@pytest.fixture
def mock_db_path(tmp_path):
    db_file = tmp_path / "test_job_hunt.db"
    return str(db_file)

@pytest.fixture
def repo(mock_db_path):
    # Initialize repository on temp DB
    return JobRepository(db_path=mock_db_path)

@pytest.fixture
def setup_test_data(repo):
    # Insert a dummy job
    job = DiscoveredJob(
        id="test_job_1",
        url="https://example.com/job1",
        company="Test Corp",
        role="Senior Engineer",
        location="Remote",
        salary="150k",
        remote_hybrid="Remote",
        posted_timestamp="2023-01-01T10:00:00Z",
        required_experience="5 years",
        major_skills=["Python", "AWS"],
        source="LinkedIn"
    )
    repo.insert_discovered_job(job)
    
    # Progress it to HIGH_MATCH and add research data to payload
    research = ResearchedJob(
        job_id=job.id,
        company=job.company,
        business_summary="A cool company",
        recent_developments="Launched a new AI product",
        hiring_context="Expanding team",
        source_links=["https://example.com/news"]
    )
    
    payload = job.model_dump(mode='json')
    payload.update(research.model_dump(mode='json'))
    
    # We must transition through valid states
    repo.update_job_status(job.id, "SCREENED", payload)
    repo.update_job_status(job.id, "HIGH_MATCH", payload)
    
    return job

@pytest.mark.asyncio
async def test_module_5_tailoring(repo, setup_test_data, mock_db_path):
    # Use mock tailor
    tailor = MockApplicationTailor()
    engine = TailoringEngine(tailor_agent=tailor, max_concurrent=1, db_path=mock_db_path)
    
    # Override Master CV path to use the real one in job_hunter root
    master_cv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "master_cv_template.json")
    with open(master_cv_path, "r", encoding="utf-8") as f:
        engine.master_cv = json.load(f)

    # Run engine
    metrics = await engine.run()
    
    # Validate metrics
    assert metrics["total_tailored"] == 1
    assert metrics["adherence_flags_passed"] == 1
    
    # Validate state transition
    pending = repo.get_pending_jobs("APP_READY")
    assert len(pending) == 1
    
    # Validate payload has TailoredMaterial
    payload = pending[0]['payload']
    assert 'tailored_cv_diff' in payload
    assert 'tailored_cover_letter' in payload
    assert 'adherence_guarantee' in payload
    assert payload['cv_prepared'] == "Yes"
    
    # Anti-hallucination verification
    # Assert that the CV diff contains Python and AWS but not made-up tech like "QuantumComputing"
    cv_diff = payload['tailored_cv_diff']
    assert "Python" in cv_diff
    assert "AWS" in cv_diff
    assert "QuantumComputing" not in cv_diff

    # Validate dashboard projection in CSV
    csv_path = "Job-Hunt-Master.csv"
    assert os.path.exists(csv_path)
    
    found = False
    with open(csv_path, "r", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['job_id'] == "test_job_1":
                assert row['status'] == "APP_READY"
                assert row['cv_prepared'] == "Yes"
                found = True
                break
    
    assert found
