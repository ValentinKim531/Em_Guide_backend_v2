import json

from constants.assistants_answers_var import (
    DailySurveyQuestions,
    RegistrationQuestions,
)
from models import User
from services.openai_service import send_to_gpt
from utils.config import ASSISTANT_ID, ASSISTANT2_ID
from utils.redis_client import (
    get_user_dialogue_history,
    save_user_dialogue_history,
)
from crud import Postgres
import logging

logger = logging.getLogger(__name__)


async def process_user_message(user_id: str, message: dict, db: Postgres):
    """
    Обрабатывает ответ пользователя на основании его состояния (регистрация или опрос) с учетом истории диалога.
    """

    user = await db.get_entity_parameter(User, {"userid": user_id})
    logger.info(f"message: {message}")

    if user:
        instruction = ASSISTANT_ID
        logger.info(f"Assistant is daily survey")
    else:
        instruction = ASSISTANT2_ID
        logger.info(f"Assistant is Registration")

    # Извлекаем историю диалога
    dialogue_history = await get_user_dialogue_history(user_id)

    # Добавляем текущее сообщение пользователя в историю
    dialogue_history.append(
        {"role": "user", "content": json.dumps(message, ensure_ascii=False)}
    )

    # Отправляем запрос в GPT с текущей историей диалога
    gpt_response = await send_to_gpt(dialogue_history, instruction)

    # Добавляем ответ GPT в историю
    dialogue_history.append({"role": "assistant", "content": gpt_response})

    # Сохраняем обновленную историю в Redis
    await save_user_dialogue_history(user_id, dialogue_history)

    # Проверяем наличие ключа "question" в ответе GPT
    try:
        gpt_response_content = json.loads(gpt_response)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding GPT response: {e}")
        return {
            "type": "response",
            "status": "error",
            "message": "Ошибка при обработке ответа от GPT",
        }

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
