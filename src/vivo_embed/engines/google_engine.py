"""Google Gemini Embedding engine — direkt httpx REST, SDK-fuggetlenul
Model: gemini-embedding-001 (3072 dim, multilingual, v1beta)
"""
from __future__ import annotations
import time
import logging
from typing import List
import httpx
from .. config import get

log = logging.getLogger("vivo_embed.google")

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

class GoogleEmbedder:
    def __init__(self):
        cfg            = get()["google"]
        self.api_key   = cfg["api_key"]
        self.model     = cfg["model"]
        self.dims      = cfg.get("dimensions", 3072)
        self.batch_size= cfg.get("batch_size", 20)
        self._last     = 0.0
        self._client   = httpx.Client(timeout=30)

    def _throttle(self):
        elapsed = time.monotonic() - self._last
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        self._last = time.monotonic()

    def _embed_batch(self, texts: List[str], task: str) -> List[List[float]]:
        self._throttle()
        requests_body = [
            {"model": f"models/{self.model}",
             "content": {"parts": [{"text": t}]},
             "taskType": task}
            for t in texts
        ]
        url = f"{BASE_URL}/{self.model}:batchEmbedContents?key={self.api_key}"
        resp = self._client.post(url, json={"requests": requests_body})
        resp.raise_for_status()
        return [e["values"] for e in resp.json().get("embeddings", [])]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            try:
                results.extend(self._embed_batch(batch, "RETRIEVAL_DOCUMENT"))
                log.debug(f"Embedded {len(batch)} chunk(s)")
            except Exception as e:
                log.error(f"Embedding hiba (batch {i}): {e}")
                results.extend([[0.0] * self.dims] * len(batch))
        return results

    def embed_query(self, text: str) -> List[float]:
        try:
            embs = self._embed_batch([text], "RETRIEVAL_QUERY")
            return embs[0] if embs else [0.0] * self.dims
        except Exception as e:
            log.error(f"Query embedding hiba: {e}")
            return [0.0] * self.dims
