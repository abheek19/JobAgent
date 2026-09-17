import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, Any

from database import JobRepository
from orchestrator.nodes import OrchestratorNodes
from orchestrator.graph import GraphBuilder
from schemas import DiscoveredJob

class MockDiscoveryEngine:
    def __init__(self, repo: JobRepository):
        self.repo = repo
        
    async def run_fast_lane(self):
        job1 = DiscoveredJob(
            company="MockCorp", role="AI Engineer", location="Remote", remote_hybrid="Remote",
            posted_timestamp=datetime.now(timezone.utc), url="https://example.com/mockjob1",
            required_experience="3 years", major_skills=["Python", "AI"], source="MockScout"
        )
        self.repo.insert_discovered_job(job1)
        
    async def run_normal_lane(self):
        await self.run_fast_lane()

class MockFilterEngine:
    def __init__(self, repo: JobRepository):
        self.repo = repo
        
    async def run(self):
        pending = self.repo.get_pending_jobs("DISCOVERED")
        for job in pending:
            payload = job.get('payload', {})
            payload['classification'] = "High Match"
            payload['match_evidence'] = "100% matched by Mock Screener"
            # In real system we transition to SCREENED then HIGH_MATCH
            self.repo.update_job_status(job['id'], "SCREENED", payload)
            self.repo.update_job_status(job['id'], "HIGH_MATCH", payload)

class MockDeepeningEngine:
    def __init__(self, repo: JobRepository):
        self.repo = repo
        
    async def run(self):
        pending = self.repo.get_pending_jobs("HIGH_MATCH")
        for job in pending:
            payload = job.get('payload', {})
            payload['research'] = {
                "job_id": job['id'],
                "company": job['company'],
                "business_summary": "Mock business summary doing amazing AI things.", 
                "recent_developments": "Launched mock product.", 
                "hiring_context": "Expanding engineering team.", 
                "source_links": []
            }
            payload['network_lead'] = {
                "job_id": job['id'],
                "contact_name": "Jane Doe Mock", 
                "contact_role": "VP of Engineering", 
                "profile_url": "https://example.com/jane", 
                "relevance_reasoning": "Hiring manager", 
                "drafted_outreach_message": "Hi Jane..."
            }
            payload['contact_name'] = "Jane Doe Mock"
            payload['contact_found'] = "Yes"
            self.repo.update_job_status(job['id'], "HIGH_MATCH", payload)

class MockTailoringEngine:
    def __init__(self, repo: JobRepository):
        self.repo = repo
        
    async def run(self):
        pending = self.repo.get_pending_jobs("HIGH_MATCH")
        for job in pending:
            payload = job.get('payload', {})
            payload['tailored_cv_diff'] = "+ Added mock experience with MockCorp stack"
            payload['tailored_cover_letter'] = "Dear Jane Doe Mock, I'd love to join MockCorp..."
            payload['adherence_guarantee'] = "True"
            payload['cv_prepared'] = "Yes"
            self.repo.update_job_status(job['id'], "APP_READY", payload)


def create_mock_app(db_path: str = ":memory:"):
    repo = JobRepository(db_path=db_path)
    discovery = MockDiscoveryEngine(repo)
    filter_engine = MockFilterEngine(repo)
    deepening = MockDeepeningEngine(repo)
    tailoring = MockTailoringEngine(repo)
    
    nodes_impl = OrchestratorNodes(repo, discovery, filter_engine, deepening, tailoring)
    builder = GraphBuilder(nodes_impl)
    app = builder.build()
    return app, repo
