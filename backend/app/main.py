from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(title="InsightCase API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "service": "InsightCase API",
        "health": "/health",
        "api": "/api/v1",
        "docs": "/docs",
        "ui": "Start the React app: cd frontend && npm run dev — then open http://localhost:5173",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
