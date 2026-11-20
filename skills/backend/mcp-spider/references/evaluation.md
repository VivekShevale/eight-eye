# MCP Evaluation

The rules from `rag-spider/references/evaluation.md` apply: only when the user explicitly asks, same `eval/` layout (`golden_dataset/`, `scripts/`, gitignored `reports/`), `eval_client.py` for login and reports, modules run with `python -m eval.scripts.<name>`, judging by the assistant's own model, the project's LLM only when the model itself is measured.

## Priority list

| Priority | Evaluation | Measures | LLM called? |
|---|---|---|---|
| P0 | Tool selection | For each golden prompt, `tool_used` equals `expected_tool` (missing `tool_used` = fail) | Project LLM (it's the model's choice being tested) |
| P0 | Fallback resilience | MCP failure → fallback path works; patched module-level clients with `unittest.mock.AsyncMock` | No (mocked) |
| P0 | Multi-tenant isolation | Another user's files/chats/documents → 404; no token → 401 | No |
| P1 | File integrity | Generated files open (ZIP magic bytes for docx/xlsx/pptx, size ≥ 100 bytes, expected text present) | Project LLM (end to end) |
| P1 | Read tools | Read-only prompts call read tools and return the item's content | Project LLM |
| P1 | Persona / memory | Stored preferences change later answers; rolling summary kept | Project LLM, judged by the assistant |
| P2 | Latency | P50/P95 per scenario, split MCP vs fallback | Project LLM |
| P2 | Token usage | Provider-reported tokens from `usage_logs` by `conversation_id`, never estimated | Project LLM |
| P3 | Temperature stability | Same prompts at fixed temperature (set in `.env`, verified in the startup log) | Project LLM |
| P3 | Model comparison | Same golden set per provider/model, CSV + JSON | Project LLM (each model) |

Then `build_evaluation_summary.py` combines the latest reports into one JSON + Markdown file without calling any API.

## Golden prompt format

```json
{"id": "excel_01", "category": "excel", "prompt": "Create a quarterly expense tracker...", "expected_tool": "create_excel_sheet", "expected_file_type": "xlsx", "assertions": {"must_contain_text": ["Food", "Travel"], "must_have_formula": true}}
```

## Practical rules

- Reuse the login flow that already works (`EvalClient.login`); don't rewrite auth per script.
- An HTTP 200 that hides a provider failure (swallowed 429, empty answer) is a failure.
- Read generated documents from MongoDB/disk to check metadata (`method_used`, `fallback_used`) instead of assuming fields in the API response.
- Show progress (`flush=True`) and use short auth timeouts so a stuck run is visible.
- Don't run the server with `--reload` watching `eval/`.
- Generated Office files and `~$*` lock files from eval runs are never committed.
