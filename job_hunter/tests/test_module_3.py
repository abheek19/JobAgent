import pytest
import asyncio
from datetime import datetime, timezone
import json
import csv

from schemas import DiscoveredJob, FilteredJob
from database import JobRepository
from filter.mock_evaluator import MockEvaluator
from filter.engine import FilterEngine
from filter.screener import JobFilterScreener

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_hunt.db"
    repository = JobRepository(db_path=str(db_path))
    yield repository

@pytest.fixture
def mock_evaluator():
    return MockEvaluator()

@pytest.fixture
def sample_jobs():
    return [
        DiscoveredJob(
            company="RustCorp",
            role="Systems Engineer",
            location="Remote",
            remote_hybrid="Remote",
            posted_timestamp=datetime.now(timezone.utc),
            url="https://rustcorp.com/job/1",
            required_experience="5 years",
            major_skills=["Rust", "C++"],
            source="Test"
        ),
        DiscoveredJob(
            company="LegacyBank",
            role="Mainframe Dev",
            location="NYC",
            remote_hybrid="On-site",
            posted_timestamp=datetime.now(timezone.utc),
            url="https://legacybank.com/job/2",
            required_experience="10 years",
            major_skills=["Cobol", "DB2"],
            source="Test"
        ),
        DiscoveredJob(
            company="QuantumAI",
            role="Quantum Computing Lead",
            location="SF",
            remote_hybrid="Remote",
            posted_timestamp=datetime.now(timezone.utc),
            url="https://quantumai.com/job/3",
            required_experience="10+ years",
            major_skills=["Physics", "Python"],
            source="Test"
        ),
        DiscoveredJob(
            company="PythonShop",
            role="Senior Python Developer",
            location="Remote",
            remote_hybrid="Remote",
            posted_timestamp=datetime.now(timezone.utc),
            url="https://pythonshop.com/job/4",
            required_experience="5 years",
            major_skills=["Python", "Django"],
            source="Test"
        ),
        DiscoveredJob(
            company="MediocreCorp",
            role="Mid-level Engineer",
            location="Remote",
            remote_hybrid="Remote",
            posted_timestamp=datetime.now(timezone.utc),
            url="https://mediocre.com/job/5",
            required_experience="3 years",
            major_skills=["Java"],
            source="Test"
        )
    ]

def test_mock_evaluator_anti_hallucination(mock_evaluator, sample_jobs):
    # Test Rust rejection
    rust_job = mock_evaluator.screen_job(sample_jobs[0])
    assert rust_job.classification == "Reject"
    assert "Rust is absent from Master CV." in rust_job.missing_qualifications
    
    # Test Cobol rejection
    cobol_job = mock_evaluator.screen_job(sample_jobs[1])
    assert cobol_job.classification == "Reject"
    assert "Cobol is absent from Master CV." in cobol_job.missing_qualifications
    
    # Test 10+ years Quantum Computing rejection
    quantum_job = mock_evaluator.screen_job(sample_jobs[2])
    assert quantum_job.classification == "Reject"
    assert "10+ years Quantum Computing is absent from Master CV." in quantum_job.missing_qualifications

def test_mock_evaluator_high_match(mock_evaluator, sample_jobs):
    python_job = mock_evaluator.screen_job(sample_jobs[3])
    assert python_job.classification == "High Match"
    assert not python_job.missing_qualifications

@pytest.mark.asyncio
async def test_filter_engine_execution(repo, mock_evaluator, sample_jobs, tmp_path):
    # Insert jobs into DB
    for job in sample_jobs:
        repo.insert_discovered_job(job)
        
    engine = FilterEngine(repo=repo, screener=mock_evaluator)
    
    counts = await engine.run()
    
    # We expect 3 Rejects, 1 High Match, 1 Possible Match
    assert counts["Reject"] == 3
    assert counts["High Match"] == 1
    assert counts["Possible Match"] == 1
    assert counts["Total"] == 5
    
    # Verify State Transitions in DB
    conn = repo._get_conn()
    cursor = conn.execute("SELECT status FROM jobs WHERE company = 'RustCorp'")
    assert cursor.fetchone()['status'] == 'REJECTED'
    
    cursor = conn.execute("SELECT status FROM jobs WHERE company = 'PythonShop'")
    assert cursor.fetchone()['status'] == 'HIGH_MATCH'
    
    cursor = conn.execute("SELECT status FROM jobs WHERE company = 'MediocreCorp'")
    assert cursor.fetchone()['status'] == 'POSSIBLE_MATCH'
    
    # Validate payload is set
    cursor = conn.execute("SELECT payload FROM jobs WHERE company = 'PythonShop'")
    payload = json.loads(cursor.fetchone()['payload'])
    assert payload['classification'] == 'High Match'
    
    # Sync to CSV test
    csv_path = tmp_path / "test_master.csv"
    repo.sync_to_csv(filepath=str(csv_path))
    
    assert csv_path.exists()
    with open(csv_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 5
        classifications = [r['classification'] for r in rows]
        assert 'High Match' in classifications
        assert 'Reject' in classifications
