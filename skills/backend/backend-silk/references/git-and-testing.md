# Git and Testing

## What never gets committed

`.env`, keys and credential files (`credentials.json`, `token.json`, `*_private.pem`), uploads, vector data (`chroma_data/`), local databases (`db.sqlite3`), logs, virtual environments (`venv/`, `node_modules/`), generated evaluation reports and Office lock files (`~$*`). Check `git status` before staging and stage explicit paths.

Migrations are committed together with the model change that produced them.

## Commit messages

Conventional Commits, short and accurate about what the commit contains:

```text
feat: add expense filtering by date range and category
fix: return 424 when MongoDB is unavailable
refactor: move expense filters into ExpenseHelper
chore: add .env.example with logging settings
test: add ownership isolation tests for documents
docs: add setup steps to README
perf: run embedding and bcrypt in worker threads
```

One concern per commit; separate commits per repository when a change spans two repos.

## PR description

```markdown
## Summary
One or two sentences.

## Changes
- one bullet per meaningful change, covering every commit in the PR

## Testing
- what was run and the result
```

## Tests

- pytest (Python) or `node:test` (Node) for critical paths: auth, ownership/isolation between users, validation, error responses, dependency failures (mocked), kept in `tests/`.
- External dependencies (LLMs, other repos, paid APIs) are mocked; tests never call them.
- Quick checks (`python -m compileall app`, importing the app, one request) use temporary scripts that aren't committed.
- Evaluations (golden datasets, eval scripts, reports) are separate from tests and exist only when requested; see `rag-spider` / `mcp-spider`.

## Debugging approach

1. Read the full error and the code it points to.
2. Find the root cause before changing code.
3. Apply the smallest fix that solves it.
4. Check whether the same mistake exists elsewhere (other routes, the other repo).
5. If schema and database disagree (e.g. "column does not exist"), check the applied migrations before changing code.

## README

Short and practical: what the project does, requirements, setup (venv or npm install, `.env` from `.env.example`, generating secrets, migrations), how to run, main endpoints. Kept in sync when setup steps change.
