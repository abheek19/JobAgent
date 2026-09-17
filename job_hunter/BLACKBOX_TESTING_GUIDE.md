# Black-Box Testing Guide: Job Hunting Department

This guide provides a comprehensive step-by-step manual testing protocol for end users, QA engineers, and system integrators to validate the end-to-end functionality of the Job Hunting Department.

## Prerequisites

Before executing manual testing, ensure the following environment configurations are met:

1. **Python Environment**: You must have `uv` installed.
2. **Environment Variables**:
   - `GEMINI_API_KEY`: Must be set for the screening and deepening engines to function.
   - Example: `set GEMINI_API_KEY=your-api-key-here` (Windows) or `export GEMINI_API_KEY=your-api-key-here` (Unix).
3. **Database Initialization**: 
   - Ensure the SQLite database (`job_hunt.db`) is initialized. Running the orchestrator for the first time will automatically create and provision the schema.

## Step-by-Step Manual CLI Walk-through

### 1. Injecting Custom Test Listings

To test the system against specific mock jobs:
- Use the `master_cv_template.json` to configure the target candidate profile. The screening engine uses this as the "ground truth" to evaluate jobs.
- The `DiscoveryEngine` normally pulls from active feeds. For localized testing without hitting external sites, you can manually insert rows into the `jobs` table of `job_hunt.db` with a status of `DISCOVERED` and the JSON payload matching the `DiscoveredJob` schema.

### 2. Triggering the Orchestrator

The system operates in two execution modes:

- **Fast Lane**: Prioritizes jobs from direct sources or specific companies.
  ```bash
  uv run python orchestrator/cli.py --lane fast_lane
  ```
- **Normal Lane**: Scours all standard job board streams.
  ```bash
  uv run python orchestrator/cli.py --lane normal_lane
  ```

Run the command to begin the pipeline. The CLI will provide real-time updates as jobs transition through `DISCOVERED` -> `SCREENED` -> `HIGH_MATCH` -> `APP_READY`.

### 3. Inspecting the Rich Terminal Digest

Once jobs reach the `APP_READY` state, the LangGraph supervisor pauses execution at the `interrupt()` gate.
- The CLI will render a `rich` terminal digest containing tables for each `APP_READY` job.
- You will see the **Company**, **Role**, **Match Evidence** (from the filter engine), the **Business Summary** (from the investigator), and the **Contact** person found.
- The prompt will ask for a decision: `APPROVE`, `REJECT`, `REVISE`, or `QUIT`.

### 4. Verification Checklists

After entering your decision (e.g., `APPROVE`), verify the system state:

- **Database State (`job_hunt.db`)**:
  ```bash
  sqlite3 job_hunt.db "SELECT status, json_extract(payload, '$.applied') FROM jobs WHERE id = '<job_id>';"
  ```
  Expected Output for `APPROVE`: `APPLIED|Yes`
  Expected Output for `REJECT`: `REJECTED|`

- **Spreadsheet State (`Job-Hunt-Master.csv`)**:
  Open `Job-Hunt-Master.csv` in Excel or Google Sheets.
  Check that the following columns match your decision:
  - `status` should be `APPLIED` (if approved) or `REJECTED`.
  - `cv_prepared` should be `Yes`.
  - `contact_found` should be `Yes` (if a contact was identified).

### 5. Failure Modes & Troubleshooting

- **Duplicate URLs**: The system uses a deterministic SHA-256 hash of the job URL as the primary key. Re-ingesting the same job URL will safely fail due to SQLite `UNIQUE` constraints (Idempotent Re-ingestion). Check logs for `sqlite3.IntegrityError`.
- **SQLite WAL Checkpoints**: The database runs in Write-Ahead Log (WAL) mode. If `job_hunt.db-wal` grows excessively large, run `sqlite3 job_hunt.db "PRAGMA wal_checkpoint(TRUNCATE);"` to merge and truncate.
- **Process Crashes**: LangGraph's `MemorySaver` checkpointer ensures thread states are preserved. If the process crashes during an active run, simply re-run the CLI with the same `--lane` argument; the graph will resume from the last saved state.
