"""
JSON Cache Layer for Extraction Results

Avoids re-scanning the 100MB+ College Scorecard file every time the
analysis runs. After a successful extraction, stores just the extracted
field dict (a few KB) to JSON. Next run reads from cache if fresh.

Demonstrates production data-engineering patterns: read-through cache,
TTL invalidation, atomic write.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Optional, Any


class ExtractionCache:
    """
    Simple JSON-backed cache for extracted institution rows.

    Storage layout:
        {
            "metadata": {
                "last_refresh": "2026-08-28T17:32:00Z",
                "source_file": "MERGED2019_20_PP.csv",
                "source_sha": "<optional checksum>"
            },
            "schools": {
                "SAMPLE000001": { "INSTNM": "...", "DEBT_MDN": "..." },
                ...
            }
        }
    """

    def __init__(self, cache_path: str, ttl_days: int = 90, force_refresh: bool = False):
        self.cache_path = cache_path
        self.ttl_days = ttl_days
        self.force_refresh = force_refresh
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.cache_path):
            return {"metadata": {}, "schools": {}}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"metadata": {}, "schools": {}}

    def _is_fresh(self) -> bool:
        if self.force_refresh:
            return False
        last = self._data.get("metadata", {}).get("last_refresh")
        if not last:
            return False
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        except ValueError:
            return False
        return datetime.now(last_dt.tzinfo) - last_dt < timedelta(days=self.ttl_days)

    def is_cached(self, match_value: str) -> bool:
        """Returns True if this institution is in cache AND the cache is fresh."""
        if not self._is_fresh():
            return False
        return match_value in self._data.get("schools", {})

    def get(self, match_value: str) -> Optional[Dict[str, Any]]:
        if not self.is_cached(match_value):
            return None
        return self._data["schools"].get(match_value)

    def set(self, match_value: str, row: Dict[str, Any]) -> None:
        if "metadata" not in self._data:
            self._data["metadata"] = {}
        if "schools" not in self._data:
            self._data["schools"] = {}
        self._data["schools"][match_value] = row
        self._data["metadata"]["last_refresh"] = datetime.utcnow().isoformat() + "Z"

    def save(self) -> None:
        """Atomic write — write to temp file, then rename. Prevents corruption
        if the process dies mid-write."""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        dir_name = os.path.dirname(self.cache_path) or "."
        with tempfile.NamedTemporaryFile(
            "w", dir=dir_name, delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(self._data, tmp, indent=2, ensure_ascii=False)
            tmp.flush()
            tmp_name = tmp.name
        os.replace(tmp_name, self.cache_path)

    def clear(self) -> None:
        self._data = {"metadata": {}, "schools": {}}