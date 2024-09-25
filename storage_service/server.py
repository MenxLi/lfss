from fastapi import FastAPI
from contextlib import asynccontextmanager
from dataclasses import dataclass
from .database import Database

conn = Database()

@asynccontextmanager
async def lifespan():
    global conn
    try:
        await conn.init()
    finally:
        await conn.close()

app = FastAPI(docs_url=None, redoc_url=None)
