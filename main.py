import logging
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from crud import Postgres
from services.database import async_session
from services.yandex_service import get_iam_token, refresh_iam_token
from server import main as websocket_server


# # Удаляем все предыдущие обработчики
# for handler in logging.root.handlers[:]:
#     logging.root.removeHandler(handler)
#
# # Создаем новый обработчик
# handler = logging.StreamHandler()
# handler.setLevel(logging.WARNING)
# formatter = logging.Formatter(
#     "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# )
# handler.setFormatter(formatter)
# logging.root.addHandler(handler)
# logging.root.setLevel(logging.WARNING)

logging.getLogger("sqlalchemy").disabled = True
logging.getLogger("sqlalchemy.engine").disabled = True
logging.getLogger("sqlalchemy.pool").disabled = True
logging.getLogger("sqlalchemy.dialects").disabled = True

#
# logging.basicConfig(level=logging.INFO)
#
logger = logging.getLogger(__name__)

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
        uvicorn.run(app, host="0.0.0.0", port=8084, log_level="info")
    except Exception as e:
        logger.error(f"Error starting FastAPI server: {e}")
