# Repository Guidelines

## Project Structure & Module Organization

PitWall Agent is a Python 3.12 FastAPI backend with a Next.js frontend. Backend code lives in `app/`: API routers in `app/api`, agent orchestration in `app/agents`, domain services in `app/services`, data access in `app/repositories`, schemas in `app/schemas`, and database setup in `app/db`. Tests mirror these areas under `tests/`. Operational scripts are in `scripts/`, documentation is in `docs/`, and regulation assets are under `data/regulations`. Frontend code is in `frontend/`, with routes in `frontend/app`, components in `frontend/components`, and API helpers in `frontend/services`.

## Build, Test, and Development Commands

- `uv sync` installs backend dependencies from `pyproject.toml` and `uv.lock`.
- `docker compose up -d` starts local Postgres with pgvector and Redis.
- `uv run uvicorn app.main:app --reload` runs the backend API locally.
- `uv run pytest` runs the backend test suite.
- `uv run ruff check .` checks Python lint rules.
- `uv run pyright` runs Python type checking.
- `cd frontend && npm install` installs frontend dependencies.
- `cd frontend && npm run dev` starts the Next.js dev server.
- `cd frontend && npm run build` validates the production frontend build.

## Coding Style & Naming Conventions

Use 4-space indentation and type annotations for Python. Keep modules snake_case, classes PascalCase, and functions/tests snake_case. Prefer Pydantic schemas for request/response data, and keep API handlers thin by delegating logic to services. Use Ruff for lint consistency and Pyright for type checks. Frontend files use TypeScript; components should be typed and named with kebab-case filenames such as `message-bubble.tsx`.

## Testing Guidelines

Pytest is the backend test framework. Add tests near the relevant layer, following existing names like `test_chat_api.py`, `test_agent_service.py`, or `test_rule_repository.py`. Prefer focused unit tests for services and repositories, plus API tests for request/response behavior. Run `uv run pytest` before submitting changes; use targeted runs such as `uv run pytest tests/services/test_chat_service.py` while developing.

## Commit & Pull Request Guidelines

Recent commits use short, imperative Chinese summaries. Keep messages concise and focused on the user-visible or architectural change. Pull requests should include a clear description, linked issue when available, test results, and screenshots for frontend UI changes. Note any required `.env`, database, Redis, or data-ingestion setup.

## Security & Configuration Tips

Do not commit secrets. Keep local configuration in `.env`, and document new required variables in the PR. Treat `data/regulations/raw` as source assets and avoid rewriting large generated files unless the change requires it.
