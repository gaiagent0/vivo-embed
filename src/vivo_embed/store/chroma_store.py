"""ChromaDB persistent store wrapper"""
from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from .. config import get

log = logging.getLogger("vivo_embed.store")
COLLECTIONS = ["docs", "code", "notes", "system", "web"]
CHROMA_MAX_BATCH = 5000

class ChromaStore:
    def __init__(self):
        cfg = get()["chroma"]
        self.client = chromadb.PersistentClient(
            path=cfg["persist_path"],
            settings=Settings(anonymized_telemetry=False),
        )
        self._cols: dict = {}
        for name in COLLECTIONS:
            self._cols[name] = self.client.get_or_create_collection(
                name=name, metadata={"hnsw:space": "cosine"},
            )
        log.info(f"ChromaDB betoltve: {cfg['persist_path']}")

    def col(self, name: str):
        return self._cols.get(name, self._cols["docs"])

    def upsert(self, collection: str, ids: List[str],
               embeddings: List[List[float]], documents: List[str],
               metadatas: List[Dict]) -> None:
        col = self.col(collection)
        for start in range(0, len(ids), CHROMA_MAX_BATCH):
            end = start + CHROMA_MAX_BATCH
            col.upsert(
                ids=ids[start:end], embeddings=embeddings[start:end],
                documents=documents[start:end], metadatas=metadatas[start:end],
            )

    def search(self, collection: str, query_embedding: List[float],
               n_results: int = 10, where: Optional[Dict] = None) -> Dict[str, Any]:
        kwargs = dict(query_embeddings=[query_embedding], n_results=n_results,
                      include=["documents", "metadatas", "distances"])
        if where:
            kwargs["where"] = where
        return self.col(collection).query(**kwargs)

    def search_all(self, query_embedding: List[float], n_results: int = 5) -> List[Dict]:
        combined = []
        per_col = max(2, n_results // len(COLLECTIONS))
        for name in COLLECTIONS:
            try:
                r = self.search(name, query_embedding, n_results=per_col)
                for i, doc in enumerate(r["documents"][0]):
                    combined.append({"content": doc, "metadata": r["metadatas"][0][i],
                                     "distance": r["distances"][0][i], "collection": name})
            except Exception:
                pass
        combined.sort(key=lambda x: x["distance"])
        return combined[:n_results]

    def delete_by_path(self, collection: str, path: str) -> None:
        try:
            self.col(collection).delete(where={"path": path})
        except Exception:
            pass

    def stats(self) -> Dict[str, int]:
        return {name: self._cols[name].count() for name in COLLECTIONS}
