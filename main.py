import logging
import asyncio
from fastapi import FastAPI, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from handlers.process_message import process_message
from crud import Postgres
from services.database import async_session
from services.yandex_service import get_iam_token, refresh_iam_token
from server import main as websocket_server

# Настройка логирования
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Настройка уровня логирования для SQLAlchemy
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)

app = FastAPI()


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


db = Postgres(async_session)


class Message(BaseModel):
    user_id: str
    content: str
    created_at: str


@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Supabase startup_event.")
        get_iam_token()
        task = asyncio.create_task(refresh_iam_token())
        _ = task
        asyncio.ensure_future(websocket_server())
    except Exception as e:
        logger.error(f"Error during startup event: {e}")


if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
    except Exception as e:
        logger.error(f"Error starting FastAPI server: {e}")
