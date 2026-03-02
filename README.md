# AgileGPT

AgileGPT is an **AI-powered SCRUM team** that builds full-stack web applications autonomously. You give it a nonprofit's annual report PDF, and it extracts the organization's profile, plans a multi-sprint development roadmap, and executes every sprint using specialized AI agents — producing a working React + Flask website at `localhost:5000` with zero human coding.

## How It Works

AgileGPT automates the entire software development lifecycle using four AI agents that mirror a real SCRUM team:

```
Annual Report PDF
       |
       v
  [RAG Service] -----> Extracts nonprofit profile from PDF
       |
       v
  [Manager Agent] ---> Conversational review with user (chat UI)
       |                User confirms profile
       v
  [PM Agent] ---------> Plans 5 sprints with tasks, API contracts, and test specs
       |
       v
  For each sprint:
  |  [Backend Agent] -> Writes Flask routes, data models, CSV persistence
  |  [Frontend Agent] -> Writes React components, forms, styling
  |  [QA Agent] ------> Writes and runs pytest tests against live server
  |  [PM Agent] ------> Reviews results, adjusts future sprints if needed
  |  [JIRA] ----------> Creates/updates sprint tickets in real time
       |
       v
  Site launches at http://localhost:5000
```

### The Agents

| Agent | Role | Model | What It Produces |
|-------|------|-------|-----------------|
| **Manager** | Reviews extracted profile with user in chat | GPT-4.1-mini | Finalized nonprofit profile |
| **PM** | Plans sprints, reviews results, adapts the roadmap | OpenAI o3 | Sprint plan JSON, API contracts |
| **Backend** | Writes Flask API code with CSV data persistence | Azure GPT-4.1 | `app.py`, route blueprints, `data/*.csv` |
| **Frontend** | Writes React components served via CDN | Azure GPT-4.1 | `index.html`, `src/components/*.js`, CSS |
| **QA** | Writes and runs integration + frontend tests | Azure GPT-4.1 | `tests/test_api.py`, `tests/test_frontend.py` |

### Key Design Decisions

- **Shared API Contract**: The PM defines every endpoint (path, method, request/response schema) upfront. All agents reference this contract so frontend fetch calls match backend routes exactly.
- **CSV Persistence**: Every form on the frontend (donations, signups, contacts) has a backend endpoint that writes to a CSV file in `data/`. A matching GET endpoint reads from the same CSV, and the frontend renders stored entries back to the user (e.g., "Recent Donors" list).
- **Iterative Memory**: Agents receive the actual workspace files from disk each sprint, plus a log of their own prior work. This means Sprint 3's frontend agent sees everything Sprint 1 and 2's frontend agent wrote, and builds on top of it.
- **Adaptive Planning**: After each sprint, the PM reviews pass/fail results and can modify future tasks or insert up to 2 additional sprints (max 7 total) to fix issues.
- **Workspace Isolation**: Each project gets its own directory with a dedicated Python venv, so multiple projects don't interfere.

## Project Structure

```
agilegpt/
├── app.py                    # Flask API server (upload, chat, confirm, pipeline status)
├── run.py                    # CLI entry point — runs the full pipeline headlessly
├── config.py                 # Loads and validates environment variables
├── requirements.txt          # Python dependencies
├── .env                      # API keys and config (not committed)
│
├── agents/
│   ├── base_agent.py         # Base class — wraps an LLM call with a system prompt
│   ├── manager.py            # Profile review chat agent (pre-SCRUM)
│   ├── pm_agent.py           # PM agent — planning, review, retrospective modes
│   ├── backend_agent.py      # Backend dev agent — Flask routes and data persistence
│   ├── frontend_agent.py     # Frontend dev agent — React components and styling
│   └── qa_agent.py           # QA agent — integration and frontend tests
│
├── orchestrator/
│   ├── engine.py             # The brain — runs the full SCRUM loop
│   └── state.py              # Pydantic models for project state, agent memory, sprint records
│
├── services/
│   ├── llm_service.py        # Multi-provider LLM wrapper (OpenAI + Azure OpenAI)
│   ├── rag_service.py        # PDF text extraction + LLM-based profile extraction
│   └── jira_package/         # JIRA REST API client (sprints, issues, bulk operations)
│       ├── client.py
│       ├── issues.py
│       ├── sprints.py
│       └── delete_ops.py
│
├── frontend/                 # Next.js dashboard UI (upload, chat, pipeline monitor)
│   ├── app/
│   │   ├── page.tsx
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── package.json
│   └── ...
│
└── workspaces/               # Generated project output (one folder per project)
    └── <project-id>/
        ├── .venv/            # Isolated Python venv
        ├── app.py            # Generated Flask backend
        ├── index.html        # Generated React frontend
        ├── src/components/   # Generated React component JS files
        ├── static/           # Generated CSS
        ├── routes/           # Generated Flask blueprints
        ├── data/             # CSV files written by form submissions
        ├── tests/            # Generated pytest test files
        └── scrum_plan.json   # The PM's sprint plan (updated after each sprint)
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the dashboard frontend)
- An Azure OpenAI deployment (GPT-4.1)
- An OpenAI API key (for o3)
- A JIRA Cloud project with API access

### 1. Install Python dependencies

```bash
cd agilegpt
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the `agilegpt/` directory:

```env
# Azure OpenAI (used by Backend, Frontend, QA agents + RAG extraction)
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_41=gpt-41           # GPT-4.1 deployment name
AZURE_OPENAI_DEPLOYMENT_41_MINI=gpt-41-mini # GPT-4.1-mini deployment name

# OpenAI (used by PM agent)
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL_O3=o3

# JIRA Cloud
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
JIRA_BOARD_ID=123
```

### 3. Install the dashboard frontend

```bash
cd agilegpt/frontend
npm install
```

## Usage

### Option A: Full pipeline via CLI (headless)

The fastest way to run AgileGPT. Edit the brief in `engine.py` or pass your own, then:

```bash
cd agilegpt
python run.py
```

This will:
1. Plan 5 sprints via the PM agent
2. Execute each sprint (backend -> frontend -> QA)
3. PM reviews and adjusts after each sprint
4. Launch the generated site at `http://localhost:5000`

Output shows pass/fail per task:
```
Sprint 1:
  [PASS] Set up Flask app with health endpoint and donation routes
  [PASS] Build React shell with navigation and hero section
  [FAIL] Integration tests for health and donation endpoints
Sprint 2:
  ...
```

### Option B: Full workflow via web UI

Run both the AgileGPT backend and the Next.js dashboard:

```bash
# Terminal 1: AgileGPT API server
cd agilegpt
python app.py

# Terminal 2: Dashboard frontend
cd agilegpt/frontend
npm run dev
```

Then open `http://localhost:3000` to:
1. Upload a nonprofit's annual report PDF
2. Review and edit the extracted profile in a chat interface
3. Confirm and kick off the automated SCRUM pipeline
4. Watch sprint progress in real time with JIRA ticket updates

## How the SCRUM Cycle Works

### Planning Phase
The PM agent receives the nonprofit's profile and produces a JSON sprint plan containing:
- **5 sprints** (can grow to 7 max if the PM inserts sprints during review)
- **3 tasks per sprint**: 1 backend, 1 frontend, 1 QA/integration
- **Shared contract**: Every API endpoint with path, method, request schema, response schema, and success status code
- **Handoff contract**: Maps each endpoint to the backend file, frontend component, and test that owns it

### Sprint Execution
For each sprint, the orchestrator:
1. **Starts the JIRA sprint** and moves tickets to "In Progress"
2. **Runs the backend agent** — receives the task + existing `.py` files + shared contract, returns new/updated files and install commands
3. **Runs the frontend agent** — receives the task + existing `.html/.css/.js` files + shared contract, returns new/updated components
4. **Starts the Flask server** in the background
5. **Runs the QA agent** — receives the task + all workspace files, returns test files and `pytest` commands that run against the live server
6. **Stops the server**, closes the JIRA sprint, records pass/fail per task

### PM Review (between sprints)
After each sprint (except the last), the PM agent receives:
- Task results (DONE/FAILED for each)
- What each agent has built so far (file lists + work logs)
- The full remaining plan

The PM can then:
- **Keep the plan unchanged** if everything passed
- **Modify future sprint tasks** to fix issues (e.g., correct an endpoint path, add missing preservation instructions)
- **Insert a new sprint** if critical issues can't be fixed by modifying existing tasks (up to 7 sprints max)

## LLM Model Routing

| Component | Provider | Model | Why |
|-----------|----------|-------|-----|
| PM Agent | OpenAI | o3 | Best reasoning for complex planning and review decisions |
| Backend Agent | Azure OpenAI | GPT-4.1 | Strong code generation for Python/Flask |
| Frontend Agent | Azure OpenAI | GPT-4.1 | Strong code generation for React/JS/CSS |
| QA Agent | Azure OpenAI | GPT-4.1 | Accurate test generation with correct endpoint references |
| Manager Chat | Azure OpenAI | GPT-4.1-mini | Lightweight conversational model for profile review |
| RAG Extraction | Azure OpenAI | GPT-4.1-mini | Structured data extraction from PDF text |

## API Endpoints (AgileGPT Server)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/session/new` | Upload PDF, extract profile, start review session |
| `POST` | `/session/chat` | Send a message in the review conversation |
| `GET` | `/session/:id/profile` | Get the current extracted profile |
| `PATCH` | `/session/:id/profile` | Update profile fields |
| `POST` | `/session/:id/confirm` | Confirm profile and start the SCRUM pipeline |
| `GET` | `/pipeline/status/:id` | Poll pipeline progress (sprint status, current sprint) |
| `GET` | `/jira/sprint-issues` | Fetch issues in the currently active JIRA sprint |
| `GET` | `/session/:id/transcript` | Get the full review conversation transcript |
| `DELETE` | `/session/:id` | Delete a review session |

## Built With

- **Python 3.12** + Flask + Flask-CORS
- **OpenAI o3** (PM agent planning and review)
- **Azure OpenAI GPT-4.1** (code generation agents)
- **Azure OpenAI GPT-4.1-mini** (chat and extraction)
- **PyMuPDF** (PDF text extraction)
- **LangChain** (manager agent conversation management)
- **Pydantic** (state models and validation)
- **JIRA Cloud REST API** (sprint and issue tracking)
- **Next.js** + TypeScript (dashboard frontend)
- **React via CDN** (generated project frontend — no build step needed)