import json
import os
from google import genai
from pydantic import BaseModel
from typing import List, Optional
from schemas import DiscoveredJob, FilteredJob
from config import get_settings

class JobFilterScreener:
    def __init__(self, master_cv_path: str = "master_cv_template.json"):
        with open(master_cv_path, 'r') as f:
            self.master_cv = json.load(f)
            
        # Extract facts from CV for the prompt
        self.verified_skills = self._extract_skills(self.master_cv.get("core_skills_matrix", {}))
        self.work_history = self.master_cv.get("work_history", [])
        self.education = self.master_cv.get("education", [])
        
        self.settings = get_settings()
        api_key = self.settings.filter_engine_api_key or self.settings.gemini_api_key
        self.client = genai.Client(api_key=api_key)

    def _extract_skills(self, matrix: dict) -> List[str]:
        skills = []
        for category, items in matrix.items():
            if isinstance(items, list):
                skills.extend(items)
        return skills

    def screen_job(self, job: DiscoveredJob) -> FilteredJob:
        system_instruction = (
            "Evaluate the listing solely against verified facts in the Master CV. "
            "Classify strictly into 'High Match', 'Possible Match', or 'Reject'. "
            "You are STRICTLY FORBIDDEN from inferring, assuming, or inventing qualifications, "
            "years of experience, or tools not explicitly documented in the CV. "
            "Must cite explicit bullet points/evidence from the CV for `match_evidence`, "
            "and enumerate missing mandatory requirements in `missing_qualifications`."
        )

        prompt = f"""
Master CV Verified Skills: {', '.join(self.verified_skills)}
Master CV Work History: {json.dumps(self.work_history)}
Master CV Education: {json.dumps(self.education)}

---
Job Listing to Evaluate:
Company: {job.company}
Role: {job.role}
Required Experience: {job.required_experience}
Major Skills: {', '.join(job.major_skills)}
"""
        response = self.client.models.generate_content(
            model=self.settings.default_model_fast,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=FilteredJob,
            ),
        )

        # In google-genai, the structured output can be mapped back to Pydantic if needed,
        # but returning response_schema validates the JSON response.
        # We parse the response JSON string into our FilteredJob model.
        import json as json_mod
        response_dict = json_mod.loads(response.text)
        
        # Ensure job_id, company, and role are explicitly tied back since the LLM might mess it up
        response_dict["job_id"] = job.id
        response_dict["company"] = job.company
        response_dict["role"] = job.role
        
        return FilteredJob(**response_dict)
