from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any

class PipelineRunRequest(BaseModel):
    lane: Literal["fast_lane", "normal_lane"] = "normal_lane"
    custom_keywords: Optional[List[str]] = None

class JobIngestRequest(BaseModel):
    url: str
    company: str
    role: str
    location: str
    salary: Optional[str] = None
    major_skills: List[str] = Field(default_factory=list)
    required_experience: str = ""

class ApprovalDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT", "REVISE"]
    feedback: Optional[str] = None

class JobResponse(BaseModel):
    id: str
    url: str
    company: str
    role: str
    location: str
    salary: Optional[str] = None
    status: str
    payload: Optional[Dict[str, Any]] = None
    updated_at: str

class SystemStatusResponse(BaseModel):
    status: str
    env: str
    default_model_fast: str
    default_model_pro: str
    database_connected: bool
