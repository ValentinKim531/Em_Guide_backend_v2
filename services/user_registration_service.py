from crud import Postgres
from models import User
from utils.logging_config import get_logger

logger = get_logger(name="user_registration_service")


async def update_user_registration_data(
    db: Postgres, user_id: str, message: dict
):
    """
    Обновляет информацию пользователя при регистрации на основании полученных данных.
    """
    try:
        if message["index"] == 2:
            await db.update_entity_parameter(
                user_id, "menstrual_cycle", message["text"], User
            )

        elif message["index"] == 3:
            await db.update_entity_parameter(
                user_id, "country", message["text"], User
            )

        elif message["index"] == 4:
            await db.update_entity_parameter(
                user_id, "medication_name", message["text"], User
            )

        elif message["index"] == 5:
            await db.update_entity_parameter(
                user_id, "const_medication_name", message["text"], User
            )

    except Exception as e:
        logger.error(f"Error updating user registration data: {e}")
