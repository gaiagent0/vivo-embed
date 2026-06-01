"""MCP stdio szerver - Hermes + Claude Code integracio
Tools: search_knowledge, index_file, get_stats
"""
from __future__ import annotations
import asyncio
import json
import sys
import logging
from pathlib import Path
from .. engines.google_engine import GoogleEmbedder
from .. store.chroma_store import ChromaStore
from .. api.rest import _index_single

log = logging.getLogger("vivo_embed.mcp")

TOOLS = [
    {
        "name": "search_knowledge",
        "description": (
            "Szemantikus kereses a helyi tudasbazisban. "
            "Magyar es angol szoveget egyarant keres. "
            "Minden fajlt, kodot, dokumentumot es konfiguraciott tartalmaz a gepen."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keresesi kifejezes"},
                "top_k": {"type": "integer", "default": 8, "description": "Talalatok szama"},
                "collection": {
                    "type": "string",
                    "enum": ["docs", "code", "notes", "system", "web"],
                    "description": "Szures gyujtemenyre (opcionalis)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "index_file",
        "description": "Egy adott fajl azonnali indexelese a tudasbazisba.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Fajl teljes eleresi utja"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "get_stats",
        "description": "Indexelesi statisztikak es gyujtemeny merete.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

async def handle(request: dict) -> dict:
    method = request.get("method")
    rid    = request.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "vivo-embed", "version": "1.0"},
        }}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name   = request["params"]["name"]
        args   = request["params"].get("arguments", {})
        result = await call_tool(name, args)
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
        }}

    return {"jsonrpc": "2.0", "id": rid if rid is not None else 0,
            "error": {"code": -32601, "message": "Method not found"}}

async def call_tool(name: str, args: dict) -> dict:
    embedder = GoogleEmbedder()
    store    = ChromaStore()

    if name == "search_knowledge":
        query = args["query"]
        top_k = args.get("top_k", 8)
        col   = args.get("collection")
        emb   = embedder.embed_query(query)
        if col:
            raw = store.search(col, emb, n_results=top_k)
            results = [
                {"content": raw["documents"][0][i],
                 "path": raw["metadatas"][0][i].get("path", ""),
                 "score": round(1.0 - raw["distances"][0][i], 4)}
                for i in range(len(raw["documents"][0]))
            ]
        else:
            raw = store.search_all(emb, n_results=top_k)
            results = [
                {"content": r["content"],
                 "path": r["metadata"].get("path", ""),
                 "score": round(1.0 - r["distance"], 4),
                 "collection": r["collection"]}
                for r in raw
            ]
        return {"results": results, "count": len(results)}

    if name == "index_file":
        path = Path(args["path"])
        if not path.exists():
            return {"error": f"Nem talalhato: {path}"}
        _index_single(path)
        return {"status": "ok", "path": str(path)}

    if name == "get_stats":
        return {"collections": store.stats(), "total": sum(store.stats().values())}

    return {"error": f"Ismeretlen tool: {name}"}

async def run_stdio():
    log.info("vivo-embed MCP szerver indul (stdio)...")
    while True:
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        try:
            req = json.loads(line.strip())
            resp = await handle(req)
            print(json.dumps(resp, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"jsonrpc": "2.0", "id": 0,
                              "error": {"code": -32700, "message": str(e)}}), flush=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_stdio())
