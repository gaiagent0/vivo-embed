"""Ollama Embedding engine — lokális, nincs quota, nincs rate limit
Modél: bge-m3 (100+ nyelv, magyar, 1024 dim) VAGY nomic-embed-text (768 dim, gyors)
API: http://localhost:11434/api/embed
"""
from __future__ import annotations
import logging
from typing import List
import httpx
from .. config import get

log = logging.getLogger("vivo_embed.ollama")

class OllamaEmbedder:
    def __init__(self):
        cfg = get().get("ollama", {})
        self.base_url   = cfg.get("base_url", "http://localhost:11434")
        self.model      = cfg.get("model", "bge-m3")
        self.batch_size = cfg.get("batch_size", 50)
        self.dims       = cfg.get("dimensions", 1024)
        self._client    = httpx.Client(timeout=120)
        log.info(f"OllamaEmbedder: {self.model} @ {self.base_url} ({self.dims} dim)")

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        resp = self._client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": texts},
        )
        resp.raise_for_status()
        return resp.json().get("embeddings", [])

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            try:
                embs = self._embed_batch(batch)
                results.extend(embs)
                log.debug(f"Embedded {len(batch)} chunk(s)")
            except Exception as e:
                log.error(f"Ollama embedding hiba: {e}")
                results.extend([[0.0] * self.dims] * len(batch))
        return results

    def embed_query(self, text: str) -> List[float]:
        try:
            embs = self._embed_batch([text])
            return embs[0] if embs else [0.0] * self.dims
        except Exception as e:
            log.error(f"Query embedding hiba: {e}")
            return [0.0] * self.dims
