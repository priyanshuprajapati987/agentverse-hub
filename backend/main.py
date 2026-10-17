"""AgentVerse Hub - FastAPI Backend"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import agents, health
from security import SecurityMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="AgentVerse Hub API",
    description="AI Agent Marketplace - Build, test, and share agents",
    version="0.1.0",
)

# CORS — explicit origin allowlist (no wildcard)
_allowed_origins = os.getenv(
    "AGENTVERSE_CORS_ORIGINS",
    "http://localhost:3001,http://localhost:3000,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security: rate limiting + input sanitization + optional API-key auth
app.add_middleware(SecurityMiddleware)

# Routes
app.include_router(health.router, tags=["health"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])


@app.get("/")
async def root():
    return {
        "name": "AgentVerse Hub API",
        "version": "0.1.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
