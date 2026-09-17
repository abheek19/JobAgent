import os
import json
from typing import Optional
from google import genai
from google.genai import types
from pydantic import ValidationError

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from schemas import ResearchedJob, DiscoveredJob
from config import get_settings

class CompanyInvestigator:
    def __init__(self, model_id: Optional[str] = None):
        settings = get_settings()
        self.model_id = model_id or settings.default_model_fast
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def investigate(self, job: DiscoveredJob) -> ResearchedJob:
        prompt = f"""
You are an expert corporate researcher and intelligence analyst. Your task is to research the following employer based on a job listing, using Google Search to gather the most up-to-date information.

**TARGET EMPLOYER AND ROLE**
Company: {job.company}
Role: {job.role}
Location: {job.location}

**SAFETY & POLICY GUARDRAILS**
- You are strictly operating in a read-only research capacity.
- You must NEVER attempt to contact, interact with, or submit forms to any company endpoints.
- Base your analysis strictly on publicly available information.
- If certain information cannot be confidently found, state "Information not publicly available" rather than hallucinating.

**YOUR OBJECTIVES**
1. **Business Summary**: Determine the employer's official business domain, primary products/services, and target market.
2. **Recent Developments**: Identify any recent public developments, news, product launches, or financial milestones in the last 12 months.
3. **Hiring Context**: Ascertain any context around their hiring (e.g., are they expanding, did they recently get funding, is this a replacement role, or general growth?).
4. **Source Links**: Provide a list of URLs used for this research (official website, news articles, etc.).

Output the results exactly matching the specified JSON schema.
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ResearchedJob,
                    tools=[{"google_search": {}}],
                    temperature=0.2,
                ),
            )
            
            result = json.loads(response.text)
            
            # Ensure job_id and company are maintained
            result["job_id"] = job.id
            result["company"] = job.company
            
            return ResearchedJob.model_validate(result)
            
        except Exception as e:
            # Fallback if something goes wrong
            return ResearchedJob(
                job_id=job.id,
                company=job.company,
                business_summary=f"Error during research: {str(e)}",
                recent_developments="N/A",
                hiring_context="N/A",
                source_links=[]
            )
