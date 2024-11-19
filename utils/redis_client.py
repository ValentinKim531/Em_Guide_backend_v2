import aioredis
from utils.config import REDIS_URL
from collections import defaultdict
import json
from utils.logging_config import get_logger

# Инициализация подключения к Redis
redis = aioredis.from_url(REDIS_URL)


logger = get_logger(name="redis_client")


async def get_user_dialogue_history(user_id):
    """
    Получает историю диалога пользователя из Redis с корректной кодировкой.
    """
    try:
        # Получаем строку JSON из Redis
        dialogue_history = await redis.get(f"dialogue_history:{user_id}")
        if dialogue_history:
            return json.loads(dialogue_history)
        return []
    except Exception as e:
        logger.error(f"Error getting dialogue history for user {user_id}: {e}")
        return []


async def save_user_dialogue_history(user_id, dialogue):
    """
    Сохраняет историю диалога пользователя в Redis с правильной кодировкой.
    """
    try:
        dialogue_json = json.dumps(dialogue, ensure_ascii=False)
        await redis.set(f"dialogue_history:{user_id}", dialogue_json)
    except Exception as e:
        logger.error(f"Error saving dialogue history for user {user_id}: {e}")


async def delete_user_dialogue_history(user_id: str) -> None:
    """
    Удаляет историю диалога пользователя из Redis.
    """
    try:
        await redis.delete(f"dialogue_history:{user_id}")
    except Exception as e:
        logger.error(
            f"Ошибка при удалении истории диалога для пользователя {user_id}: {e}"
        )


async def save_registration_status(user_id: str, is_registration: bool):
    """
    Сохраняет статус регистрации в Redis.
    """
    try:
        await redis.set(
            f"registration_status:{user_id}",
            json.dumps({"is_registration": is_registration}),
        )
    except Exception as e:
        logger.error(
            f"Error saving registration status for user {user_id}: {e}"
        )


async def get_registration_status(user_id: str) -> bool:
    """
    Получает статус регистрации из Redis.
    """
    try:
        registration_status = await redis.get(f"registration_status:{user_id}")
        if registration_status:
            return json.loads(registration_status).get(
                "is_registration", False
            )
        return False
    except Exception as e:
        logger.error(
            f"Error getting registration status for user {user_id}: {e}"
        )
        return False
