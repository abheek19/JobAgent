from typing import List
from datetime import datetime, timezone, timedelta
from schemas import DiscoveredJob, generate_job_id

def _create_mock_job(
    company: str, 
    role: str, 
    url: str, 
    source: str, 
    hours_ago: int,
    location: str = "San Francisco, CA",
    remote_hybrid: str = "Remote"
) -> DiscoveredJob:
    return DiscoveredJob(
        company=company,
        role=role,
        location=location,
        remote_hybrid=remote_hybrid,
        posted_timestamp=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        salary="$180k - $220k",
        url=url,
        required_experience="5+ years",
        major_skills=["Python", "Cloud"],
        source=source
    )

def get_mock_jobs(scout_name: str, time_range_hours: int) -> List[DiscoveredJob]:
    """
    Returns deterministic lists of jobs for testing purposes based on the scout.
    Only returns jobs that are 'newer' than the time_range_hours.
    """
    
    # We define a static universe of jobs with specific 'hours_ago'
    # For testing, we ensure that:
    # 1. Some jobs overlap (same URL) across different scouts to test deduplication.
    # 2. Some jobs are within 1-3 hours (fast lane), some are older (normal lane).
    
    all_mock_jobs = {
        "LinkedInScout": [
            _create_mock_job("Google", "Senior Engineer", "https://linkedin.com/jobs/google123", "LinkedIn", 2),
            _create_mock_job("Meta", "Software Architect", "https://linkedin.com/jobs/meta456", "LinkedIn", 12),
            # Overlap with CompanyDirect
            _create_mock_job("Stripe", "Backend Engineer", "https://jobs.lever.co/stripe/789", "LinkedIn", 20),
        ],
        "CompanyDirectScout": [
            _create_mock_job("Stripe", "Backend Engineer", "https://jobs.lever.co/stripe/789", "CompanyDirect", 20), # Duplicate URL
            _create_mock_job("Airbnb", "Principal Engineer", "https://boards.greenhouse.io/airbnb/101", "CompanyDirect", 1),
        ],
        "BoardsScout": [
            _create_mock_job("Netflix", "Data Engineer", "https://indeed.com/viewjob?jk=123", "Indeed", 5),
            _create_mock_job("Amazon", "SDE III", "https://ziprecruiter.com/jobs/amazon1", "ZipRecruiter", 22),
        ],
        "StartupScout": [
            _create_mock_job("OpenAI", "Research Engineer", "https://wellfound.com/jobs/openai99", "Wellfound", 1),
            _create_mock_job("Anthropic", "Alignment Engineer", "https://workatastartup.com/jobs/anthropic88", "YC", 2),
        ],
        "AcademicScout": [
            _create_mock_job("Stanford", "Research Scientist", "https://higheredjobs.com/stanford/12", "HigherEdJobs", 10),
            _create_mock_job("MIT", "Postdoc Researcher", "https://higheredjobs.com/mit/34", "HigherEdJobs", 23),
        ]
    }
    
    jobs = all_mock_jobs.get(scout_name, [])
    # Filter by time_range
    now = datetime.now(timezone.utc)
    filtered = [
        job for job in jobs 
        if (now - job.posted_timestamp).total_seconds() / 3600.0 <= time_range_hours
    ]
    return filtered
