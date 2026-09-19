import asyncio
from typing import Optional
import json
from schemas import DiscoveredJob
from database import JobRepository

class FilterEngine:
    def __init__(self, repo: JobRepository, screener=None, max_concurrent: int = 5):
        self.repo = repo
        self.screener = screener
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def _screen_and_update(self, job_dict: dict):
        async with self.semaphore:
            # The full DiscoveredJob details are stored in the 'payload' column
            payload = job_dict.get('payload', {})
            job = DiscoveredJob(**payload)
            try:
                # We can call the screener. If the screener is synchronous (which it is using genai.Client),
                # we should run it in a thread pool to avoid blocking the event loop.
                filtered_job = await asyncio.to_thread(self.screener.screen_job, job)
                
                # Determine next state
                if filtered_job.classification == "High Match":
                    next_status = "HIGH_MATCH"
                else:
                    # 'Possible Match' or 'Reject' go to SCREENED
                    # wait, the DB schema has "DISCOVERED" -> "SCREENED" or "REJECTED". 
                    # "SCREENED" -> "HIGH_MATCH", "POSSIBLE_MATCH", "REJECTED"
                    # But the requirement: 
                    # "If classified as High Match: Calls update_job_status(job_id, 'HIGH_MATCH')" 
                    # Note: Our DB might require going through SCREENED first, or maybe DISCOVERED -> HIGH_MATCH is missing?
                    # Let's look at `VALID_TRANSITIONS`:
                    # "DISCOVERED": {"SCREENED", "REJECTED"},
                    # "SCREENED": {"HIGH_MATCH", "POSSIBLE_MATCH", "REJECTED"}
                    # If I try DISCOVERED -> HIGH_MATCH, it will fail due to valid transitions!
                    # Ah! The requirement says:
                    # - If High Match: update_job_status(job_id, "HIGH_MATCH", payload=filtered_data)
                    # Let's fix the transition in FilterEngine. I must first transition to SCREENED, then HIGH_MATCH.
                    # Or update the DB VALID_TRANSITIONS. Since I'm not supposed to rewrite module 1, 
                    # I will transition to SCREENED first, and then to HIGH_MATCH or POSSIBLE_MATCH.
                    
                    next_status = "SCREENED"
                
                payload = filtered_job.model_dump(mode='json')
                
                # First transition to SCREENED since DISCOVERED -> HIGH_MATCH is invalid directly
                self.repo.update_job_status(job.id, "SCREENED", payload=payload)
                
                if filtered_job.classification == "High Match":
                    self.repo.update_job_status(job.id, "HIGH_MATCH", payload=payload)
                elif filtered_job.classification == "Possible Match":
                    self.repo.update_job_status(job.id, "POSSIBLE_MATCH", payload=payload)
                elif filtered_job.classification == "Reject":
                    self.repo.update_job_status(job.id, "REJECTED", payload=payload)
                    
                return filtered_job.classification
            except Exception as e:
                print(f"Error processing job {job.id}: {e}")
                return "Error"
            finally:
                await asyncio.sleep(15) # Strict 5 RPM limit for gemini-3.5-flash

    async def run(self):
        pending = self.repo.get_pending_jobs(status="DISCOVERED")
        if not pending:
            return {"High Match": 0, "Possible Match": 0, "Reject": 0, "Total": 0}

        tasks = [self._screen_and_update(job_dict) for job_dict in pending]
        results = await asyncio.gather(*tasks)

        counts = {
            "High Match": results.count("High Match"),
            "Possible Match": results.count("Possible Match"),
            "Reject": results.count("Reject"),
            "Total": len(results)
        }

        # Automatically call sync_to_csv after batch completion
        self.repo.sync_to_csv()
        
        return counts
