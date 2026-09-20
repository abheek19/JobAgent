import json
import os
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from schemas import DiscoveredJob, ResearchedJob, TailoredMaterial
from config import get_settings

class ApplicationTailor:
    def __init__(self, model_id: Optional[str] = None):
        self.settings = get_settings()
        api_key = self.settings.tailor_engine_api_key or self.settings.gemini_api_key
        self.client = genai.Client(api_key=api_key)
        self.model = model_id or self.settings.default_model_pro
        
        self.system_instruction = """You are a Principal Software Architect Application Tailor.
Your goal is to synthesize the candidate's verified credentials with a target job description and company research brief to generate tailored application materials.
You are STRICTLY FORBIDDEN from manufacturing, exaggerating, or altering employment history, companies, dates, degrees, job titles, or metrics.
Reorder, emphasize, and highlight genuine achievements to address the vacancy requirements, but never invent credentials.
Output drafts only. Never submit or push application packages to external endpoints.
You must strictly guarantee adherence to the candidate's Master CV."""

    def generate_materials(self, master_cv: Dict[str, Any], job: DiscoveredJob, research: ResearchedJob) -> TailoredMaterial:
        prompt = f"""
Target Job Details:
Title: {job.role}
Company: {job.company}
Requirements: {job.required_experience}
Major Skills: {', '.join(job.major_skills)}

Company Research Brief:
{research.business_summary}
Recent Developments: {research.recent_developments}
Hiring Context: {research.hiring_context}

Candidate Master CV (Single Source of Truth):
{json.dumps(master_cv, indent=2)}

Task:
Generate a tailored resume diff (highlighting and prioritizing the most relevant genuine achievements) and a bespoke cover letter that cites real company developments and the candidate's genuine milestones.
Remember: DO NOT fabricate any information. You must return `adherence_guarantee` as a string "True" or "Yes" if you followed this rule.
"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                system_instruction=self.system_instruction,
                response_mime_type="application/json",
                response_schema=TailoredMaterial,
            )
        )
        
        # Pydantic validation
        result = TailoredMaterial.model_validate_json(response.text)
        # Ensure job_id matches
        result.job_id = job.id
        return result
