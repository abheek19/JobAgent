import axios from 'axios';

// If in development mode (Vite), point to the FastAPI port. Otherwise, use relative path (handled by FastAPI in prod)
const API_URL = import.meta.env.DEV ? 'http://localhost:8000' : '';

export const apiClient = axios.create({
  baseURL: API_URL,
});

export interface Job {
  id: string;
  url: string;
  company: string;
  role: string;
  location: string;
  salary?: string;
  status: string;
  updated_at: string;
}

export interface JobPackage {
  job_id: string;
  company_brief?: string;
  cv_prepared?: string;
  cover_letter?: string;
  outreach_notes?: string;
}

export interface SystemStatus {
  status: string;
  env: string;
  default_model_fast: string;
  default_model_pro: string;
  database_connected: boolean;
}

export const api = {
  getHealth: () => apiClient.get<SystemStatus>('/health').then(res => res.data),
  getJobs: (status?: string) => apiClient.get<Job[]>('/api/v1/jobs', { params: { status } }).then(res => res.data),
  getPendingApprovals: () => apiClient.get<Job[]>('/api/v1/approvals/pending').then(res => res.data),
  runPipeline: (lane: 'fast_lane' | 'normal_lane' = 'normal_lane') => 
    apiClient.post('/api/v1/pipeline/run', { lane }).then(res => res.data),
  makeApprovalDecision: (threadId: string, decision: 'APPROVE' | 'REJECT' | 'REVISE', feedback?: string) => 
    apiClient.post(`/api/v1/approvals/${threadId}/decision`, { decision, feedback }).then(res => res.data),
  getJobPackage: (jobId: string) => apiClient.get<JobPackage>(`/api/v1/jobs/${jobId}/package`).then(res => res.data),
  uploadResume: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/v1/resume/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(res => res.data);
  }
};
