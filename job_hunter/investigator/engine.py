import asyncio
import time
import json
from typing import List, Dict, Any

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from database import JobRepository
from schemas import DiscoveredJob, ResearchedJob, NetworkLead
from investigator.company_investigator import CompanyInvestigator
from investigator.network_scout import NetworkScout

class DeepeningEngine:
    def __init__(self, repo: JobRepository, max_concurrent: int = 3, investigator=None, scout=None):
        self.repo = repo
        self.investigator = investigator or CompanyInvestigator()
        self.scout = scout or NetworkScout()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    async def process_job(self, job_record: Dict[str, Any]) -> bool:
        async with self.semaphore:
            job_id = job_record['id']
            payload = job_record.get('payload', {})
            
            # Reconstruct DiscoveredJob from payload for context
            try:
                # payload might have extra fields, but DiscoveredJob should be able to parse if we provide basics
                # Wait, the job record has the top level fields and the payload has the original job dict
                job_data = {
                    "id": job_id,
                    "company": job_record['company'],
                    "role": job_record['role'],
                    "location": job_record['location'],
                    "salary": job_record['salary'],
                    "url": job_record['url'],
                    # Fill in missing fields from payload if they exist, else provide defaults
                    "remote_hybrid": payload.get('remote_hybrid', "Unknown"),
                    "posted_timestamp": payload.get('posted_timestamp', job_record['created_at']),
                    "required_experience": payload.get('required_experience', "Unknown"),
                    "major_skills": payload.get('major_skills', []),
                    "source": payload.get('source', "Unknown")
                }
                job = DiscoveredJob.model_validate(job_data)
            except Exception as e:
                print(f"Error reconstructing job {job_id}: {e}")
                return False

            print(f"Deepening research for {job.company} - {job.role}...")
            
            # Execute sequentially to prevent concurrent Pro model burst limits
            try:
                research_res = await self.investigator.investigate(job)
                await asyncio.sleep(15)
                scout_res = await self.scout.scout(job)
                
                # Update payload
                update_payload = {
                    "research": research_res.model_dump(mode='json'),
                    "network_lead": scout_res.model_dump(mode='json'),
                    "contact_name": scout_res.contact_name if scout_res.contact_name != "Not Found" else None,
                    "contact_found": "Yes" if scout_res.contact_name != "Not Found" else "No"
                }
                
                # We update the payload but keep status as HIGH_MATCH
                self.repo.update_job_status(job_id, "HIGH_MATCH", update_payload)
                return True
                
            except Exception as e:
                print(f"Failed deepening for {job_id}: {e}")
                return False
            finally:
                await asyncio.sleep(15) # Strict 5 RPM limit for gemini-3.5-flash

    async def run(self):
        start_time = time.time()
        
        # Get pending HIGH_MATCH jobs
        high_match_jobs = self.repo.get_pending_jobs("HIGH_MATCH")
        
        # Filter those lacking research or network leads
        jobs_to_process = []
        for j in high_match_jobs:
            payload = j.get('payload') or {}
            if 'research' not in payload or 'network_lead' not in payload:
                jobs_to_process.append(j)
                
        if not jobs_to_process:
            print("No HIGH_MATCH jobs pending deepening.")
            return

        print(f"Starting deepening engine for {len(jobs_to_process)} jobs...")
        
        tasks = [self.process_job(job) for job in jobs_to_process]
        results = await asyncio.gather(*tasks)
        
        successful = sum(1 for r in results if r)
        
        # Sync to CSV
        self.repo.sync_to_csv()
        
        duration = time.time() - start_time
        print(f"Deepening complete in {duration:.2f}s.")
        print(f"Jobs processed: {len(jobs_to_process)}")
        print(f"Briefs compiled & Contacts sourced: {successful}")

if __name__ == "__main__":
    engine = DeepeningEngine()
    asyncio.run(engine.run())
