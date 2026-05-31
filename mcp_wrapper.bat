@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONPATH=C:\AI\apps\vivo-embed\src
if not defined GOOGLE_API_KEY set GOOGLE_API_KEY=your-key-here
"C:\AI\apps\vivo-embed\.venv\Scripts\python.exe" -m vivo_embed.api.mcp_server
