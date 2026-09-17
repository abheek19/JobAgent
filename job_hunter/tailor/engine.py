import asyncio
import json
import time
import os
from typing import Dict, Any
from database import JobRepository
from schemas import DiscoveredJob, ResearchedJob, TailoredMaterial

class TailoringEngine:
    def __init__(self, repo: JobRepository, tailor_agent, max_concurrent: int = 3):
        self.tailor_agent = tailor_agent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.repo = repo
        self.metrics = {
            "applications_tailored": 0,
            "total_latency_seconds": 0.0,
            "adherence_flags_passed": 0
        }
        
        # Load Master CV
        master_cv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "master_cv_template.json")
        with open(master_cv_path, "r", encoding="utf-8") as f:
            self.master_cv = json.load(f)

    async def _process_job(self, job_record: Dict[str, Any]) -> None:
        start_time = time.time()
        async with self.semaphore:
            payload = job_record.get('payload', {})
            
            # Reconstruct DiscoveredJob and ResearchedJob
            try:
                job = DiscoveredJob.model_validate(payload)
                # research is expected to be in payload if it reached HIGH_MATCH through Module 4
                if 'business_summary' not in payload:
                    print(f"Skipping job {job_record['id']} - missing research brief.")
                    return
                
                research = ResearchedJob.model_validate(payload)
            except Exception as e:
                print(f"Schema validation failed for {job_record['id']}: {e}")
                return

            # Call tailor
            try:
                # We can't await if generate_materials is sync. We should run in executor if it's blocking.
                # Assuming tailor_agent.generate_materials is synchronous as implemented.
                loop = asyncio.get_running_loop()
                tailored = await loop.run_in_executor(None, self.tailor_agent.generate_materials, self.master_cv, job, research)
                
                # Update payload
                payload.update(tailored.model_dump(mode='json'))
                payload['cv_prepared'] = "Yes"
                
                # Update DB and state transition
                self.repo.update_job_status(job_record['id'], "APP_READY", payload)
                
                # Update metrics
                self.metrics["applications_tailored"] += 1
                if str(tailored.adherence_guarantee).lower() in ["true", "yes"]:
                    self.metrics["adherence_flags_passed"] += 1
                    
            except Exception as e:
                print(f"Tailoring failed for {job_record['id']}: {e}")
            finally:
                self.metrics["total_latency_seconds"] += (time.time() - start_time)

    async def run(self) -> Dict[str, Any]:
        pending_jobs = self.repo.get_pending_jobs("HIGH_MATCH")
        
        tasks = []
        for record in pending_jobs:
            tasks.append(self._process_job(record))
            
        if tasks:
            await asyncio.gather(*tasks)
            
        # Synchronize CSV
        self.repo.sync_to_csv()
        
        # Calculate averages
        avg_latency = 0
        if self.metrics["applications_tailored"] > 0:
            avg_latency = self.metrics["total_latency_seconds"] / self.metrics["applications_tailored"]
            
        return {
            "total_tailored": self.metrics["applications_tailored"],
            "avg_latency_seconds": round(avg_latency, 2),
            "adherence_flags_passed": self.metrics["adherence_flags_passed"]
        }
