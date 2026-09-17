import pytest
import asyncio
import os
import sqlite3
from typing import Dict, Any

from schemas import DiscoveredJob
from database import JobRepository
from scouts.engine import DiscoveryEngine
from scouts.mock_feed import get_mock_jobs

@pytest.fixture
def test_db():
    # Use a file-based DB for concurrent test to accurately test WAL
    db_path = "test_module_2_jobs.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass
    
    repo = JobRepository(db_path=db_path)
    yield repo
    
    # Close connection
    if hasattr(repo._local, 'conn'):
        repo._local.conn.close()
        
    # Cleanup
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass
    if os.path.exists("Job-Hunt-Master.csv"):
        try:
            os.remove("Job-Hunt-Master.csv")
        except PermissionError:
            pass

def test_schema_compliance():
    # Fetch mock jobs and ensure they validate cleanly
    jobs = get_mock_jobs("LinkedInScout", 24)
    assert len(jobs) > 0
    for job in jobs:
        assert isinstance(job, DiscoveredJob)
        assert job.url.scheme in ["http", "https"]

@pytest.mark.asyncio
async def test_deduplication_and_idempotency(test_db):
    engine = DiscoveryEngine(repository=test_db, template_path="master_cv_template.json", use_mock=True)
    
    # Run normal lane
    telemetry = await engine.run_normal_lane()
    
    # Total unique mock jobs across all 5 scouts in the 24 hour window:
    # LinkedIn: 3
    # CompanyDirect: 2 (1 overlaps with LinkedIn)
    # Boards: 2
    # Startup: 2
    # Academic: 2
    # But wait, one from Academic is 10 hours ago, one is 23 hours ago.
    # Let's just check that duplicates_skipped > 0 because of the overlapping Stripe job
    # "https://jobs.lever.co/stripe/789" is present in LinkedIn (20h) and CompanyDirect (20h)
    
    assert telemetry["duplicates_skipped"] >= 1
    
    # Let's count the DB directly
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM jobs")
    count = cursor.fetchone()[0]
    conn.close()
    
    # Assert DB count matches unique inserted
    assert count == telemetry["unique_inserted"]

@pytest.mark.asyncio
async def test_fast_lane_vs_normal_lane(test_db):
    engine = DiscoveryEngine(repository=test_db, template_path="master_cv_template.json", use_mock=True)
    
    # Fast lane (3 hours, Scout B and Scout D)
    fast_telemetry = await engine.run_fast_lane()
    
    # Scout B has Airbnb (1h), Stripe (20h, filtered out)
    # Scout D has OpenAI (1h), Anthropic (2h)
    # Total found should be 3
    assert fast_telemetry["total_found"] == 3
    assert fast_telemetry["unique_inserted"] == 3
    assert "CompanyDirectScout" in fast_telemetry["scout_breakdown"]
    assert "StartupScout" in fast_telemetry["scout_breakdown"]
    assert "LinkedInScout" not in fast_telemetry["scout_breakdown"]
    
    # Run normal lane afterwards
    # It covers 24 hours, all 5 scouts
    normal_telemetry = await engine.run_normal_lane()
    
    # Because fast lane already inserted 3 jobs, normal lane will skip those 3
    # Total jobs across 24h:
    # LinkedIn: 3
    # CompanyDirect: 2 (Stripe, Airbnb)
    # Boards: 2
    # Startup: 2
    # Academic: 2
    # Total unique: 3 + 1 (Airbnb) + 2 + 2 + 2 = 10
    # Already inserted: 3
    # New inserted: 7
    assert normal_telemetry["unique_inserted"] == 7
    assert normal_telemetry["duplicates_skipped"] >= 3

@pytest.mark.asyncio
async def test_concurrent_safety(test_db):
    # Testing that no "database is locked" occurs
    # by running multiple fast/normal lanes concurrently.
    engine = DiscoveryEngine(repository=test_db, template_path="master_cv_template.json", use_mock=True)
    
    tasks = [
        engine.run_normal_lane(),
        engine.run_fast_lane(),
        engine.run_normal_lane()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for r in results:
        assert not isinstance(r, Exception), f"Exception occurred during concurrent access: {r}"
        assert r["errors"] == 0, "Errors recorded in telemetry"
