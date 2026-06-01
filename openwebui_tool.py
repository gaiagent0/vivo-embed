"""
title: vivo-embed Tudasbazis
author: gaiagent0
version: 1.0.0
description: Szemantikus kereses es indexeles a helyi vivo-embed rendszerben (port 7272)
"""
import json
import urllib.request
import urllib.error
import os

VIVO_EMBED_URL = "http://localhost:7272"

class Tools:
    def __init__(self):
        pass

    def search_knowledge(self, query: str, top_k: int = 8, collection: str = "") -> str:
        """
        Szemantikus kereses a helyi tudasbazisban (minden fajl a gepen).
        :param query: Keresesi kifejezes (magyar vagy angol)
        :param top_k: Talalatok szama (1-20)
        :param collection: Szures: docs / code / notes / system / web
        """
        payload = {"query": query, "top_k": top_k}
        if collection and collection in ("docs", "code", "notes", "system", "web"):
            payload["collection"] = collection
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{VIVO_EMBED_URL}/search", data=data,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                results = json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            return f"vivo-embed nem elerheto ({VIVO_EMBED_URL}): {e}"
        if not results:
            return "Nem talaltam relevant tartalmat."
        output = [f"**Talalatok** ({len(results)} db):\n"]
        for i, r in enumerate(results, 1):
            score = round(r.get("score", 0) * 100, 1)
            path  = r.get("path", "").replace("\\", "/").split("/")[-1]
            col   = r.get("collection", "")
            content = r.get("content", "").strip()[:300]
            output.append(f"**{i}.** `{path}` [{col}] {score}%\n> {content}...\n")
        return "\n".join(output)

    def index_folder(self, folder_path: str) -> str:
        """
        Egy mappa osszes fajljanak indexelese.
        :param folder_path: Teljes Windows eleresi ut (pl. C:\\Users\\istva\\Dev\\projekt)
        """
        if not os.path.isdir(folder_path):
            return f"Nem talalhato mappa: {folder_path}"
        exts = {".py",".ts",".js",".ps1",".md",".txt",".yaml",".yml",".json",".pdf",".docx",".cs",".go",".rs"}
        queued, errors = [], []
        for root, _, files in os.walk(folder_path):
            for fname in files:
                if any(fname.lower().endswith(e) for e in exts):
                    fpath = os.path.join(root, fname)
                    payload = json.dumps({"path": fpath}).encode("utf-8")
                    req = urllib.request.Request(
                        f"{VIVO_EMBED_URL}/index", data=payload,
                        headers={"Content-Type": "application/json"}, method="POST"
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=5): pass
                        queued.append(fname)
                    except Exception as e:
                        errors.append(f"{fname}: {e}")
        msg = f"Indexeles inditva: **{len(queued)} fajl**\n`{folder_path}`"
        if errors:
            msg += f"\nHibas: {', '.join(errors[:5])}"
        return msg

    def index_status(self) -> str:
        """Az indexer aktualis allapota es statisztikak."""
        try:
            with urllib.request.urlopen(f"{VIVO_EMBED_URL}/status", timeout=5) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            return f"vivo-embed nem elerheto: {e}"
        cols = data.get("collections", {})
        total = data.get("total", 0)
        st = "FOLYAMATBAN" if data.get("indexing") else "KESZ"
        return (
            f"**Indexer allapot: {st}**\n\n"
            f"| Gyujtemeny | Chunk |\n|---|---|\n"
            f"| docs | {cols.get('docs',0):,} |\n"
            f"| code | {cols.get('code',0):,} |\n"
            f"| notes | {cols.get('notes',0):,} |\n"
            f"| system | {cols.get('system',0):,} |\n"
            f"| **Osszes** | **{total:,}** |"
        )

    def trigger_reindex(self, full: bool = False) -> str:
        """Ujraindexeles inditasa (inkrementalis vagy teljes).
        :param full: True = mindent ujra, False = csak valtozott fajlok
        """
        url = f"{VIVO_EMBED_URL}/reindex?full={'true' if full else 'false'}"
        req = urllib.request.Request(url, data=b"", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            return f"Ujraindexeles inditva ({'TELJES' if full else 'INKREM'}): {data.get('status','ok')}"
        except urllib.error.URLError as e:
            return f"Hiba: {e}"
