import pytest
import os
from langgraph.types import Command

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from orchestrator.mock_graph import create_mock_app

import tempfile

@pytest.fixture
def mock_app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app, repo = create_mock_app(path)
    yield app, repo
    # cleanup
    try:
        repo._get_conn().close()
    except:
        pass
    import time
    time.sleep(0.1) # small delay to let threads close connections
    try:
        if os.path.exists(path):
            os.remove(path)
    except PermissionError:
        pass # Ignored on Windows due to thread local conns

@pytest.mark.asyncio
async def test_graph_pauses_at_interrupt(mock_app):
    app, repo = mock_app
    config = {"configurable": {"thread_id": "test_thread_1"}}
    initial_state = {
        "thread_id": "test_thread_1",
        "lane": "fast_lane",
        "candidate_cv": {},
        "target_preferences": {},
        "pending_job_ids": [],
        "current_stage": "init",
        "human_decision": None,
        "active_alerts": [],
        "review_feedback": None
    }
    
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    state = app.get_state(config)
    assert len(state.next) > 0
    assert state.next[0] == "supervisor"
    
    app_ready = repo.get_pending_jobs("APP_READY")
    assert len(app_ready) == 1
    
    alerts = []
    if state.tasks and state.tasks[0].interrupts:
        alerts = state.tasks[0].interrupts[0].value
        
    assert len(alerts) == 1
    assert alerts[0]["company"] == "MockCorp"

@pytest.mark.asyncio
async def test_graph_resumes_on_approve(mock_app):
    app, repo = mock_app
    config = {"configurable": {"thread_id": "test_thread_2"}}
    initial_state = {
        "thread_id": "test_thread_2",
        "lane": "fast_lane",
    }
    
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    state = app.get_state(config)
    assert len(state.next) > 0
    
    async for event in app.astream(Command(resume="APPROVE"), config, stream_mode="values"):
        pass
        
    state = app.get_state(config)
    assert len(state.next) == 0
    
    applied_jobs = repo.get_pending_jobs("APPLIED")
    assert len(applied_jobs) == 1
    assert applied_jobs[0]["company"] == "MockCorp"
    payload = applied_jobs[0].get("payload", {})
    assert payload.get("applied") == "Yes"

@pytest.mark.asyncio
async def test_graph_resumes_on_reject(mock_app):
    app, repo = mock_app
    config = {"configurable": {"thread_id": "test_thread_3"}}
    initial_state = {
        "thread_id": "test_thread_3",
        "lane": "fast_lane",
    }
    
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    async for event in app.astream(Command(resume="REJECT"), config, stream_mode="values"):
        pass
        
    rejected = repo.get_pending_jobs("REJECTED")
    assert len(rejected) == 1
    applied = repo.get_pending_jobs("APPLIED")
    assert len(applied) == 0

@pytest.mark.asyncio
async def test_zero_submission_safety(mock_app):
    app, repo = mock_app
    config = {"configurable": {"thread_id": "test_thread_4"}}
    initial_state = {
        "thread_id": "test_thread_4",
        "lane": "fast_lane",
    }
    
    async for event in app.astream(initial_state, config, stream_mode="values"):
        pass
        
    applied = repo.get_pending_jobs("APPLIED")
    assert len(applied) == 0
    
    app_ready = repo.get_pending_jobs("APP_READY")
    assert len(app_ready) == 1
