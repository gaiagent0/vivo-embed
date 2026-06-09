"""FastAPI REST API — /search /index /index/github /status /reindex"""
from __future__ import annotations
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .. config import get
from .. store.chroma_store import ChromaStore
from .. indexer.crawler import iter_files
from .. indexer.extractors import extract_text, get_collection
from .. indexer.chunker import chunk_text

log = logging.getLogger("vivo_embed.api")
app = FastAPI(title="vivo-embed", version="1.0")
cfg = get()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_embedder = None
_store: ChromaStore | None = None
_indexing = False

def get_embedder():
    global _embedder
    if _embedder is None:
        embedder_type = get().get("embedder", "ollama")
        if embedder_type == "ollama":
            from .. engines.ollama_engine import OllamaEmbedder
            _embedder = OllamaEmbedder()
        else:
            from .. engines.google_engine import GoogleEmbedder
            _embedder = GoogleEmbedder()
    return _embedder

def get_store():
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

class GitHubIndexRequest(BaseModel):
    username: str = "gaiagent0"
    skip_repos: List[str] = []

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
        return [SearchResult(content=raw["documents"][0][i],
            path=raw["metadatas"][0][i].get("path", ""), collection=req.collection,
            score=1.0 - raw["distances"][0][i],
            file_type=raw["metadatas"][0][i].get("type", ""))
            for i in range(len(raw["documents"][0]))]
    raw = store.search_all(emb, n_results=req.top_k)
    return [SearchResult(content=r["content"], path=r["metadata"].get("path", ""),
        collection=r["collection"], score=1.0 - r["distance"],
        file_type=r["metadata"].get("type", "")) for r in raw]

@app.post("/index")
def index_file(req: IndexRequest, background_tasks: BackgroundTasks):
    path = Path(req.path)
    if not path.exists():
        raise HTTPException(404, f"Nem talalhato: {req.path}")
    background_tasks.add_task(_index_single, path)
    return {"status": "queued", "path": str(path)}

@app.post("/index/github")
def index_github(req: GitHubIndexRequest, background_tasks: BackgroundTasks):
    global _indexing
    if _indexing:
        return {"status": "already_running"}
    background_tasks.add_task(_index_github_user, req.username, req.skip_repos)
    return {"status": "started", "username": req.username}

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
    stats = {"indexed": 0, "errors": 0}
    try:
        store = get_store()
        embedder = get_embedder()
        for fpath, col, chunks in iter_files(incremental=incremental):
            try:
                embeddings = embedder.embed_documents(chunks)
                if not embeddings or all(v == 0.0 for v in embeddings[0][:5]):
                    continue
                base_id = hashlib.md5(str(fpath).encode()).hexdigest()
                ids  = [f"{base_id}_{i}" for i in range(len(chunks))]
                meta = [{"path": str(fpath), "type": fpath.suffix, "chunk": i}
                        for i in range(len(chunks))]
                store.upsert(col, ids, embeddings, chunks, meta)
                stats["indexed"] += 1
                if stats["indexed"] % 100 == 0:
                    log.info(f"Haladás: {stats}")
            except Exception as e:
                log.error(f"Hiba {fpath.name}: {e}")
                stats["errors"] += 1
    except Exception as e:
        log.error(f"Reindex fatal: {e}")
    finally:
        _indexing = False
        log.info(f"Reindex kesz: {stats}")

def _index_github_user(username: str, skip_repos: list):
    global _indexing
    _indexing = True
    try:
        from .. indexer.github_indexer import GitHubIndexer
        token = os.environ.get("GITHUB_TOKEN", "")
        indexer = GitHubIndexer(token=token)
        stats = indexer.index_user(username=username, store=get_store(),
            embedder=get_embedder(), chunker_fn=chunk_text, skip_repos=skip_repos)
        log.info(f"GitHub kesz: {stats}")
    except Exception as e:
        log.error(f"GitHub hiba: {e}")
    finally:
        _indexing = False
