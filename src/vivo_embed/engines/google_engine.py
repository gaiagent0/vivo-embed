"""Google Gemini Embedding engine — per-key throttle, soha nem hit 429
10 RPM limit = 1 call / 6s per key. Fallback ha Ollama nem elerheto.
"""
from __future__ import annotations
import os
import time
import logging
from typing import List
import httpx
from .. config import get

log = logging.getLogger("vivo_embed.google")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
KEY_INTERVAL = 6.5

class GoogleEmbedder:
    def __init__(self):
        cfg = get()["google"]
        keys = [cfg["api_key"]]
        for i in (2, 3, 4):
            k = os.environ.get(f"GOOGLE_API_KEY_{i}", "").strip()
            if k and k not in keys:
                keys.append(k)
        self.keys      = keys
        self.key_times = [0.0] * len(keys)
        self.model     = cfg["model"]
        self.dims      = cfg.get("dimensions", 3072)
        self.batch_size= cfg.get("batch_size", 20)
        self._client   = httpx.Client(timeout=30)
        log.info(f"GoogleEmbedder: {len(self.keys)} key, {KEY_INTERVAL}s/key throttle")

    def _pick_key(self) -> tuple[int, float]:
        now = time.monotonic()
        best_idx, best_ready = 0, float('inf')
        for i, last in enumerate(self.key_times):
            ready_at = last + KEY_INTERVAL
            if ready_at <= now:
                return i, 0.0
            if ready_at < best_ready:
                best_ready = ready_at
                best_idx = i
        return best_idx, best_ready - now

    def _embed_batch(self, texts: List[str], task: str) -> List[List[float]]:
        requests_body = [
            {"model": f"models/{self.model}",
             "content": {"parts": [{"text": t}]},
             "taskType": task}
            for t in texts
        ]
        for attempt in range(4):
            idx, wait = self._pick_key()
            if wait > 0:
                log.debug(f"Varakozas {wait:.1f}s (key #{idx+1})")
                time.sleep(wait)
            self.key_times[idx] = time.monotonic()
            url = f"{BASE_URL}/{self.model}:batchEmbedContents?key={self.keys[idx]}"
            try:
                resp = self._client.post(url, json={"requests": requests_body})
                if resp.status_code == 429:
                    log.warning(f"429 key #{idx+1} \u2014 penalizalva 65s (attempt {attempt+1})")
                    self.key_times[idx] = time.monotonic() + 55
                    time.sleep(2)
                    continue
                resp.raise_for_status()
                return [e["values"] for e in resp.json().get("embeddings", [])]
            except httpx.TimeoutException:
                log.warning(f"Timeout key #{idx+1} (attempt {attempt+1})")
                time.sleep(3)
            except Exception as e:
                log.error(f"Embedding hiba key #{idx+1}: {e}")
                if attempt < 3:
                    time.sleep(5)
        log.error("Embedding vegleges sikertelenseg")
        return [[0.0] * self.dims] * len(texts)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        results = []
        for i in range(0, len(texts), self.batch_size):
            results.extend(self._embed_batch(texts[i:i+self.batch_size], "RETRIEVAL_DOCUMENT"))
        return results

    def embed_query(self, text: str) -> List[float]:
        embs = self._embed_batch([text], "RETRIEVAL_QUERY")
        return embs[0] if embs else [0.0] * self.dims
