import logging
from openai import AsyncOpenAI
from utils.config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logger = logging.getLogger(__name__)


async def send_to_gpt(dialogue_history, instruction):
    """
    Отправляет запрос в GPT с учетом накопленной истории диалога.
    """
    logger.info(f"dialogue_history: {dialogue_history}")
    # Формируем запрос с историей диалога
    messages = [{"role": "system", "content": instruction}] + dialogue_history
    logger.info(f"messages_to_GPT: {messages}")

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=1000,
    )

    logger.info(f"GPT response: {response}")
    return response.choices[0].message.content
