import json
import anthropic
import asyncio
from utils.config import ANTHROPIC_API_KEY
import time
from openai import AsyncOpenAI
from utils.config import OPENAI_API_KEY
from utils.logging_config import get_logger

logger = get_logger(name="openai_service")


# client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
#
#
# async def send_to_gpt(dialogue_history, instruction):
#     """
#     Отправляет запрос в Anthropic Claude с учетом накопленной истории диалога.
#     Используется prompt-caching для ускорения обработки.
#     """
#     try:
#         # Проверка и преобразование данных в `dialogue_history`
#         for i, message in enumerate(dialogue_history):
#             if isinstance(message, dict):
#                 # Если это уже dict, ничего не делаем
#                 pass
#             elif isinstance(message, str):
#                 # Если это строка, преобразуем в dict
#                 dialogue_history[i] = json.loads(message)
#             else:
#                 raise ValueError(
#                     f"Unsupported data format at index {i}: {message}"
#                 )
#
#         logger.info(f"dialogue_history: {dialogue_history}")
#
#         # Замер времени начала
#         start_time = time.perf_counter()
#
#         # Устанавливаем системное сообщение
#         system_content = {
#             "type": "text",
#             "text": instruction,
#             "cache_control": {"type": "ephemeral"},
#         }
#
#         # Формируем сообщения для Claude
#         messages = [
#             {"role": "user", "content": message["content"]}
#             for message in dialogue_history
#         ]
#         logger.info(f"messages_to_Claude: {messages}")
#
#         # Отправляем запрос к Anthropic Claude
#         response = await asyncio.to_thread(
#             client.beta.prompt_caching.messages.create,
#             model="claude-3-5-haiku-20241022",
#             max_tokens=1000,
#             system=[system_content],  # Системное сообщение передается отдельно
#             messages=messages,
#         )
#
#         logger.info(
#             f"Claude cache stats: creation tokens = {response.usage.cache_creation_input_tokens}, read tokens = {response.usage.cache_read_input_tokens}"
#         )
#
#         # Замер времени завершения
#         end_time = time.perf_counter()
#         logger.info(
#             f"Claude API request duration (precise): {end_time - start_time:.2f} seconds"
#         )
#
#         # Логируем и возвращаем ответ
#         logger.info(f"Claude API response: {response}")
#
#         # Обработка ответа
#         assistant_reply = (
#             response.content[0].text.strip() if response.content else None
#         )
#
#         if assistant_reply:
#             try:
#                 # Разделение JSON-объекта и текстового ответа
#                 json_part = assistant_reply.split("\n\n")[
#                     0
#                 ]  # Извлекаем первую часть
#                 parsed_json = json.loads(json_part)
#                 logger.info(f"Parsed JSON from response: {parsed_json}")
#
#                 # Преобразуем словарь в строку перед использованием
#                 if isinstance(parsed_json, dict):
#                     return json.dumps(parsed_json, ensure_ascii=False)
#                 else:
#                     return parsed_json
#             except json.JSONDecodeError as e:
#                 logger.error(f"Error decoding JSON part: {e}")
#                 return assistant_reply
#         else:
#             logger.error("Empty response content from Claude API.")
#             return "Error: Empty response content."
#
#     except Exception as e:
#         logger.error(f"Error sending request to Claude with caching: {e}")
#         return "Error processing the request."


client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def send_to_gpt(dialogue_history, instruction):
    """
    Отправляет запрос в GPT с учетом накопленной истории диалога.
    """
    try:
        logger.info(f"dialogue_history: {dialogue_history}")

        # Формируем запрос с историей диалога
        messages = [
            {"role": "system", "content": instruction}
        ] + dialogue_history
        logger.info(
            f"message_to_GPT: {messages[-1].get('content', 'No content found')}"
        )

        # Замер времени выполнения
        start_time = time.time()

        # Отправка запроса в GPT
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        # Вычисляем длительность запроса
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"GPT API request duration: {duration:.2f} seconds")

        # Логируем и возвращаем результат
        logger.info(
            f"GPT_response_content: {response.choices[0].message.content}"
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Error sending request to GPT: {e}")
        return "Error processing the request."
