import asyncio
from typing import Optional, List, Dict, Any
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from config import get_settings
from database import JobRepository
from scouts.engine import DiscoveryEngine
from filter.engine import FilterEngine
from investigator.engine import DeepeningEngine
from tailor.engine import TailoringEngine
from tailor.tailor_agent import ApplicationTailor
from orchestrator.nodes import OrchestratorNodes
from orchestrator.graph import GraphBuilder
from schemas import DiscoveredJob
from api.schemas import PipelineRunRequest, JobResponse, ApprovalDecisionRequest

# In-memory saver for the graph
memory = MemorySaver()

# Initialize the repository and engines
repo = JobRepository()

# For a production setup, we might need actual implementations of scouts, but we'll use the engines
# Ensure engines use the repo
discovery_engine = DiscoveryEngine(repo)
filter_engine = FilterEngine(repo)
deepening_engine = DeepeningEngine(repo)
tailor_agent = ApplicationTailor()
tailoring_engine = TailoringEngine(repo, tailor_agent)

nodes = OrchestratorNodes(repo, discovery_engine, filter_engine, deepening_engine, tailoring_engine)
builder = GraphBuilder(nodes)
app = builder.build(checkpointer=memory)

async def run_pipeline_background(thread_id: str, lane: str):
    """Background task to run the graph."""
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "thread_id": thread_id,
        "lane": lane,
        "candidate_cv": {},
        "target_preferences": {},
        "pending_job_ids": [],
        "current_stage": "init",
        "human_decision": None,
        "active_alerts": [],
        "review_feedback": None
    }
    
    # Run the graph
    async for event in app.astream(initial_state, config=config):
        # We can log events here if needed
        pass

def get_pending_approvals() -> List[Dict]:
    """Queries JobRepository for jobs halted at APP_READY."""
    return repo.get_pending_jobs("APP_READY")

async def resume_approval(thread_id: str, decision: str, feedback: Optional[str]):
    """Resumes the graph with human approval."""
    config = {"configurable": {"thread_id": thread_id}}
    
    command = Command(resume={"human_decision": decision, "review_feedback": feedback})
    
    async for event in app.astream(command, config=config):
        pass

def ingest_job(job: DiscoveredJob) -> bool:
    return repo.insert_discovered_job(job)

def get_all_jobs(status: Optional[str] = None) -> List[Dict]:
    if status:
        return repo.get_pending_jobs(status)
    
    # Custom query for all jobs
    conn = repo._get_conn()
    cursor = conn.execute('SELECT * FROM jobs ORDER BY updated_at DESC')
    results = []
    import json
    for row in cursor:
        d = dict(row)
        if d['payload']:
            d['payload'] = json.loads(d['payload'])
        results.append(d)
    return results

def get_job(job_id: str) -> Optional[Dict]:
    conn = repo._get_conn()
    cursor = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
    row = cursor.fetchone()
    if row:
        d = dict(row)
        import json
        if d['payload']:
            d['payload'] = json.loads(d['payload'])
        return d
    return None
