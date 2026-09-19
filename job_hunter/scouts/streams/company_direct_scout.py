from typing import Dict, Any, List
from schemas import DiscoveredJob
from scouts.base_scout import BaseScout
from scouts.mock_feed import get_mock_jobs
from config import get_settings
import logging
import json
from datetime import datetime, timezone
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class CompanyDirectScout(BaseScout):
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        self.settings = get_settings()
        if not self.use_mock:
            self.client = genai.Client()

    @property
    def name(self) -> str:
        return "CompanyDirectScout"

    @property
    def source_category(self) -> str:
        return "DirectATS"

    async def search(self, query_params: Dict[str, Any]) -> List[DiscoveredJob]:
        time_range = query_params.get("time_range_hours", 24)
        
        if self.use_mock:
            return get_mock_jobs(self.name, time_range)
            
        target_roles = query_params.get("roles", ["Software Engineer"])
        
        roles_str = " OR ".join(target_roles)
        
        prompt = f"""
        Search for recent job postings directly on ATS platforms like Greenhouse (boards.greenhouse.io) and Lever (jobs.lever.co) matching:
        Roles: {roles_str}
        
        Use the Google Search tool to find a MAXIMUM OF 5 real job listings from these domains that were posted recently.
        Do not return more than 5 jobs per execution to avoid pipeline overload.
        
        Return a JSON list of objects matching this exact schema:
        {{
            "company": "Company Name",
            "role": "Job Title",
            "location": "Job Location",
            "remote_hybrid": "Remote/Hybrid/Onsite",
            "salary": "$X - $Y (if available, else null)",
            "url": "https://boards.greenhouse.io/...",
            "required_experience": "X years",
            "major_skills": ["Skill1", "Skill2"]
        }}
        """
        
        try:
            logger.info(f"[{self.name}] Searching Google for recent ATS jobs...")
            response = self.client.models.generate_content(
                model=self.settings.default_model_fast,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            
            data = json.loads(response.text)
            jobs = []
            now = datetime.now(timezone.utc)
            for item in data:
                try:
                    job = DiscoveredJob(
                        company=item.get("company", "Unknown"),
                        role=item.get("role", "Unknown"),
                        location=item.get("location", "Unknown"),
                        remote_hybrid=item.get("remote_hybrid", "Unknown"),
                        salary=item.get("salary"),
                        url=item.get("url"),
                        required_experience=item.get("required_experience", ""),
                        major_skills=item.get("major_skills", []),
                        source="CompanyATS",
                        posted_timestamp=now
                    )
                    jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to parse a job item: {e}")
            
            logger.info(f"[{self.name}] Found {len(jobs)} real jobs.")
            return jobs
        except Exception as e:
            logger.error(f"[{self.name}] Error searching real ATS jobs: {e}")
            return []
