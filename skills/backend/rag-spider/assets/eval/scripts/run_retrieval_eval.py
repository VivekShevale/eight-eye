"""Retrieval evaluation: hit rate, MRR and precision@k against a hand-checked golden dataset.

No LLM is called. Run from the project root after indexing the golden documents for EVAL_USER_ID:

    python -m eval.scripts.run_retrieval_eval
    python -m eval.scripts.run_retrieval_eval --top-k 3 --limit 10 --min-hit-rate 0.8
"""

import argparse
import json
import os
import sys
from pathlib import Path

from app.config import settings
from app.services.retrieval_service import RetrievalService
from eval.scripts.eval_client import PROJECT_ROOT, EvalClient

GOLDEN_FILE = PROJECT_ROOT / "eval" / "golden_dataset" / "retrieval_golden.json"


class RetrievalEvaluation:
    """Score retrieval for every golden question."""

    def __init__(self, top_k: int, limit: int | None, min_hit_rate: float | None) -> None:
        self.top_k = top_k
        self.limit = limit
        self.min_hit_rate = min_hit_rate
        self.user_id = os.getenv("EVAL_USER_ID", "")

    @staticmethod
    def parse_args() -> argparse.Namespace:
        """Command-line options."""
        parser = argparse.ArgumentParser(description="Evaluate retrieval against the golden dataset.")
        parser.add_argument("--top-k", type=int, default=settings.retrieval_top_k)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--min-hit-rate", type=float, default=None, help="exit with code 1 below this hit rate")
        return parser.parse_args()

    def score_case(self, case: dict) -> dict:
        """Retrieve for one question and compare with the expected document pages."""
        chunks = RetrievalService.search_chunks(self.user_id, case["question"], self.top_k)
        relevant = [
            chunk["metadata"]["filename"] == case["expected_document"] and chunk["metadata"]["page_number"] in case["expected_pages"]
            for chunk in chunks
        ]
        first_hit = next((rank for rank, is_relevant in enumerate(relevant, start=1) if is_relevant), None)
        return {
            "id": case["id"],
            "question": case["question"],
            "hit": first_hit is not None,
            "reciprocal_rank": 1 / first_hit if first_hit else 0.0,
            "precision_at_k": sum(relevant) / self.top_k,
            "retrieved": [{"filename": c["metadata"]["filename"], "page": c["metadata"]["page_number"], "distance": round(c["distance"], 4)} for c in chunks],
        }

    def run(self) -> int:
        """Score every case, save the report, return the process exit code."""
        if not self.user_id:
            print("Set EVAL_USER_ID to the user who owns the indexed golden documents.", flush=True)
            return 2
        # Refusal cases have no expected pages; they belong to the answer evaluation, not this one.
        cases = [case for case in json.loads(Path(GOLDEN_FILE).read_text(encoding="utf-8")) if case["expected_pages"]][: self.limit]
        results = []
        for index, case in enumerate(cases, start=1):
            results.append(self.score_case(case))
            print(f"[{index}/{len(cases)}] {case['id']} hit={results[-1]['hit']}", flush=True)
        count = len(results) or 1
        summary = {
            "cases": len(results),
            "hit_rate": round(sum(result["hit"] for result in results) / count, 4),
            "mrr": round(sum(result["reciprocal_rank"] for result in results) / count, 4),
            "mean_precision_at_k": round(sum(result["precision_at_k"] for result in results) / count, 4),
        }
        config = {"top_k": self.top_k, "embedding_model": settings.embedding_model_name, "chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap, "max_distance": settings.retrieval_max_distance}
        EvalClient.save_report("retrieval_eval", config, summary, results)
        print(json.dumps(summary, indent=2), flush=True)
        failed = self.min_hit_rate is not None and summary["hit_rate"] < self.min_hit_rate
        return 1 if failed else 0


if __name__ == "__main__":
    arguments = RetrievalEvaluation.parse_args()
    sys.exit(RetrievalEvaluation(arguments.top_k, arguments.limit, arguments.min_hit_rate).run())
