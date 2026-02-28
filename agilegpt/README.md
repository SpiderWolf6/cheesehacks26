# AgileGPT Backend Scaffold

AgileGPT is a minimal Flask backend scaffold for an AI-orchestrated Scrum-like development system.

This MVP focuses on clean structure, readability, and educational value.

## What this scaffold currently does

- Provides a Flask API with:
  - `GET /health`
  - `POST /chat` (temporary echo behavior)
- Loads and validates required environment variables.
- Defines simple service wrappers for:
  - Azure OpenAI chat completions
  - JIRA REST API calls (partially stubbed)
- Defines PM + Dev agent class scaffolding.
- Defines a basic in-memory orchestrator state and engine.

## Folder structure

```
agilegpt/
├── app.py
├── config.py
├── .env.example
├── README.md
├── services/
│   ├── llm_service.py
│   └── jira_service.py
├── agents/
│   ├── base_agent.py
│   ├── pm_agent.py
│   ├── frontend_agent.py
│   ├── backend_agent.py
│   └── qa_agent.py
└── orchestrator/
    ├── state.py
    └── engine.py
```

## Setup

1. Use Python 3.11+.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   pip install flask requests python-dotenv pydantic
   ```

4. Copy `.env.example` to `.env` and fill all required values.

## Run

From the `agilegpt` folder:

```bash
python app.py
```

Then open:

- `http://localhost:5000/health`

## Important notes

- This is scaffold-only: no database, no persistent state yet.
- Project state is temporary in-memory data.
- JIRA methods include TODOs for board/transition mapping.
- Docker sandbox creation is stubbed in orchestrator TODOs.
- Structured JSON output enforcement for agents is planned for later.
- Sprint iteration loops and execution policy will be added in future iterations.
