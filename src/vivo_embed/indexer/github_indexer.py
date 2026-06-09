"""GitHub repo indexer — API-n keresztul, helyi klon nelkul"""
from __future__ import annotations
import logging
import os
import hashlib
import time
from typing import Iterator, Tuple
from pathlib import PurePosixPath
import httpx

log = logging.getLogger("vivo_embed.github")

INDEXABLE_EXTS = {
    ".py", ".ts", ".js", ".jsx", ".tsx",
    ".md", ".rst", ".txt",
    ".yaml", ".yml", ".json", ".toml",
    ".ps1", ".sh", ".bat",
    ".go", ".rs", ".cs", ".java",
}
MAX_FILE_SIZE = 200_000

class GitHubIndexer:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        headers = {"User-Agent": "vivo-embed/1.0", "Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.client = httpx.Client(headers=headers, timeout=30)

    def list_repos(self, username: str) -> list[dict]:
        repos, page = [], 1
        while True:
            r = self.client.get(
                f"https://api.github.com/users/{username}/repos",
                params={"per_page": 100, "page": page, "sort": "updated"},
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            repos.extend(batch)
            page += 1
        return repos

    def iter_repo_files(self, owner: str, repo: str, branch: str = "HEAD") -> Iterator[Tuple[str, str, str]]:
        try:
            r = self.client.get(
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}",
                params={"recursive": "1"},
            )
            r.raise_for_status()
        except Exception as e:
            log.warning(f"Tree fetch hiba {owner}/{repo}: {e}")
            return
        for item in r.json().get("tree", []):
            if item.get("type") != "blob":
                continue
            path = item["path"]
            ext = PurePosixPath(path).suffix.lower()
            if ext not in INDEXABLE_EXTS:
                continue
            size = item.get("size", 0)
            if size > MAX_FILE_SIZE or size < 50:
                continue
            time.sleep(0.05)
            try:
                br = self.client.get(item.get("url", ""))
                br.raise_for_status()
                blob = br.json()
                if blob.get("encoding") == "base64":
                    import base64
                    content = base64.b64decode(blob["content"]).decode("utf-8", errors="replace")
                else:
                    content = blob.get("content", "")
            except Exception as e:
                log.debug(f"File fetch hiba {path}: {e}")
                continue
            if not content or len(content.strip()) < 50:
                continue
            col = "notes" if ext in (".md", ".rst", ".txt") else \
                  "system" if ext in (".yaml", ".yml", ".json", ".toml") else "code"
            yield path, content, col

    def index_user(self, username: str, store, embedder, chunker_fn, skip_repos=None) -> dict:
        skip = set(skip_repos or [])
        repos = self.list_repos(username)
        stats = {"repos": 0, "files": 0, "chunks": 0, "errors": 0}
        for repo in repos:
            repo_name = repo["name"]
            if repo_name in skip:
                continue
            branch = repo.get("default_branch", "HEAD")
            log.info(f"GitHub: {username}/{repo_name}")
            for path, content, col in self.iter_repo_files(username, repo_name, branch):
                try:
                    from .chunker import chunk_text
                    chunks = chunk_text(content)
                    if not chunks:
                        continue
                    embeddings = embedder.embed_documents(chunks)
                    virtual_path = f"github://{username}/{repo_name}/{path}"
                    base_id = hashlib.md5(virtual_path.encode()).hexdigest()
                    ids  = [f"{base_id}_{i}" for i in range(len(chunks))]
                    meta = [{"path": virtual_path, "type": PurePosixPath(path).suffix,
                             "chunk": i, "repo": repo_name, "source": "github"}
                            for i in range(len(chunks))]
                    store.upsert(col, ids, embeddings, chunks, meta)
                    stats["files"] += 1
                    stats["chunks"] += len(chunks)
                except Exception as e:
                    log.error(f"Hiba {path}: {e}")
                    stats["errors"] += 1
            stats["repos"] += 1
        return stats
