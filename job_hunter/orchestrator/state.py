from typing import TypedDict, List, Dict, Any, Optional, Literal

class JobDepartmentGraphState(TypedDict):
    thread_id: str
    lane: Literal["fast_lane", "normal_lane"]
    candidate_cv: Dict[str, Any]
    target_preferences: Dict[str, Any]
    pending_job_ids: List[str]
    current_stage: str
    human_decision: Optional[Literal["APPROVE", "REJECT", "REVISE"]]
    review_feedback: Optional[str]
    active_alerts: List[Dict[str, Any]]
