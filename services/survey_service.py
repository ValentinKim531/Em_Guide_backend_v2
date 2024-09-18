import logging
from crud import Postgres
from models import Survey
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def update_survey_data(db: Postgres, user_id: str, message: dict):
    """
    Обновляет информацию по ежедневному опросу на основании полученных данных.
    Если запись по опросу еще не существует или была создана более 1 часа назад, создается новая.
    """
    try:
        # Получаем текущее время
        current_time = datetime.utcnow().replace(tzinfo=timezone.utc)

        # Порог времени для создания новой записи — 1 час назад
        one_hour_ago = current_time - timedelta(hours=1)

        # Проверяем, существует ли запись, созданная за последние 1 час
        survey = await db.get_entity_parameter(
            Survey,
            filters={
                "userid": user_id,
            },
        )

        # Если запись существует и была создана менее 1 часа назад, обновляем её
        if survey and survey.created_at >= one_hour_ago:
            logger.info(
                f"Found survey created within the last hour for user {user_id}. Updating it."
            )

            if message["index"] == 1:
                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "headache_today",
                    message["text"],
                    Survey,
                )
            elif message["index"] == 2:
                try:
                    pain_intensity = int(message["text"])
                    await db.update_entity_parameter(
                        (survey.survey_id, user_id),
                        "pain_intensity",
                        pain_intensity,
                        Survey,
                    )
                except ValueError:
                    logger.error(
                        f"Invalid input for pain_intensity: {message['text']}"
                    )

            elif message["index"] == 3:
                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "pain_area",
                    message["text"],
                    Survey,
                )
            elif message["index"] == 4:
                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "area_detail",
                    message["text"],
                    Survey,
                )
            elif message["index"] == 5:
                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "pain_type",
                    message["text"],
                    Survey,
                )

            logger.info(f"Updated survey for user {user_id}")

        # Если записи нет или она была создана более часа назад, создаем новую запись
        else:
            logger.info(
                f"No recent survey found or survey is older than 1 hour. Creating a new survey for user {user_id}."
            )

            # Создаем новую запись
            new_survey_data = {"userid": user_id}

            # Заполняем первое поле в новой записи
            if message["index"] == 1:
                new_survey_data["headache_today"] = message["text"]
            elif message["index"] == 2:
                try:
                    new_survey_data["pain_intensity"] = int(message["text"])
                except ValueError as e:
                    logger.error(
                        f"Error converting pain intensity to integer: {e}"
                    )
                    return {
                        "type": "response",
                        "status": "error",
                        "message": "Invalid input for pain intensity, must be a number.",
                    }
            elif message["index"] == 3:
                new_survey_data["pain_area"] = message["text"]
            elif message["index"] == 4:
                new_survey_data["area_detail"] = message["text"]
            elif message["index"] == 5:
                new_survey_data["pain_type"] = message["text"]

            # Добавляем новую запись
            await db.add_entity(new_survey_data, Survey)

            logger.info(f"Created new survey for user {user_id}")

    except Exception as e:
        logger.error(f"Error updating survey data: {e}")
