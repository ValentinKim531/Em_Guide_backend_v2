import json
from crud import Postgres
from models import Message


async def save_message_to_db(
    db: Postgres, user_id: str, content: dict | str, is_created_by_user: bool
):
    """
    Сохраняет сообщение (от пользователя или GPT) в базу данных.
    """
    # Преобразуем content в JSON-строку, если это dict
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False)

    # Формируем данные для сохранения
    message_data = {
        "user_id": user_id,
        "content": content,  # Уже строка JSON
        "is_created_by_user": is_created_by_user,
    }

    # Добавляем запись в базу данных
    await db.add_entity(message_data, Message)
