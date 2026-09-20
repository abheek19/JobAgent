import { useEffect, useState } from 'react';
import { api, type Job, type JobPackage, type SystemStatus } from './api';
import { Briefcase, Activity, Clock, Play, FileText, Upload } from 'lucide-react';

function App() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Job[]>([]);
  const [selectedJobPkg, setSelectedJobPkg] = useState<JobPackage | null>(null);
  const [loadingPkg, setLoadingPkg] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>('');
  const [uploading, setUploading] = useState<boolean>(false);

  const fetchStatus = () => api.getHealth().then(setStatus).catch(console.error);
  const fetchJobs = () => api.getJobs().then(setJobs).catch(console.error);
  const fetchPending = () => api.getPendingApprovals().then(setPendingApprovals).catch(console.error);

  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    fetchStatus();
    fetchJobs();
    fetchPending();
    
    if (!autoRefresh) return;
    
    const interval = setInterval(() => {
      fetchStatus();
      fetchJobs();
      fetchPending();
    }, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const [lane, setLane] = useState<'normal_lane' | 'fast_lane'>('normal_lane');

  const handleRunPipeline = async () => {
    try {
      await api.runPipeline(lane);
      alert(`Pipeline started in ${lane}!`);
    } catch (e) {
      alert('Failed to start pipeline');
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith('.pdf')) {
      alert("Only PDF files are supported!");
      return;
    }
    
    setUploading(true);
    try {
      await api.uploadResume(file);
      alert("Resume successfully uploaded and parsed into the target schema!");
    } catch (e: any) {
      alert("Failed to upload resume: " + (e.response?.data?.detail || e.message));
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleDecision = async (threadId: string, decision: 'APPROVE' | 'REJECT' | 'REVISE') => {
    try {
      await api.makeApprovalDecision(threadId, decision, feedback);
      setFeedback('');
      alert(`Decision ${decision} sent.`);
      fetchPending();
      fetchJobs();
    } catch (e) {
      alert('Failed to submit decision.');
    }
  };

  const loadJobPackage = async (jobId: string) => {
    setLoadingPkg(true);
    try {
      const pkg = await api.getJobPackage(jobId);
      setSelectedJobPkg(pkg);
    } catch (e) {
      alert('Failed to load job package or not generated yet.');
    } finally {
      setLoadingPkg(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 space-y-6">
      <header className="flex justify-between items-center bg-white p-4 rounded-xl shadow">
        <div className="flex items-center space-x-3">
          <Briefcase className="text-blue-600" size={32} />
          <h1 className="text-2xl font-bold text-gray-800">Job Hunter Dashboard</h1>
        </div>
        <div className="flex items-center space-x-4">
          <label className="flex items-center space-x-2 text-sm text-gray-600 cursor-pointer">
            <input 
              type="checkbox" 
              checked={autoRefresh} 
              onChange={e => setAutoRefresh(e.target.checked)} 
              className="rounded text-blue-600 focus:ring-blue-500"
            />
            <span>Auto-refresh (10s)</span>
          </label>
          <label className="flex items-center space-x-2 bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded shadow transition cursor-pointer border border-gray-300">
            {uploading ? <Activity className="animate-spin" size={18} /> : <Upload size={18} />}
            <span className="text-sm font-medium">{uploading ? 'Parsing...' : 'Upload PDF Resume'}</span>
            <input type="file" accept=".pdf" className="hidden" onChange={handleFileUpload} disabled={uploading} />
          </label>
          <select 
            value={lane} 
            onChange={(e) => setLane(e.target.value as any)}
            className="border p-2 rounded text-sm bg-gray-50"
          >
            <option value="normal_lane">Normal Lane</option>
            <option value="fast_lane">Fast Lane</option>
          </select>
          <button 
            onClick={handleRunPipeline}
            className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded shadow transition"
          >
            <Play size={18} />
            <span>Run Pipeline</span>
          </button>
          {status && (
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm font-medium ${status.database_connected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
              <Activity size={16} />
              <span>{status.database_connected ? 'System Online' : 'Database Error'}</span>
            </div>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <section className="bg-white p-6 rounded-xl shadow">
            <h2 className="text-xl font-bold mb-4 flex items-center"><Clock className="mr-2" /> Pending Approvals ({pendingApprovals.length})</h2>
            {pendingApprovals.length === 0 ? (
              <p className="text-gray-500">No pending approvals.</p>
            ) : (
              <div className="space-y-4">
                {pendingApprovals.map(job => (
                  <div key={job.id} className="border border-yellow-200 bg-yellow-50 p-4 rounded-lg">
                    <h3 className="font-semibold text-lg">{job.role} @ {job.company}</h3>
                    <p className="text-sm text-gray-600 mb-2">{job.location} | {job.salary || 'Unknown Salary'}</p>
                    <div className="mt-3 space-y-2">
                      <input 
                        type="text" 
                        placeholder="Feedback (if revising)" 
                        className="w-full p-2 border rounded"
                        value={feedback}
                        onChange={e => setFeedback(e.target.value)}
                      />
                      <div className="flex space-x-2">
                        <button onClick={() => handleDecision(job.id, 'APPROVE')} className="flex-1 bg-green-500 text-white py-1 rounded hover:bg-green-600 transition">Approve</button>
                        <button onClick={() => handleDecision(job.id, 'REVISE')} className="flex-1 bg-orange-500 text-white py-1 rounded hover:bg-orange-600 transition">Revise</button>
                        <button onClick={() => handleDecision(job.id, 'REJECT')} className="flex-1 bg-red-500 text-white py-1 rounded hover:bg-red-600 transition">Reject</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="bg-white p-6 rounded-xl shadow">
            <h2 className="text-xl font-bold mb-4">Discovered Jobs ({jobs.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="p-3">Company</th>
                    <th className="p-3">Role</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {jobs.map(job => (
                    <tr key={job.id} className="hover:bg-gray-50">
                      <td className="p-3 font-medium">{job.company}</td>
                      <td className="p-3">{job.role}</td>
                      <td className="p-3">
                        <span className="bg-gray-200 text-gray-800 px-2 py-1 rounded text-xs">
                          {job.status}
                        </span>
                      </td>
                      <td className="p-3">
                        <button 
                          onClick={() => loadJobPackage(job.id)}
                          className="text-blue-600 hover:underline flex items-center space-x-1"
                        >
                          <FileText size={16} /> <span>Package</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="lg:col-span-1">
          <section className="bg-white p-6 rounded-xl shadow sticky top-4">
            <h2 className="text-xl font-bold mb-4">Job Package Details</h2>
            {loadingPkg && <p>Loading...</p>}
            {!loadingPkg && !selectedJobPkg && <p className="text-gray-500 text-sm">Select a job package to view details.</p>}
            
            {!loadingPkg && selectedJobPkg && (
              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold text-gray-700">Company Brief</h3>
                  <div className="text-sm bg-gray-50 p-2 rounded border max-h-40 overflow-y-auto whitespace-pre-wrap">
                    {selectedJobPkg.company_brief || 'Not available'}
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-700">Cover Letter</h3>
                  <div className="text-sm bg-gray-50 p-2 rounded border max-h-60 overflow-y-auto whitespace-pre-wrap">
                    {selectedJobPkg.cover_letter || 'Not available'}
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-700">Outreach Notes</h3>
                  <div className="text-sm bg-gray-50 p-2 rounded border max-h-40 overflow-y-auto whitespace-pre-wrap">
                    {selectedJobPkg.outreach_notes || 'Not available'}
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-700">Tailored CV</h3>
                  <div className="text-sm bg-gray-50 p-2 rounded border max-h-60 overflow-y-auto whitespace-pre-wrap">
                    {selectedJobPkg.cv_prepared || 'Not available'}
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

export default App;
