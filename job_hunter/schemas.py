from pydantic import BaseModel, Field, field_validator, model_validator, HttpUrl
from typing import List, Optional, Literal
from datetime import datetime, timezone
import hashlib

def generate_job_id(url: str) -> str:
    """Deterministic SHA-256 URL-hashing function."""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()

class DiscoveredJob(BaseModel):
    id: str = Field(default="")
    company: str
    role: str
    location: str
    remote_hybrid: str
    posted_timestamp: datetime
    salary: Optional[str] = None
    url: HttpUrl
    required_experience: str
    major_skills: List[str]
    source: str
    
    @field_validator('posted_timestamp', mode='before')
    @classmethod
    def enforce_timezone(cls, v):
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v
    
    @model_validator(mode='after')
    def set_id(self):
        if not self.id:
            # Generate ID from string representation of url
            self.id = generate_job_id(str(self.url))
        return self

class FilteredJob(BaseModel):
    job_id: str
    company: str
    role: str
    classification: Literal["High Match", "Possible Match", "Reject"]
    match_evidence: str
    missing_qualifications: List[str]

class ResearchedJob(BaseModel):
    job_id: str
    company: str
    business_summary: str
    recent_developments: str
    hiring_context: str
    source_links: List[HttpUrl]

class NetworkLead(BaseModel):
    job_id: str
    contact_name: str
    contact_role: str
    profile_url: HttpUrl
    relevance_reasoning: str
    drafted_outreach_message: str

class TailoredMaterial(BaseModel):
    job_id: str
    tailored_cv_diff: str
    tailored_cover_letter: str
    adherence_guarantee: str

class PipelineRecord(BaseModel):
    job_id: str
    status: str
    company: str
    role: str
    url: HttpUrl
    location: str
    salary: Optional[str] = None
    classification: Optional[str] = None
    contact_name: Optional[str] = None
    contact_found: Optional[str] = None
    cv_prepared: Optional[str] = None
    updated_at: datetime
