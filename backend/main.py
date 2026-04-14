from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import get_config
from backend.db.database import create_tables
from backend.llm.factory import get_provider
from backend.routers import audio as audio_router
from backend.routers import calendar as calendar_router
from backend.routers import goals as goals_router
from backend.routers import sessions as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield
    # Clean shutdown — release thread pool to avoid semaphore leak warnings
    audio_router._executor.shutdown(wait=False)


app = FastAPI(title="LifePilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(goals_router.router)
app.include_router(sessions_router.router)
app.include_router(audio_router.router)
app.include_router(calendar_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}


class ChatRequest(BaseModel):
    message: str
    system: str = "You are a helpful assistant."


class ChatResponse(BaseModel):
    response: str
    provider: str


@app.post("/chat", response_model=ChatResponse, tags=["llm"])
async def chat(req: ChatRequest):
    """Stateless single-turn chat. Config reloaded on every request."""
    provider = get_provider(get_config())
    response = await provider.chat(
        messages=[{"role": "user", "content": req.message}],
        system=req.system,
    )
    return ChatResponse(response=response, provider=provider.provider_name())
