import asyncio
from typing import Dict, Any, List
from langgraph.types import interrupt

from database import JobRepository
from scouts.engine import DiscoveryEngine
from filter.engine import FilterEngine
from investigator.engine import DeepeningEngine
from tailor.engine import TailoringEngine
from orchestrator.state import JobDepartmentGraphState

class OrchestratorNodes:
    def __init__(
        self,
        repository: JobRepository,
        discovery_engine: DiscoveryEngine,
        filter_engine: FilterEngine,
        deepening_engine: DeepeningEngine,
        tailoring_engine: TailoringEngine
    ):
        self.repo = repository
        self.discovery = discovery_engine
        self.filter = filter_engine
        self.deepening = deepening_engine
        self.tailoring = tailoring_engine

    async def discovery_node(self, state: JobDepartmentGraphState) -> JobDepartmentGraphState:
        state['current_stage'] = 'discovery'
        if state.get('lane') == 'fast_lane':
            await self.discovery.run_fast_lane()
        else:
            await self.discovery.run_normal_lane()
        return state

    async def filter_node(self, state: JobDepartmentGraphState) -> JobDepartmentGraphState:
        state['current_stage'] = 'filtering'
        await self.filter.run()
        return state

    async def deepening_node(self, state: JobDepartmentGraphState) -> JobDepartmentGraphState:
        state['current_stage'] = 'deepening'
        await self.deepening.run()
        return state

    async def tailor_node(self, state: JobDepartmentGraphState) -> JobDepartmentGraphState:
        state['current_stage'] = 'tailoring'
        await self.tailoring.run()
        return state

    async def supervisor_manager_node(self, state: JobDepartmentGraphState) -> JobDepartmentGraphState:
        app_ready_jobs = self.repo.get_pending_jobs("APP_READY")
        
        if not app_ready_jobs:
            state['active_alerts'] = []
            return state
            
        alerts = []
        for job in app_ready_jobs:
            payload = job.get('payload', {})
            alerts.append({
                "job_id": job['id'],
                "company": job['company'],
                "role": job['role'],
                "match_evidence": payload.get('classification', '') + " - " + payload.get('match_evidence', ''),
                "business_summary": payload.get('research', {}).get('business_summary', ''),
                "contact_name": payload.get('contact_name', 'Not Found')
            })
            
        state['active_alerts'] = alerts
        state['current_stage'] = 'supervisor_review'
        
        # Trigger HITL
        decision = interrupt(alerts)
        
        state['human_decision'] = decision
        return state

    async def submission_gate_node(self, state: JobDepartmentGraphState) -> JobDepartmentGraphState:
        decision = state.get('human_decision')
        
        if not decision:
            # If there was no decision (e.g. no APP_READY jobs), we just pass through
            return state
            
        app_ready_jobs = self.repo.get_pending_jobs("APP_READY")
        
        for job in app_ready_jobs:
            job_id = job['id']
            payload = job.get('payload', {})
            
            if decision == "APPROVE":
                # APP_READY -> APPROVED
                self.repo.update_job_status(job_id, "APPROVED", payload)
                # APPROVED -> APPLIED
                payload['applied'] = "Yes"
                self.repo.update_job_status(job_id, "APPLIED", payload)
            elif decision == "REJECT":
                self.repo.update_job_status(job_id, "REJECTED", payload)
            elif decision == "REVISE":
                # Just keeping it in APP_READY or sending back
                pass
                
        self.repo.sync_to_csv()
        state['current_stage'] = 'complete'
        
        # Reset human decision after processing so we don't re-process
        state['human_decision'] = None
        state['active_alerts'] = []
        
        return state
