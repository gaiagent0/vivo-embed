# vivo-embed

**Magyar Embedding Indexer Agent** — Snapdragon X Elite (vivo2) gépen futó, teljes gépes tudásbázist indexelő és szemantikusan kereső rendszer.

## Áttekintés

```
Fájlok (minden partíció)
    ↓
File Crawler (inkrementális, diff-alapú)
    ↓
Smart Chunker (magyar mondathatár-tudatos)
    ↓
Google Gemini Embedding (gemini-embedding-001, 3072 dim)
    ↓
ChromaDB (persistent, cosine similarity)
    ↓
FastAPI REST :7272  +  MCP stdio server
    ↓
Hermes Agent / Claude Code / bármely app
```

## Főbb jellemzők

- **Embedding**: `gemini-embedding-001` (Google AI Studio free tier, 3072 dim, multilingual)
- **Vektor DB**: ChromaDB persistent (5 collection: docs, code, notes, system, web)
- **REST API**: FastAPI port 7272 — `/search`, `/index`, `/status`, `/reindex`
- **MCP szerver**: stdio, JSON-RPC 2.0 — Hermes és Claude Desktop integrációhoz
- **Crawler**: minden partíció (C:, D:, E:, ...), inkrementális hash-alapú diff
- **Chunker**: magyar rövidítés-tudatos mondathatár felismerés
- **Extractors**: PDF (pdfplumber), DOCX (python-docx), MD, TXT, PY, PS1, YAML, JSON

## Gyors telepítés

```powershell
git clone https://github.com/gaiagent0/vivo-embed.git C:\AI\apps\vivo-embed
cd C:\AI\apps\vivo-embed

# API key beállítása
copy .env.example .env
notepad .env  # GOOGLE_API_KEY=AIza...

# Telepítés és indítás
.\setup.ps1
.\start.ps1
```

## API használat

```powershell
# Keresés
$b = [System.Text.Encoding]::UTF8.GetBytes('{"query":"LiteLLM configuration","top_k":5}')
Invoke-WebRequest -Uri http://localhost:7272/search -Method POST `
  -Headers @{"Content-Type"="application/json"} -Body $b

# Státusz
Invoke-WebRequest -Uri http://localhost:7272/status

# Teljes újraindexelés
Invoke-WebRequest -Uri http://localhost:7272/reindex -Method POST
```

## MCP integráció

### Hermes (`config.yaml`)

```yaml
mcp_servers:
  vivo-embed:
    command: cmd
    args: [/c, C:\AI\apps\vivo-embed\mcp_wrapper.bat]
    connect_timeout: 15
    timeout: 30
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "vivo-embed": {
      "command": "cmd",
      "args": ["/c", "C:\\AI\\apps\\vivo-embed\\mcp_wrapper.bat"]
    }
  }
}
```

### MCP Tools

| Tool | Leírás |
|---|---|
| `search_knowledge` | Szemantikus keresés, collection filter, top_k |
| `index_file` | Egyedi fájl azonnali indexelése |
| `get_stats` | Collection méret statisztikák |

## Projekt struktúra

```
vivo-embed/
├── src/vivo_embed/
│   ├── config.py              # Konfiguráció betöltő
│   ├── engines/
│   │   └── google_engine.py   # Gemini embedding (httpx REST)
│   ├── store/
│   │   └── chroma_store.py    # ChromaDB wrapper
│   ├── indexer/
│   │   ├── crawler.py         # Multi-partíció fájl crawler
│   │   ├── chunker.py         # Magyar-tudatos chunker
│   │   └── extractors.py      # PDF/DOCX/MD/code extractors
│   └── api/
│       ├── rest.py            # FastAPI REST
│       └── mcp_server.py      # MCP stdio szerver
├── src/main.py                # Belépési pont
├── config.yaml                # Fő konfig
├── requirements.txt
├── setup.ps1                  # Egyszeri telepítés
├── start.ps1                  # Szerver indítás
└── mcp_wrapper.bat            # MCP launcher (Hermes/Claude)
```

## Követelmények

- Windows 11 ARM64 (Snapdragon X Elite) vagy x64
- Python 3.12+
- [uv](https://astral.sh/uv) csomagkezelő
- Google AI Studio API key (ingyenes: [aistudio.google.com](https://aistudio.google.com/apikey))

## Teljesítmény

| Metrika | Érték |
|---|---|
| Embedding model | gemini-embedding-001 |
| Dimenzió | 3072 |
| Batch méret | 20 chunk/kérés |
| Rate limit (free) | ~1500 kérés/nap |
| ChromaDB hasonlóság | cosine |
| Keresési válaszidő | ~1-2s |

## Kapcsolódó projektek

- [gaiagent0/pve-ai-agent](https://github.com/gaiagent0/pve-ai-agent) — Proxmox AI sysadmin agent
- [gaiagent0/hu-voice-assistant](https://github.com/gaiagent0/hu-voice-assistant) — Magyar hangalapú asszisztens

## Licenc

MIT
