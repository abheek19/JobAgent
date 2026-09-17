import asyncio

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from schemas import ResearchedJob, NetworkLead, DiscoveredJob
from investigator.company_investigator import CompanyInvestigator
from investigator.network_scout import NetworkScout

class MockCompanyInvestigator(CompanyInvestigator):
    def __init__(self):
        pass

    async def investigate(self, job: DiscoveredJob) -> ResearchedJob:
        await asyncio.sleep(0.1) # Simulate network delay
        return ResearchedJob(
            job_id=job.id,
            company=job.company,
            business_summary=f"{job.company} is a leading technology firm specializing in innovative solutions.",
            recent_developments=f"Recently launched a new AI product.",
            hiring_context=f"Expanding their {job.role} team to support new initiatives.",
            source_links=["https://example.com/news", "https://example.com/about"]
        )

class MockNetworkScout(NetworkScout):
    def __init__(self):
        pass

    async def scout(self, job: DiscoveredJob) -> NetworkLead:
        await asyncio.sleep(0.1) # Simulate network delay
        return NetworkLead(
            job_id=job.id,
            contact_name="Jane Doe",
            contact_role="Technical Recruiter",
            profile_url="https://linkedin.com/in/janedoe",
            relevance_reasoning="Jane handles tech hiring for this department.",
            drafted_outreach_message=f"Hi Jane, I'm interested in the {job.role} role at {job.company}."
        )
