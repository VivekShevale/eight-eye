import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = PROJECT_ROOT / "eval" / "reports"


class EvalClient:
    """Login and report saving shared by every eval script, instead of copying them into each one.

    Settings: EVAL_BASE_URL (default http://localhost:8000), EVAL_EMAIL, EVAL_PASSWORD.
    """

    def __init__(self, timeout: float = 120.0) -> None:
        self.client = httpx.Client(base_url=os.getenv("EVAL_BASE_URL", "http://localhost:8000"), timeout=timeout)

    def login(self) -> None:
        """Log in as the eval user, registering it first if it doesn't exist yet."""
        credentials = {"email": os.getenv("EVAL_EMAIL", "eval_user@example.com"), "password": os.getenv("EVAL_PASSWORD", "EvalPass123!")}
        print("Authenticating eval user...", flush=True)
        response = self.client.post("/api/v1/auth/login", json=credentials, timeout=20.0)
        if response.status_code == 401:
            self.client.post("/api/v1/auth/register", json=credentials, timeout=20.0).raise_for_status()
            response = self.client.post("/api/v1/auth/login", json=credentials, timeout=20.0)
        response.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        print("Authenticated.", flush=True)

    def post(self, path: str, payload: dict) -> httpx.Response:
        """POST to the API with the eval user's token."""
        return self.client.post(path, json=payload)

    @staticmethod
    def save_report(name: str, config: dict, summary: dict, results: list[dict]) -> Path:
        """Write eval/reports/<name>_YYYYMMDD_HHMMSS.json with the config used, the summary and every case."""
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"{name}_{timestamp}.json"
        report = {"name": name, "created_at": timestamp, "config": config, "summary": summary, "results": results}
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"Report saved: {report_path}", flush=True)
        return report_path
