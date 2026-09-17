import sqlite3
import threading
from typing import Optional, Dict, List
import json
from datetime import datetime, timezone
import csv
import tempfile
import os
import shutil

from schemas import DiscoveredJob, generate_job_id, PipelineRecord
from config import get_settings

class JobRepository:
    VALID_TRANSITIONS = {
        "DISCOVERED": {"SCREENED", "REJECTED"},
        "SCREENED": {"HIGH_MATCH", "POSSIBLE_MATCH", "REJECTED"},
        "POSSIBLE_MATCH": {"HIGH_MATCH", "REJECTED"},
        "HIGH_MATCH": {"APP_READY", "REJECTED"},
        "APP_READY": {"APPROVED", "REJECTED"},
        "APPROVED": {"APPLIED", "REJECTED"},
        "APPLIED": {"INTERVIEW", "REJECTED"},
        "INTERVIEW": {"REJECTED", "OFFER"},
        "REJECTED": set(),
        "OFFER": set(),
    }

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            url = get_settings().database_url
            if url.startswith("sqlite:///"):
                self.db_path = url.replace("sqlite:///", "")
            else:
                self.db_path = "job_hunt.db"
        else:
            self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    company TEXT NOT NULL,
                    role TEXT NOT NULL,
                    location TEXT NOT NULL,
                    salary TEXT,
                    status TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)')

    def insert_discovered_job(self, job: DiscoveredJob) -> bool:
        conn = self._get_conn()
        try:
            with conn:
                now = datetime.now(timezone.utc).isoformat()
                job_dict = job.model_dump(mode='json')
                conn.execute('''
                    INSERT INTO jobs (id, url, company, role, location, salary, status, payload, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job.id,
                    str(job.url),
                    job.company,
                    job.role,
                    job.location,
                    job.salary,
                    "DISCOVERED",
                    json.dumps(job_dict),
                    now,
                    now
                ))
            return True
        except sqlite3.IntegrityError:
            return False

    def update_job_status(self, job_id: str, new_status: str, payload: Optional[Dict] = None) -> bool:
        if new_status not in self.VALID_TRANSITIONS:
            raise ValueError(f"Invalid status: {new_status}")
            
        conn = self._get_conn()
        with conn:
            cursor = conn.execute('SELECT status, payload FROM jobs WHERE id = ?', (job_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Job {job_id} not found")
                
            current_status = row['status']
            if new_status != current_status and new_status not in self.VALID_TRANSITIONS.get(current_status, set()):
                raise ValueError(f"Invalid state transition from {current_status} to {new_status}")
            
            current_payload = json.loads(row['payload']) if row['payload'] else {}
            if payload:
                current_payload.update(payload)
                
            now = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                UPDATE jobs 
                SET status = ?, payload = ?, updated_at = ?
                WHERE id = ?
            ''', (new_status, json.dumps(current_payload), now, job_id))
            
        return True

    def get_pending_jobs(self, status: str) -> List[Dict]:
        conn = self._get_conn()
        cursor = conn.execute('SELECT * FROM jobs WHERE status = ?', (status,))
        results = []
        for row in cursor:
            d = dict(row)
            if d['payload']:
                d['payload'] = json.loads(d['payload'])
            results.append(d)
        return results

    def sync_to_csv(self, filepath: Optional[str] = None) -> None:
        if filepath is None:
            filepath = get_settings().csv_export_path
        conn = self._get_conn()
        cursor = conn.execute('SELECT id, company, role, location, salary, url, status, payload, updated_at FROM jobs ORDER BY updated_at DESC')
        rows = cursor.fetchall()
        
        records = []
        for r in rows:
            payload = json.loads(r['payload']) if r['payload'] else {}
            classification = payload.get('classification')
            contact_name = payload.get('contact_name')
            contact_found = payload.get('contact_found')
            cv_prepared = payload.get('cv_prepared')
            record = PipelineRecord(
                job_id=r['id'],
                status=r['status'],
                company=r['company'],
                role=r['role'],
                url=r['url'],
                location=r['location'],
                salary=r['salary'],
                classification=classification,
                contact_name=contact_name,
                contact_found=contact_found,
                cv_prepared=cv_prepared,
                updated_at=datetime.fromisoformat(r['updated_at'])
            )
            records.append(record)
            
        target_dir = os.path.dirname(os.path.abspath(filepath)) or '.'
        fd, temp_path = tempfile.mkstemp(dir=target_dir)
        
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
            if not records:
                writer = csv.writer(f)
                writer.writerow(list(PipelineRecord.model_fields.keys()))
            else:
                writer = csv.DictWriter(f, fieldnames=list(PipelineRecord.model_fields.keys()))
                writer.writeheader()
                for rec in records:
                    writer.writerow(rec.model_dump(mode='json'))
                    
        shutil.move(temp_path, filepath)

if __name__ == "__main__":
    repo = JobRepository()
    conn = repo._get_conn()
    cursor = conn.execute('SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status')
    print("Pipeline Counts by Status:")
    for row in cursor:
        print(f"- {row['status']}: {row['cnt']}")
