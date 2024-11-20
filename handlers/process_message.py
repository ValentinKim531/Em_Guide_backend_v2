import json
from datetime import datetime
import re
from constants.assistants_answers_var import (
    DailySurveyQuestions,
    RegistrationQuestions,
)
from models import User
from services.openai_service import send_to_gpt
from services.save_message_to_db import save_message_to_db
from services.survey_service import update_survey_data
from services.user_registration_service import update_user_registration_data
from utils.config import ASSISTANT_ID, ASSISTANT2_ID, ASSISTANT3_ID
from utils.redis_client import (
    get_user_dialogue_history,
    save_user_dialogue_history,
)
from crud import Postgres
from services.audio_text_processor import process_audio_and_text
import asyncio
from utils.logging_config import get_logger


logger = get_logger(name="process_message")
tasks = []


async def safe_add_entity(db, user_data):
    try:
        await db.add_entity(user_data, User)
    except Exception as e:
        logger.error(f"Error adding user to database: {e}")


async def safe_update_survey_data(db, user_id, gpt_response_content):
    try:
        await update_survey_data(db, user_id, gpt_response_content)
    except Exception as e:
        logger.error(f"Error in update_survey_data: {e}")


async def register_user_if_not_exists(db, user_id):
    """
    Проверяет существование пользователя в фоне и добавляет, если его нет.
    """
    try:
        # Проверка существующего пользователя
        existing_user_task = asyncio.create_task(
            db.get_entity_parameter(User, {"userid": str(user_id)})
        )

        # Ждём завершения проверки
        existing_user = await existing_user_task
        if not existing_user:
            # Добавление пользователя в фоне
            task = asyncio.create_task(
                db.add_entity({"userid": str(user_id)}, User)
            )
            tasks.append(task)
    except Exception as e:
        logger.error(f"Error during user registration: {e}")


async def process_user_message(user_id: str, message: dict, db: Postgres):
    """
    Обрабатывает ответ пользователя на основании его состояния (регистрация или опрос) с учетом истории диалога.
    """

    # Получаем статус регистрации из Redis
    # is_registration = await get_registration_status(user_id)
    is_registration = False
    logger.info(f"is_registration for user is: {is_registration}")

    # регистрация пользователя по номеру телефона, если нет в базе users

    # Создаём задачу для проверки существующего пользователя
    task = asyncio.create_task(register_user_if_not_exists(db, user_id))
    tasks.append(task)
    logger.info(f"message111: {message}")
    if is_registration:
        # Направляем запрос в GPT с инструкцией по регистрации
        instruction = ASSISTANT2_ID
        logger.info(f"Assistant is in registration mode for user {user_id}")
    else:
        if message["action"] == "all_in_one_message":
            instruction = ASSISTANT3_ID
            logger.info(
                f"Assistant is in all_in_one_message mode for user {user_id}"
            )
        else:
            instruction = ASSISTANT_ID
            logger.info(
                f"Assistant is in daily survey mode for user {user_id}"
            )

    # Извлекаем историю диалога
    # dialogue_history = await get_user_dialogue_history(user_id)
    dialogue_history = []
    logger.info(f"dialogue_history_begin: {dialogue_history}")

    user_language = "ru"
    text = await process_audio_and_text(message, user_language)
    logger.info(f"text: {text}")
    # Если текст не извлечен из аудио, возвращаем сообщение об ошибке
    if not text:
        if instruction == ASSISTANT3_ID:
            return {
                "type": "response",
                "status": "error",
                "action": "all_in_one_message",
                "error": "server_error",
                "message": "К сожалению, не удалось распознать ваш голос. Попробуйте, пожалуйста, ещё раз.",
                "data": message,
            }
        elif instruction == ASSISTANT_ID:
            return {
                "type": "response",
                "status": "error",
                "action": "message",
                "error": "server_error",
                "message": "К сожалению, не удалось распознать ваш ответ. Попробуйте, пожалуйста, ещё раз.",
                "data": message,
            }

    message["text"] = text
    message["audio"] = None
    # Добавляем текущее сообщение пользователя в историю
    dialogue_history.append(
        {"role": "user", "content": json.dumps(message, ensure_ascii=False)}
    )

    # Сохраняем сообщение пользователя в базу данных
    task = asyncio.create_task(save_message_to_db(db, user_id, message, True))
    tasks.append(task)

    if message["action"] == "all_in_one_message":
        gpt_response = await send_to_gpt(dialogue_history, instruction)
        # Добавляем ответ GPT в историю
        dialogue_history.append({"role": "assistant", "content": gpt_response})
        logger.info(f"gpt_response_from_111: {gpt_response}")

        try:
            gpt_response_content = json.loads(gpt_response)
            logger.info(f"gpt_response_type: {type(gpt_response_content)}")
            gpt_response_for_update = gpt_response_content.get("data")
            for message in gpt_response_for_update:
                task = asyncio.create_task(
                    safe_update_survey_data(db, user_id, message)
                )
                tasks.append(task)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding GPT response: {e}")
            return {
                "type": "response",
                "status": "error",
                "action": "all_in_one_message",
                "error": "server_error",
                "message": "Ошибка при обработке ответа от GPT",
            }

        return gpt_response_content

    # Сохраняем сообщение пользователя в базу опросов
    task = asyncio.create_task(safe_update_survey_data(db, user_id, message))
    tasks.append(task)

    # Отправляем запрос в GPT с текущей историей диалога
    gpt_response = await send_to_gpt(dialogue_history, instruction)

    # Сохраняем ответ GPT в базу данных
    task = asyncio.create_task(
        save_message_to_db(db, user_id, gpt_response, False)
    )
    tasks.append(task)

    # Добавляем ответ GPT в историю
    dialogue_history.append({"role": "assistant", "content": gpt_response})

    # Сохраняем обновленную историю в Redis
    # await save_user_dialogue_history(user_id, dialogue_history)

    # Проверяем наличие ключа "question" в ответе GPT
    try:
        gpt_response_content = json.loads(gpt_response)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding GPT response: {e}")
        return {
            "type": "response",
            "status": "error",
            "error": "server_error",
            "message": "Ошибка при обработке ответа от GPT",
        }

    # Проверяем, что ответ валидирован, то есть отсутствует ключ 'question'
    if "question" not in gpt_response_content:
        if is_registration:
            if gpt_response_content["index"] == 1:
                try:
                    # Удаляем запятые, если они есть
                    text = gpt_response_content["text"].replace(",", "")

                    # Используем регулярное выражение для поиска первой даты в тексте
                    match = re.search(r"\d{1,2} \w+ \d{4}", text)

                    if match:
                        # Извлекаем ФИО и дату
                        birthdate_str = match.group(
                            0
                        )  # Дата (например, 20 January 2000)
                        fio = text[: match.start()].strip()  # ФИО до даты

                        # Преобразуем дату в нужный формат
                        birthdate = datetime.strptime(
                            birthdate_str, "%d %B %Y"
                        ).date()

                        # Создаем нового пользователя с указанными данными
                        logger.info(
                            f"User with userid {user_id} not found, creating a new one with fio and birthdate"
                        )
                        new_user_data = {
                            "userid": user_id,
                            "fio": fio,
                            "birthdate": birthdate,
                        }
                        task = asyncio.create_task(
                            safe_add_entity(db, new_user_data)
                        )
                        tasks.append(task)

                        logger.info(
                            f"Created user {user_id} with fio: {fio} and birthdate: {birthdate}"
                        )
                    else:
                        raise ValueError("Date not found in the text")
                except ValueError as e:
                    logger.error(
                        f"Error parsing fio and birthdate from message: {gpt_response_content['text']}. Error: {e}"
                    )
                    return {
                        "type": "response",
                        "status": "error",
                        "message": "Invalid data format for fio and birthdate",
                    }
            else:
                task = asyncio.create_task(
                    update_user_registration_data(
                        db, user_id, gpt_response_content
                    )
                )
                tasks.append(task)

        else:
            task = asyncio.create_task(
                safe_update_survey_data(db, user_id, gpt_response_content)
            )
            tasks.append(task)

    if "question" in gpt_response_content:
        # Получаем индекс текущего вопроса
        question_index = gpt_response_content.get("index")

        # Проверяем, есть ли вариант ответов для данного индекса
        if question_index:
            try:
                # Получаем варианты ответов для текущего вопроса
                if instruction == ASSISTANT_ID:
                    question_enum = DailySurveyQuestions[
                        f"INDEX_{question_index}"
                    ]
                else:
                    question_enum = RegistrationQuestions[
                        f"INDEX_{question_index}"
                    ]
                options = question_enum.value["options"]
                is_custom_option_allowed = question_enum.value[
                    "is_custom_option_allowed"
                ]

                # Формируем правильный ответ с вопросом и вариантами ответов
                return {
                    "type": "response",
                    "status": "pending",
                    "action": "message",
                    "data": {
                        "index": question_index,
                        "question": {
                            "text": gpt_response_content["question"]["text"],
                            "options": options,
                            "is_custom_option_allowed": is_custom_option_allowed,
                        },
                    },
                }

            except KeyError:
                logger.error(
                    f"Index {question_index} not found in DailySurveyQuestions"
                )
                return {
                    "type": "response",
                    "status": "error",
                    "message": f"Вопрос с индексом {question_index} не найден",
                }

    return {
        "type": "response",
        "status": "success",
        "action": "message",
        "data": gpt_response_content,
    }
