from typing import Dict, Any
from schemas import DiscoveredJob, ResearchedJob, TailoredMaterial

class MockApplicationTailor:
    """Deterministic offline mock evaluator conforming to ApplicationTailor."""
    
    def generate_materials(self, master_cv: Dict[str, Any], job: DiscoveredJob, research: ResearchedJob) -> TailoredMaterial:
        # Generate a deterministic response that doesn't hallucinate.
        # We ensure it only uses entities from master_cv (e.g. Python, AWS, Tech Innovators Inc.)
        return TailoredMaterial(
            job_id=job.id,
            tailored_cv_diff="HIGHLIGHT: Architected microservices at Tech Innovators Inc. SKILLS: Python, AWS.",
            tailored_cover_letter=f"Dear {job.company} team, Given your recent developments ({research.recent_developments}), my experience at Tech Innovators Inc. with Python aligns perfectly.",
            adherence_guarantee="True"
        )
