"""FastAPI REST API — /search /index /status /reindex"""
from __future__ import annotations
import logging
import hashlib
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .. config import get
from .. engines.google_engine import GoogleEmbedder
from .. store.chroma_store import ChromaStore
from .. indexer.crawler import iter_files
from .. indexer.extractors import extract_text, get_collection
from .. indexer.chunker import chunk_text

log = logging.getLogger("vivo_embed.api")
app = FastAPI(title="vivo-embed", version="1.0", description="Magyar Embedding Indexer")
cfg = get()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_embedder: GoogleEmbedder | None = None
_store: ChromaStore | None = None
_indexing = False

def get_embedder() -> GoogleEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = GoogleEmbedder()
    return _embedder

def get_store() -> ChromaStore:
    global _store
    if _store is None:
        _store = ChromaStore()
    return _store

class SearchRequest(BaseModel):
    query: str
    collection: Optional[str] = None
    top_k: int = 10

class IndexRequest(BaseModel):
    path: str
    force: bool = False

class SearchResult(BaseModel):
    content: str
    path: str
    collection: str
    score: float
    file_type: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "ok", "service": "vivo-embed"}

@app.get("/status")
def status():
    store = get_store()
    return {"status": "ok", "indexing": _indexing,
            "collections": store.stats(), "total": sum(store.stats().values())}

@app.post("/search", response_model=List[SearchResult])
def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(400, "Ures keresesi kifejezes")
    emb = get_embedder().embed_query(req.query)
    store = get_store()
    if req.collection:
        raw = store.search(req.collection, emb, n_results=req.top_k)
        return [SearchResult(
            content=raw["documents"][0][i],
            path=raw["metadatas"][0][i].get("path", ""),
            collection=req.collection,
            score=1.0 - raw["distances"][0][i],
            file_type=raw["metadatas"][0][i].get("type", ""),
        ) for i in range(len(raw["documents"][0]))]
    else:
        raw = store.search_all(emb, n_results=req.top_k)
        return [SearchResult(
            content=r["content"], path=r["metadata"].get("path", ""),
            collection=r["collection"], score=1.0 - r["distance"],
            file_type=r["metadata"].get("type", ""),
        ) for r in raw]

@app.post("/index")
def index_file(req: IndexRequest, background_tasks: BackgroundTasks):
    path = Path(req.path)
    if not path.exists():
        raise HTTPException(404, f"Nem talalhato: {req.path}")
    background_tasks.add_task(_index_single, path)
    return {"status": "queued", "path": str(path)}

@app.post("/reindex")
def reindex(background_tasks: BackgroundTasks, full: bool = False):
    global _indexing
    if _indexing:
        return {"status": "already_running"}
    background_tasks.add_task(_reindex_all, incremental=not full)
    return {"status": "started", "mode": "full" if full else "incremental"}

def _index_single(path: Path):
    text = extract_text(path)
    if not text:
        return
    chunks = chunk_text(text)
    if not chunks:
        return
    col = get_collection(path)
    embeddings = get_embedder().embed_documents(chunks)
    store = get_store()
    base_id = hashlib.md5(str(path).encode()).hexdigest()
    ids  = [f"{base_id}_{i}" for i in range(len(chunks))]
    meta = [{"path": str(path), "type": path.suffix, "chunk": i} for i in range(len(chunks))]
    store.upsert(col, ids, embeddings, chunks, meta)
    log.info(f"Indexelve: {path} ({len(chunks)} chunk)")

def _reindex_all(incremental: bool = True):
    global _indexing
    _indexing = True
    try:
        store    = get_store()
        embedder = get_embedder()
        for fpath, col, chunks in iter_files(incremental=incremental):
            embeddings = embedder.embed_documents(chunks)
            base_id    = hashlib.md5(str(fpath).encode()).hexdigest()
            ids  = [f"{base_id}_{i}" for i in range(len(chunks))]
            meta = [{"path": str(fpath), "type": fpath.suffix, "chunk": i} for i in range(len(chunks))]
            store.upsert(col, ids, embeddings, chunks, meta)
    except Exception as e:
        log.error(f"Reindex hiba: {e}")
    finally:
        _indexing = False
        log.info("Reindex kesz")
