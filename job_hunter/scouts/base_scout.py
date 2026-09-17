from abc import ABC, abstractmethod
from typing import Dict, Any, List
import asyncio
import logging

from schemas import DiscoveredJob, generate_job_id
from database import JobRepository

logger = logging.getLogger(__name__)

class BaseScout(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scout (e.g. 'LinkedInScout')."""
        pass

    @property
    @abstractmethod
    def source_category(self) -> str:
        """Category of the source (e.g. 'Aggregator', 'DirectATS')."""
        pass

    @abstractmethod
    async def search(self, query_params: Dict[str, Any]) -> List[DiscoveredJob]:
        """
        Abstract asynchronous or thread-safe batch discovery method.
        Should query the source and return a list of DiscoveredJob items.
        """
        pass

    async def _search_with_backoff(self, query_params: Dict[str, Any], max_retries: int = 3) -> List[DiscoveredJob]:
        """Executes search with exponential backoff."""
        base_delay = 1.0
        for attempt in range(max_retries):
            try:
                return await self.search(query_params)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[{self.name}] Max retries reached. Error: {e}")
                    raise
                
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[{self.name}] Search failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
        return []

    async def run(self, query_params: Dict[str, Any], repository: JobRepository) -> Dict[str, int]:
        """
        Runs the scout, generates deterministic IDs, and writes to JobRepository.
        Gracefully counts duplicate skips.
        """
        telemetry = {
            "total_found": 0,
            "unique_inserted": 0,
            "duplicates_skipped": 0,
            "errors": 0
        }

        try:
            discovered_jobs = await self._search_with_backoff(query_params)
            telemetry["total_found"] = len(discovered_jobs)

            for job in discovered_jobs:
                # Ensure the job has an ID generated from URL
                if not job.id:
                    job.id = generate_job_id(str(job.url))
                
                # Attempt to insert
                inserted = repository.insert_discovered_job(job)
                if inserted:
                    telemetry["unique_inserted"] += 1
                else:
                    telemetry["duplicates_skipped"] += 1
                    
        except Exception as e:
            logger.error(f"[{self.name}] Error during run: {e}")
            telemetry["errors"] += 1

        return telemetry
