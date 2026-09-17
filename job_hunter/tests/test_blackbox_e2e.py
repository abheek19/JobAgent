import pytest
import os
import tempfile
import sys
import pathlib
from datetime import datetime, timezone
import json
from langgraph.types import Command
import time

sys.path.append(str(pathlib.Path(__file__).parent.parent))

from database import JobRepository
from orchestrator.nodes import OrchestratorNodes
from orchestrator.graph import GraphBuilder
from schemas import DiscoveredJob

class E2EMockDiscoveryEngine:
    def __init__(self, repo: JobRepository, jobs_to_inject=None):
        self.repo = repo
        self.jobs_to_inject = jobs_to_inject or []
        
    async def run_fast_lane(self):
        for job in self.jobs_to_inject:
            self.repo.insert_discovered_job(job)
            
    async def run_normal_lane(self):
        await self.run_fast_lane()

class E2EMockFilterEngine:
    def __init__(self, repo: JobRepository):
        self.repo = repo
        
    async def run(self):
        pending = self.repo.get_pending_jobs("DISCOVERED")
        for job in pending:
            payload = job.get('payload', {})
            # Scenario C hook: If role contains 'Reject', filter out.
            if 'Reject' in job['role']:
                payload['classification'] = "Reject"
                payload['match_evidence'] = "Lacks required qualifications."
                self.repo.update_job_status(job['id'], "SCREENED", payload)
                self.repo.update_job_status(job['id'], "REJECTED", payload)
            else:
                payload['classification'] = "High Match"
                payload['match_evidence'] = "Excellent match."
                self.repo.update_job_status(job['id'], "SCREENED", payload)
                self.repo.update_job_status(job['id'], "HIGH_MATCH", payload)

class E2EMockDeepeningEngine:
    def __init__(self, repo: JobRepository):
        self.repo = repo
        
    async def run(self):
        pending = self.repo.get_pending_jobs("HIGH_MATCH")
        for job in pending:
            payload = job.get('payload', {})
            payload['research'] = {
                "business_summary": "Solid company.",
            }
            payload['contact_name'] = "Jane E2E"
            payload['contact_found'] = "Yes"
            self.repo.update_job_status(job['id'], "HIGH_MATCH", payload)

class E2EMockTailoringEngine:
    def __init__(self, repo: JobRepository):
        self.repo = repo
        
    async def run(self):
        pending = self.repo.get_pending_jobs("HIGH_MATCH")
        for job in pending:
            payload = job.get('payload', {})
            payload['cv_prepared'] = "Yes"
            self.repo.update_job_status(job['id'], "APP_READY", payload)


def create_e2e_app(db_path: str, jobs_to_inject):
    repo = JobRepository(db_path=db_path)
    discovery = E2EMockDiscoveryEngine(repo, jobs_to_inject)
    filter_engine = E2EMockFilterEngine(repo)
    deepening = E2EMockDeepeningEngine(repo)
    tailoring = E2EMockTailoringEngine(repo)
    
    nodes_impl = OrchestratorNodes(repo, discovery, filter_engine, deepening, tailoring)
    builder = GraphBuilder(nodes_impl)
    app = builder.build()
    return app, repo

@pytest.fixture
def e2e_env():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    def _make_app(jobs):
        return create_e2e_app(path, jobs)
        
    yield _make_app, path
    
    # cleanup
    time.sleep(0.1)
    try:
        if os.path.exists(path):
            os.remove(path)
    except PermissionError:
        pass


@pytest.mark.asyncio
async def test_scenario_a_golden_path(e2e_env):
    """
    Scenario A: The "Golden Path" (High Match -> Approval)
    """
    make_app, db_path = e2e_env
    
    ideal_job = DiscoveredJob(
        company="GoldenCorp", role="Principal Engineer", location="Remote", remote_hybrid="Remote",
        posted_timestamp=datetime.now(timezone.utc), url="https://example.com/golden",
        required_experience="10 years", major_skills=["Python", "System Design"], source="ATS"
    )
    
    app, repo = make_app([ideal_job])
    config = {"configurable": {"thread_id": "e2e_golden_thread"}}
    initial_state = {"thread_id": "e2e_golden", "lane": "fast_lane"}
    
    # Run to interrupt
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    state = app.get_state(config)
    assert len(state.next) > 0, "Graph should pause at supervisor"
    
    # Resume with APPROVE
    async for event in app.astream(Command(resume="APPROVE"), config, stream_mode="values"):
        pass
        
    # Verify DB state
    applied_jobs = repo.get_pending_jobs("APPLIED")
    assert len(applied_jobs) == 1
    assert applied_jobs[0]["company"] == "GoldenCorp"
    
    payload = applied_jobs[0]["payload"]
    assert payload.get("cv_prepared") == "Yes"
    assert payload.get("contact_found") == "Yes"
    assert payload.get("applied") == "Yes"
    
    # Verify CSV Export
    csv_path = db_path.replace(".db", ".csv")
    repo.sync_to_csv(csv_path)
    
    assert os.path.exists(csv_path)
    with open(csv_path, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "GoldenCorp" in content
        assert "APPLIED" in content
    os.remove(csv_path)


@pytest.mark.asyncio
async def test_scenario_b_negative_path(e2e_env):
    """
    Scenario B: The "Negative / Rejection Path" (User Denies Submission)
    """
    make_app, db_path = e2e_env
    
    ideal_job = DiscoveredJob(
        company="RejectCorp", role="Principal Engineer", location="Remote", remote_hybrid="Remote",
        posted_timestamp=datetime.now(timezone.utc), url="https://example.com/rejectme",
        required_experience="10 years", major_skills=["Python"], source="ATS"
    )
    
    app, repo = make_app([ideal_job])
    config = {"configurable": {"thread_id": "e2e_negative_thread"}}
    initial_state = {"thread_id": "e2e_negative", "lane": "fast_lane"}
    
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    async for event in app.astream(Command(resume="REJECT"), config, stream_mode="values"):
        pass
        
    rejected_jobs = repo.get_pending_jobs("REJECTED")
    assert len(rejected_jobs) == 1
    assert rejected_jobs[0]["company"] == "RejectCorp"
    
    applied_jobs = repo.get_pending_jobs("APPLIED")
    assert len(applied_jobs) == 0
    
    payload = rejected_jobs[0]["payload"]
    assert payload.get("applied") is None or payload.get("applied") == "No"


@pytest.mark.asyncio
async def test_scenario_c_low_match_filter(e2e_env):
    """
    Scenario C: The "Low Match / Disqualification Filter"
    """
    make_app, db_path = e2e_env
    
    mismatched_job = DiscoveredJob(
        company="LowMatchCorp", role="Reject - Junior Dev", location="Remote", remote_hybrid="Remote",
        posted_timestamp=datetime.now(timezone.utc), url="https://example.com/lowmatch",
        required_experience="1 year", major_skills=["HTML"], source="ATS"
    )
    
    app, repo = make_app([mismatched_job])
    config = {"configurable": {"thread_id": "e2e_lowmatch_thread"}}
    initial_state = {"thread_id": "e2e_lowmatch", "lane": "fast_lane"}
    
    # Run graph
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    state = app.get_state(config)
    # The pipeline should finish without hitting the supervisor (no high match)
    # Wait, actually check_high_match condition routes to supervisor if no HIGH_MATCH jobs.
    # If supervisor node has no APP_READY jobs, it returns empty active_alerts.
    # The interrupt is only called if there are APP_READY jobs!
    assert len(state.next) == 0, "Graph should not pause, it should complete directly"
    
    rejected_jobs = repo.get_pending_jobs("REJECTED")
    assert len(rejected_jobs) == 1
    assert rejected_jobs[0]["company"] == "LowMatchCorp"
    assert rejected_jobs[0]["payload"]["classification"] == "Reject"


@pytest.mark.asyncio
async def test_scenario_d_zero_submission_safety(e2e_env):
    """
    Scenario D: "Zero-Submission Safety Invariant"
    """
    make_app, db_path = e2e_env
    
    job = DiscoveredJob(
        company="SafetyCorp", role="Engineer", location="Remote", remote_hybrid="Remote",
        posted_timestamp=datetime.now(timezone.utc), url="https://example.com/safety",
        required_experience="5 years", major_skills=["Python"], source="ATS"
    )
    
    app, repo = make_app([job])
    config = {"configurable": {"thread_id": "e2e_safety_thread"}}
    initial_state = {"thread_id": "e2e_safety", "lane": "fast_lane"}
    
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    state = app.get_state(config)
    assert len(state.next) > 0, "Should be paused"
    
    app_ready = repo.get_pending_jobs("APP_READY")
    assert len(app_ready) == 1
    
    applied = repo.get_pending_jobs("APPLIED")
    assert len(applied) == 0


@pytest.mark.asyncio
async def test_scenario_e_idempotent_reingestion(e2e_env):
    """
    Scenario E: "Idempotent Re-ingestion"
    """
    make_app, db_path = e2e_env
    
    job = DiscoveredJob(
        company="IdemCorp", role="Engineer", location="Remote", remote_hybrid="Remote",
        posted_timestamp=datetime.now(timezone.utc), url="https://example.com/idem",
        required_experience="5 years", major_skills=["Python"], source="ATS"
    )
    
    app, repo = make_app([job, job]) # Inject duplicate
    
    # We test that insert_discovered_job correctly handles it via sqlite3.IntegrityError
    # which E2EMockDiscoveryEngine calls. It returns False on duplicate.
    config = {"configurable": {"thread_id": "e2e_idem_thread"}}
    initial_state = {"thread_id": "e2e_idem", "lane": "fast_lane"}
    
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    # Total jobs in db should be 1
    conn = repo._get_conn()
    cursor = conn.execute("SELECT count(*) as cnt FROM jobs")
    cnt = cursor.fetchone()['cnt']
    assert cnt == 1, "Duplicate jobs should not be inserted"

