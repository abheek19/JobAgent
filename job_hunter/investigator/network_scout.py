import os
import json
from typing import Optional
from google import genai
from google.genai import types
from pydantic import ValidationError

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from schemas import NetworkLead, DiscoveredJob
from config import get_settings

class NetworkScout:
    def __init__(self, model_id: Optional[str] = None):
        settings = get_settings()
        self.model_id = model_id or settings.default_model_fast
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def scout(self, job: DiscoveredJob) -> NetworkLead:
        prompt = f"""
You are an expert talent sourcer and professional networker. Your task is to locate a relevant professional contact at the target company and draft an introductory message for a candidate interested in a specific role. You will use Google Search to find this information.

**TARGET EMPLOYER AND ROLE**
Company: {job.company}
Role: {job.role}
Location: {job.location}

**SAFETY & POLICY GUARDRAILS**
- You must ONLY draft outreach messages. You are strictly forbidden from attempting to send any messages, emails, or connection requests.
- Never interact with any external communication endpoints.

**YOUR OBJECTIVES**
1. **Identify Contact**: Find a legitimate, publicly available professional profile of someone relevant to this role at {job.company}. 
   - Ideal targets: Talent Acquisition Specialists, Technical Recruiters, Engineering Managers, or Department Heads.
2. **Determine Profile URL**: Provide the URL to their professional public profile (e.g., LinkedIn, official company team page, etc.).
3. **Relevance Reasoning**: Briefly explain why this person is the right contact for this specific role.
4. **Draft Outreach Message**: Draft a polite, concise, and contextual introductory message (under 100 words) tailored to the role, the company, and this specific contact. The message should express interest in the {job.role} position.

Output the results exactly matching the specified JSON schema.
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=NetworkLead,
                    tools=[{"google_search": {}}],
                    temperature=0.3,
                ),
            )
            
            result = json.loads(response.text)
            
            # Ensure job_id is maintained
            result["job_id"] = job.id
            
            return NetworkLead.model_validate(result)
            
        except Exception as e:
            # Fallback if something goes wrong
            return NetworkLead(
                job_id=job.id,
                contact_name="Not Found",
                contact_role="N/A",
                profile_url="https://example.com/not-found",
                relevance_reasoning=f"Search failed or error occurred: {str(e)}",
                drafted_outreach_message="N/A"
            )
