# Evaluation

## Contents
1. When
2. Layout and storage
3. Who generates answers and judgments
4. Order of RAG evaluations
5. Golden data
6. Script rules
7. Judging answers
8. Git

## 1. When

- **Only when the user explicitly asks** for an evaluation (or a specific one: "add a retrieval eval", "compare the models"). Never add an `eval/` folder, golden datasets or eval scripts on your own initiative, and never run a full evaluation unasked.
- Quick checks are always fine and are not evaluations: import the app, upload one PDF, ask three questions, compare one setting. Use a temporary script and delete it afterwards; never commit it.
- Evaluations are separate from `tests/` (pytest checks code correctness; evals measure quality).

## 2. Layout and storage

```text
eval/
├── __init__.py
├── golden_dataset/          # committed: hand-checked cases (JSON)
│   └── retrieval_golden.json
├── scripts/                 # committed: one script per evaluation
│   ├── __init__.py
│   ├── eval_client.py       # shared login + report saving
│   ├── run_retrieval_eval.py
│   └── build_evaluation_summary.py   # only once several reports exist
└── reports/                 # gitignored (keep .gitkeep): <name>_YYYYMMDD_HHMMSS.json (+ .csv when useful)
```

- Every report records the configuration it ran with: model, temperature, top_k, chunk size/overlap, embedding model, max distance.
- `build_evaluation_summary.py` reads the latest reports and writes one JSON + Markdown summary; it calls no API.

## 3. Who generates answers and judgments

- **Judging, grading and drafting** (faithfulness, correctness, citation quality, drafting candidate test questions for the user to check) are done by the assistant writing the evaluation, using its own model, by reading the report outputs. The project's LLM is not used as a judge, so the user's provider quota isn't spent on grading.
- **Evaluations of retrieval and prompt construction** don't call the project's LLM at all (retrieval metrics are computed by the script).
- **The project's LLM is called only when the evaluation measures the model itself**: model comparison, temperature stability, end-to-end latency and token usage.
- Ground truth is never LLM-generated: expected answers and pages are checked by the user against the document.

## 4. Order of RAG evaluations

1. Manual end-to-end check (upload, ask, sources, invalid files, questions with no answer).
2. Retrieval: hit rate, MRR, precision@k (`run_retrieval_eval.py`).
3. Citations: the cited file/page actually contains the answer.
4. Refusal: questions not covered by the documents get "not in the documents", not invented answers.
5. Faithfulness: every claim in the answer is supported by the retrieved context.
6. Latency breakdown (retrieval vs LLM, P50/P95) and token usage (from `usage_logs`, never estimated).
7. Temperature stability, then model comparison.
8. Re-ranking or hybrid search only if retrieval numbers justify it; tune `RETRIEVAL_MAX_DISTANCE` from the distances in retrieval reports.

## 5. Golden data

- Primary: a controlled fictional PDF with known facts on known pages (e.g. `rag_evaluation_handbook.pdf`), so answers are unambiguous.
- Secondary: one real public PDF.
- Edge cases: blank, scanned (no text layer, expected to fail extraction), corrupted, encrypted PDFs.
- Case fields: `id`, `question`, `expected_document`, `expected_pages`, `expected_answer`, `category` (`fact`, `multi_page`, `follow_up`, `refusal`).

## 6. Script rules

- Run from the project root as modules: `python -m eval.scripts.run_retrieval_eval` (needs `eval/__init__.py` and `eval/scripts/__init__.py`); no `sys.path` edits.
- Settings from env: `EVAL_BASE_URL`, `EVAL_EMAIL`, `EVAL_PASSWORD` (HTTP evals via `EvalClient`), `EVAL_USER_ID` (direct retrieval eval).
- `argparse` options such as `--category`, `--limit`, `--top-k`, `--runs`; print progress with `flush=True`; short timeouts on auth; non-zero exit code when a threshold given on the command line isn't met.
- An HTTP 200 whose body shows a failure (empty answer, missing `tool_used`, swallowed provider error) counts as a failure.
- Don't run the API with `uvicorn --reload` watching `eval/` while evaluating (every report write restarts the server).
- Mock external services (`unittest.mock`) when the evaluation targets fallback or error behaviour rather than the live service.

## 7. Judging answers

For faithfulness, refusal and citation evaluations, the script saves for each case: question, retrieved chunks (file, page, text), the answer, sources, latency and tokens. The assistant then reads that report and records per case `{"id", "verdict": "pass" | "fail", "reason"}` into `<report>_judged.json`, and reports the pass rate with the failing cases. Grading criteria are stated in the report (e.g. "fail if any claim is not supported by the retrieved text").

## 8. Git

Commit scripts and golden data after they run successfully (`test: add retrieval evaluation`). Never commit `eval/reports/*`, downloaded or generated files, or Office lock files (`~$*`).
