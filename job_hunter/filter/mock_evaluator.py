from typing import List
from schemas import DiscoveredJob, FilteredJob

class MockEvaluator:
    """Deterministic offline evaluator stub to allow end-to-end testing without Gemini."""
    
    def __init__(self, master_cv_path: str = "master_cv_template.json"):
        pass

    def screen_job(self, job: DiscoveredJob) -> FilteredJob:
        missing = []
        # Anti-hallucination test checks
        major_skills_lower = [s.lower() for s in job.major_skills]
        if "rust" in major_skills_lower:
            missing.append("Rust is absent from Master CV.")
        if "cobol" in major_skills_lower:
            missing.append("Cobol is absent from Master CV.")
        
        # Simulated Years of Experience logic for the test
        if "quantum computing" in job.role.lower() and "10+ years" in job.required_experience.lower():
            missing.append("10+ years Quantum Computing is absent from Master CV.")

        if missing:
            return FilteredJob(
                job_id=job.id,
                company=job.company,
                role=job.role,
                classification="Reject",
                match_evidence="Candidate lacks mandatory requirements.",
                missing_qualifications=missing
            )

        if "python" in major_skills_lower or "senior" in job.role.lower():
            return FilteredJob(
                job_id=job.id,
                company=job.company,
                role=job.role,
                classification="High Match",
                match_evidence="Candidate has extensive Python experience and is targeting Senior roles.",
                missing_qualifications=[]
            )

        return FilteredJob(
            job_id=job.id,
            company=job.company,
            role=job.role,
            classification="Possible Match",
            match_evidence="Role aligns partially with skills.",
            missing_qualifications=[]
        )
