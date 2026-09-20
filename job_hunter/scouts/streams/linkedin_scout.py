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

class LinkedInScout(BaseScout):
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        self.settings = get_settings()
        if not self.use_mock:
            api_key = self.settings.linkedin_scout_api_key or self.settings.gemini_api_key
            self.client = genai.Client(api_key=api_key)

    @property
    def name(self) -> str:
        return "LinkedInScout"

    @property
    def source_category(self) -> str:
        return "Aggregator"

    async def search(self, query_params: Dict[str, Any]) -> List[DiscoveredJob]:
        time_range = query_params.get("time_range_hours", 24)
        
        if self.use_mock:
            return get_mock_jobs(self.name, time_range)
            
        target_roles = query_params.get("roles", ["Software Engineer"])
        target_locations = query_params.get("locations", ["Remote"])
        
        roles_str = " OR ".join(target_roles)
        locations_str = " OR ".join(target_locations)
        
        prompt = f"""
        Search LinkedIn for recent job postings that match the following criteria:
        Roles: {roles_str}
        Locations: {locations_str}
        Posted in the last: {time_range} hours.

        Please use the Google Search tool to find a MAXIMUM OF 5 real job listings from LinkedIn (linkedin.com/jobs) that match this.
        Do not return more than 5 jobs per execution to avoid pipeline overload.
        
        Return a JSON list of objects matching this exact schema:
        {{
            "company": "Company Name",
            "role": "Job Title",
            "location": "Job Location",
            "remote_hybrid": "Remote/Hybrid/Onsite",
            "salary": "$X - $Y (if available, else null)",
            "url": "https://www.linkedin.com/jobs/view/...",
            "required_experience": "X years",
            "major_skills": ["Skill1", "Skill2"]
        }}
        """
        
        try:
            logger.info(f"[{self.name}] Searching Google for recent LinkedIn jobs...")
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
                        source="LinkedIn",
                        posted_timestamp=now
                    )
                    jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to parse a job item: {e}")
            
            logger.info(f"[{self.name}] Found {len(jobs)} real jobs.")
            return jobs
        except Exception as e:
            logger.error(f"[{self.name}] Error searching real jobs: {e}")
            return []
