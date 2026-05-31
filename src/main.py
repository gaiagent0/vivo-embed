"""Belépési pont — REST API szerver"""
import logging
import uvicorn
from vivo_embed.api.rest import app
from vivo_embed.config import get

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

if __name__ == "__main__":
    cfg = get()["api"]
    uvicorn.run(app, host=cfg["host"], port=cfg["port"], log_level="info")
