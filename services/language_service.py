from crud import Postgres
from models import User
from utils.logging_config import get_logger

logger = get_logger(name="language_service")


async def change_language(user_id: str, language: str, db: Postgres):
    try:
        await db.update_entity_parameter(
            entity_id=user_id,
            parameter="language",
            value=language,
            model_class=User,
        )
        logger.info(f"Language updated successfully for user {user_id}")
        return language
    except Exception as e:
        logger.error(f"Error updating language: {e}")
        return f"Failed to update language: {e}"
