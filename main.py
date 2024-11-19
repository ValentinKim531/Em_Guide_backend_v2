import logging
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from crud import Postgres
from services.database import async_session
from services.yandex_service import get_iam_token, refresh_iam_token
from server import main as websocket_server
from utils.logging_config import get_logger


logger = get_logger(name="main")

# Удаляем все предыдущие обработчики
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


app = FastAPI()


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


db = Postgres(async_session)


class Message(BaseModel):
    user_id: str
    content: str
    created_at: str


async def run_task_safe(coroutine, task_name):
    try:
        await coroutine
    except Exception as e:
        logger.error(f"Error in task '{task_name}': {e}")


@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Startup_event.")

        # Запускаем фоновые задачи с обработкой ошибок
        asyncio.create_task(run_task_safe(get_iam_token(), "get_iam_token"))
        asyncio.create_task(
            run_task_safe(refresh_iam_token(), "refresh_iam_token")
        )
        asyncio.create_task(
            run_task_safe(websocket_server(), "websocket_server")
        )

    except Exception as e:
        logger.error(f"Error during startup event: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    await logger.shutdown()


if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(app, host="0.0.0.0", port=8084, log_level="info")
    except Exception as e:
        logger.error(f"Error starting FastAPI server: {e}")
