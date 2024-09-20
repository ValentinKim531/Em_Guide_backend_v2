from crud import Postgres
from models import Message


async def save_message_to_db(
    db: Postgres, user_id: str, content: str, is_created_by_user: bool
):
    """
    Сохраняет сообщение (от пользователя или GPT) в базу данных.
    """
    message_data = {
        "user_id": user_id,
        "content": content,
        "is_created_by_user": is_created_by_user,
    }
    await db.add_entity(message_data, Message)
