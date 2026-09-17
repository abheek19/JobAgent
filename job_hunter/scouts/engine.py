import asyncio
import json
import logging
from typing import Dict, Any, List

from database import JobRepository
from scouts.base_scout import BaseScout
from scouts.streams.linkedin_scout import LinkedInScout
from scouts.streams.company_direct_scout import CompanyDirectScout
from scouts.streams.boards_scout import BoardsScout
from scouts.streams.startup_scout import StartupScout
from scouts.streams.academic_scout import AcademicScout

logger = logging.getLogger(__name__)

class DiscoveryEngine:
    def __init__(self, repository: JobRepository, template_path: str = "master_cv_template.json", use_mock: bool = True):
        self.repository = repository
        self.template_path = template_path
        self.use_mock = use_mock
        
        # Initialize all 5 scouts
        self.scouts: List[BaseScout] = [
            LinkedInScout(use_mock=use_mock),
            CompanyDirectScout(use_mock=use_mock),
            BoardsScout(use_mock=use_mock),
            StartupScout(use_mock=use_mock),
            AcademicScout(use_mock=use_mock)
        ]
        
        self.query_params = self._load_target_preferences()

    def _load_target_preferences(self) -> Dict[str, Any]:
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("target_preferences", {})
        except Exception as e:
            logger.error(f"Failed to load preferences from {self.template_path}: {e}")
            return {}

    async def _run_scouts(self, scouts_to_run: List[BaseScout], time_range_hours: int) -> Dict[str, Any]:
        """Runs a list of scouts concurrently and aggregates telemetry."""
        query_params = self.query_params.copy()
        query_params["time_range_hours"] = time_range_hours
        
        # Since SQLite WAL mode handles concurrent readers, but concurrent writes
        # from multiple threads/async tasks on the same connection can be tricky, 
        # we ensure that JobRepository operations are serialized or use connections
        # safely. Python's sqlite3 module handles thread-safety reasonably well in WAL mode,
        # but to avoid database locked errors under heavy async load, one might use an asyncio.Lock.
        # Given we are calling synchronous methods from async, the writes will execute synchronously 
        # in the current thread's event loop, so there's no actual concurrency of sqlite writes.
        
        tasks = [scout.run(query_params, self.repository) for scout in scouts_to_run]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        aggregate_telemetry = {
            "total_found": 0,
            "unique_inserted": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "scout_breakdown": {}
        }
        
        for scout, result in zip(scouts_to_run, results):
            if isinstance(result, Exception):
                logger.error(f"[{scout.name}] failed completely: {result}")
                aggregate_telemetry["errors"] += 1
                aggregate_telemetry["scout_breakdown"][scout.name] = {"error": str(result)}
            else:
                aggregate_telemetry["total_found"] += result["total_found"]
                aggregate_telemetry["unique_inserted"] += result["unique_inserted"]
                aggregate_telemetry["duplicates_skipped"] += result["duplicates_skipped"]
                aggregate_telemetry["errors"] += result["errors"]
                aggregate_telemetry["scout_breakdown"][scout.name] = result
                
        # Synchronize to CSV
        self.repository.sync_to_csv()
        
        return aggregate_telemetry

    async def run_fast_lane(self) -> Dict[str, Any]:
        """
        High-frequency polling cycle focused on Scout B (Direct ATS) 
        and Scout D (Startups) for listings posted in the last 3 hours.
        """
        scouts_to_run = [s for s in self.scouts if s.name in ("CompanyDirectScout", "StartupScout")]
        logger.info("Starting FAST lane discovery...")
        return await self._run_scouts(scouts_to_run, time_range_hours=3)

    async def run_normal_lane(self) -> Dict[str, Any]:
        """
        Sweeping daily routine across all 5 streams targeting the last 24 hours.
        """
        logger.info("Starting NORMAL lane discovery...")
        return await self._run_scouts(self.scouts, time_range_hours=24)
