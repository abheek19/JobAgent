from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import sys
import pathlib

# Add the parent directory to sys.path so we can import internal modules easily
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from config import get_settings
from api.schemas import (
    PipelineRunRequest,
    JobIngestRequest,
    ApprovalDecisionRequest,
    JobResponse,
    SystemStatusResponse
)
from api.service import (
    run_pipeline_background,
    get_pending_approvals,
    resume_approval,
    ingest_job,
    get_all_jobs,
    get_job,
    repo
)
from schemas import DiscoveredJob

app = FastAPI(title="Job Hunting Department API", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=SystemStatusResponse)
async def health_check():
    settings = get_settings()
    db_ok = True
    try:
        repo._get_conn().execute("SELECT 1")
    except Exception:
        db_ok = False
        
    return SystemStatusResponse(
        status="ok",
        env=settings.app_env,
        default_model_fast=settings.default_model_fast,
        default_model_pro=settings.default_model_pro,
        database_connected=db_ok
    )

@app.post("/api/v1/pipeline/run")
async def run_pipeline(request: PipelineRunRequest, background_tasks: BackgroundTasks):
    thread_id = str(uuid.uuid4())
    background_tasks.add_task(run_pipeline_background, thread_id, request.lane)
    return {"status": "accepted", "thread_id": thread_id, "lane": request.lane}

@app.post("/api/v1/jobs/ingest")
async def ingest_job_endpoint(request: JobIngestRequest):
    job = DiscoveredJob(
        company=request.company,
        role=request.role,
        location=request.location,
        salary=request.salary,
        url=request.url,
        major_skills=request.major_skills,
        required_experience=request.required_experience,
        remote_hybrid="Unknown",
        source="webhook",
        posted_timestamp=datetime.now(timezone.utc)
    )
    success = ingest_job(job)
    if not success:
        raise HTTPException(status_code=400, detail="Job already exists or could not be ingested")
    return {"status": "success", "job_id": job.id}

@app.get("/api/v1/jobs", response_model=List[JobResponse])
async def list_jobs(status: Optional[str] = Query(None)):
    jobs = get_all_jobs(status)
    return [JobResponse(**j) for j in jobs]

@app.get("/api/v1/approvals/pending", response_model=List[JobResponse])
async def get_pending_approvals_endpoint():
    jobs = get_pending_approvals()
    return [JobResponse(**j) for j in jobs]

@app.post("/api/v1/approvals/{thread_id}/decision")
async def make_approval_decision(thread_id: str, request: ApprovalDecisionRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(resume_approval, thread_id, request.decision, request.feedback)
    return {"status": "accepted", "thread_id": thread_id, "decision": request.decision}

@app.get("/api/v1/jobs/{job_id}/package")
async def get_job_package(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    payload = job.get("payload", {})
    return {
        "job_id": job_id,
        "company_brief": payload.get("business_summary"),
        "cv_prepared": payload.get("cv_prepared"),
        "cover_letter": payload.get("cover_letter"),
        "outreach_notes": payload.get("outreach_draft")
    }

from fastapi import UploadFile, File
import os
import json
from google import genai

@app.post("/api/v1/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Uploads a PDF resume, parses it using Gemini File API, and updates master_cv_template.json"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
        
    try:
        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)
        
        uploaded_file = client.files.upload(file=temp_path)
        
        with open("master_cv_template.json", "r") as f:
            template_schema = json.load(f)
            
        prompt = f"""
        Extract the information from this resume PDF and map it strictly into this JSON schema structure.
        Leave fields empty if the information is not present in the resume. 
        Do not add new fields outside this structure.
        
        Target Schema:
        {json.dumps(template_schema, indent=2)}
        """
        
        response = client.models.generate_content(
            model=settings.default_model_fast,
            contents=[uploaded_file, prompt],
            config={"response_mime_type": "application/json"}
        )
        
        extracted_data = json.loads(response.text)
        
        with open("master_cv_template.json", "w") as f:
            json.dump(extracted_data, f, indent=2)
            
        return {"message": "Resume successfully uploaded and parsed.", "data": extracted_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Mount the static assets directory from the built React app
dist_assets_path = os.path.join(pathlib.Path(__file__).parent.parent, "frontend", "dist", "assets")
if os.path.exists(dist_assets_path):
    app.mount("/assets", StaticFiles(directory=dist_assets_path), name="assets")

# Catch-all route to serve the React SPA
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    dist_dir = os.path.join(pathlib.Path(__file__).parent.parent, "frontend", "dist")
    file_path = os.path.join(dist_dir, full_path)
    
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
        
    return {"message": "Frontend not built yet. Run 'npm run build' in the frontend directory."}
