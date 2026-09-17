from typing import Dict, Any, List
from schemas import DiscoveredJob
from scouts.base_scout import BaseScout
from scouts.mock_feed import get_mock_jobs

class AcademicScout(BaseScout):
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock

    @property
    def name(self) -> str:
        return "AcademicScout"

    @property
    def source_category(self) -> str:
        return "HigherEd"

    async def search(self, query_params: Dict[str, Any]) -> List[DiscoveredJob]:
        time_range = query_params.get("time_range_hours", 24)
        
        if self.use_mock:
            return get_mock_jobs(self.name, time_range)
            
        return []
