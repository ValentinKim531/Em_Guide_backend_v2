import json
from crud import Postgres
from models import Survey
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, select
from utils.logging_config import get_logger


logger = get_logger(name="survey_service")


async def update_survey_data(db: Postgres, user_id: str, message: dict):
    """
    Обновляет информацию по ежедневному опросу на основании полученных данных.
    Если запись по опросу еще не существует или была создана более 1 часа назад, создается новая.
    """
    logger.info(f"message_for_updating_survey: {message}")

    try:
        # Преобразуем content в JSON-строку, если это dict
        if isinstance(message, dict):
            content = json.dumps(message, ensure_ascii=False)

        # Текущее время
        current_time = datetime.now(timezone.utc)

        # Начало сегодняшнего дня
        today_start = current_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Порог времени для проверки на запись созданную менее 1 часа назад
        one_hour_ago = current_time - timedelta(hours=1)

        logger.info(f"Current time (UTC): {current_time}")
        logger.info(f"Today start (UTC): {today_start}")
        logger.info(f"Time 1 hour ago: {one_hour_ago}")

        # Поиск записи с userid и фильтрация по дате создания
        async with db.async_session() as session:
            # Создаем запрос для поиска записи по user_id и времени создания
            query = select(Survey).where(
                and_(
                    Survey.userid == user_id,
                    Survey.created_at
                    >= today_start,  # Фильтр по сегодняшнему дню
                    Survey.created_at
                    >= one_hour_ago,  # Фильтр по времени создания записи менее 1 часа назад
                )
            )
            result = await session.execute(query)
            survey = result.scalars().first()

        # Если запись существует и была создана менее 1 часа назад, обновляем её
        if survey and survey.created_at >= one_hour_ago:
            logger.info(f"survey_created_at: {survey.created_at}")
            logger.info(
                f"Found survey created within the last hour for user {user_id}. Updating it."
            )

            if message["index"] == 1 and message["text"]:
                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "headache_today",
                    message["text"],
                    Survey,
                )
            elif message["index"] == 2 and message["text"]:
                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "medicament_today",
                    message["text"],
                    Survey,
                )
            elif message["index"] == 3 and message["text"]:
                if not isinstance(message["text"], str):
                    # Преобразуем только если это не строка
                    pain_intensity = str(message["text"])
                else:
                    pain_intensity = message["text"]

                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "pain_intensity",
                    pain_intensity,
                    Survey,
                )
            elif message["index"] == 4 and message["text"]:
                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "pain_area",
                    message["text"],
                    Survey,
                )
            elif message["index"] == 5 and message["text"]:
                await db.update_entity_parameter(
                    (survey.survey_id, user_id),
                    "area_detail",
                    message["text"],
                    Survey,
                )
            elif message["index"] == 6 and message["text"]:
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
            if message["index"] == 1 and message["text"]:
                new_survey_data["headache_today"] = message["text"]
            elif message["index"] == 2 and message["text"]:
                new_survey_data["medicament_today"] = message["text"]
            elif message["index"] == 3 and message["text"]:
                if not isinstance(message["text"], str):
                    # Преобразуем только если это не строка
                    new_survey_data["pain_intensity"] = str(message["text"])
                else:
                    new_survey_data["pain_intensity"] = message["text"]
            elif message["index"] == 4 and message["text"]:
                new_survey_data["pain_area"] = message["text"]
            elif message["index"] == 5 and message["text"]:
                new_survey_data["area_detail"] = message["text"]
            elif message["index"] == 6 and message["text"]:
                new_survey_data["pain_type"] = message["text"]

            # Добавляем новую запись
            await db.add_entity(new_survey_data, Survey)

            logger.info(f"Created new survey for user {user_id}")

    except Exception as e:
        logger.error(f"Error updating survey data: {e}")
