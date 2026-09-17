import os
import pytest
import sqlite3
import csv
import json
from datetime import datetime, timezone

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from schemas import DiscoveredJob, ResearchedJob, NetworkLead
from database import JobRepository
from investigator.engine import DeepeningEngine
from investigator.mock_deepener import MockCompanyInvestigator, MockNetworkScout

@pytest.fixture
def test_db_path(tmp_path):
    db_path = tmp_path / "test_job_hunt.db"
    yield str(db_path)

@pytest.fixture
def repo(test_db_path):
    return JobRepository(db_path=test_db_path)

@pytest.fixture
def csv_path(tmp_path):
    return str(tmp_path / "test_master.csv")

def insert_test_job(repo, status, company, role, url="https://example.com/job"):
    job = DiscoveredJob(
        company=company,
        role=role,
        location="Remote",
        remote_hybrid="Remote",
        posted_timestamp=datetime.now(timezone.utc),
        salary="$100k-$150k",
        url=url,
        required_experience="3+ years",
        major_skills=["Python"],
        source="Test"
    )
    repo.insert_discovered_job(job)
    # Transition to requested status
    if status != "DISCOVERED":
        repo.update_job_status(job.id, "SCREENED")
        if status not in ("SCREENED", "REJECTED"):
            repo.update_job_status(job.id, status)
    return job.id

@pytest.mark.asyncio
async def test_deepening_engine_parallelism_and_sync(repo, test_db_path, csv_path):
    # Insert a few jobs
    job1_id = insert_test_job(repo, "HIGH_MATCH", "Google", "Engineer", "https://google.com/1")
    job2_id = insert_test_job(repo, "HIGH_MATCH", "Apple", "Developer", "https://apple.com/2")
    job3_id = insert_test_job(repo, "POSSIBLE_MATCH", "Microsoft", "Dev", "https://ms.com/3") # Should be skipped
    job4_id = insert_test_job(repo, "REJECTED", "Amazon", "Coder", "https://amazon.com/4") # Should be skipped
    
    mock_inv = MockCompanyInvestigator()
    mock_scout = MockNetworkScout()
    
    engine = DeepeningEngine(
        db_path=test_db_path,
        max_concurrent=5,
        investigator=mock_inv,
        scout=mock_scout
    )
    
    # Run engine
    await engine.run()
    
    # Check SQLite payload for job1
    conn = repo._get_conn()
    cursor = conn.execute('SELECT payload FROM jobs WHERE id = ?', (job1_id,))
    row = cursor.fetchone()
    payload = json.loads(row['payload'])
    
    assert 'research' in payload
    assert payload['research']['company'] == "Google"
    assert 'network_lead' in payload
    assert payload['contact_name'] == "Jane Doe"
    assert payload['contact_found'] == "Yes"
    
    # Check job3 (POSSIBLE_MATCH) - should NOT have research
    cursor = conn.execute('SELECT payload FROM jobs WHERE id = ?', (job3_id,))
    row = cursor.fetchone()
    payload3 = json.loads(row['payload'])
    assert 'research' not in payload3
    
    # Sync to CSV and verify
    repo.sync_to_csv(filepath=csv_path)
    
    # Check CSV contents
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        # Find job1
        job1_csv = next(r for r in rows if r['job_id'] == job1_id)
        assert job1_csv['contact_name'] == "Jane Doe"
        assert job1_csv['contact_found'] == "Yes"
        
        # Find job3
        job3_csv = next(r for r in rows if r['job_id'] == job3_id)
        assert job3_csv['contact_name'] == ""
        assert job3_csv['contact_found'] == ""

def test_schema_compliance():
    # Verify the schemas validate correctly
    rj = ResearchedJob(
        job_id="123",
        company="Test Co",
        business_summary="Summary",
        recent_developments="Devs",
        hiring_context="Hiring",
        source_links=["https://example.com"]
    )
    assert rj.company == "Test Co"
    
    nl = NetworkLead(
        job_id="123",
        contact_name="John",
        contact_role="Recruiter",
        profile_url="https://linkedin.com/in/john",
        relevance_reasoning="He recruits",
        drafted_outreach_message="Hi John"
    )
    assert nl.contact_name == "John"
