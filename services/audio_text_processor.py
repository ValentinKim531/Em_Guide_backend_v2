import base64
import io
import os
import asyncio
import subprocess
import tempfile
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from .yandex_service import recognize_speech
from utils.logging_config import get_logger

logger = get_logger(name="audio_text_processor")


async def process_audio(audio_content_encoded, user_language):
    """
    Обрабатывает аудио сообщение в фоне.
    """
    try:
        # Декодируем base64
        audio_content = base64.b64decode(audio_content_encoded)
        logger.info("Successfully decoded base64 audio content.")

        # Сохраняем аудиоданные во временный файл
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".aac")
        with open(temp_input.name, "wb") as f:
            f.write(audio_content)
        logger.info(f"Saved AAC data to temporary file: {temp_input.name}")

        # Конвертация AAC в WAV с помощью ffmpeg
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        try:
            ffmpeg_command = [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-i",
                temp_input.name,
                temp_output.name,
            ]
            subprocess.run(
                ffmpeg_command,
                stdout=subprocess.DEVNULL,  # Отключение стандартного вывода
                stderr=subprocess.DEVNULL,  # Отключение вывода ошибок
            )
            logger.info("Successfully converted AAC to WAV using ffmpeg.")
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed to convert AAC to WAV: {e}")
            raise CouldntDecodeError("Failed to decode AAC file using ffmpeg")

        # Обрабатываем WAV с помощью AudioSegment
        with open(temp_output.name, "rb") as f:
            wav_data = f.read()
        audio = AudioSegment.from_file(io.BytesIO(wav_data), format="wav")
        logger.info("Successfully created AudioSegment from WAV data.")

        # Конвертируем в OGG
        ogg_io = io.BytesIO()
        audio.export(ogg_io, format="ogg", codec="libopus")
        ogg_io.seek(0)
        ogg_content = ogg_io.read()
        logger.info("Successfully converted audio to OGG format.")

        # Распознавание речи
        text = recognize_speech(
            ogg_content, lang="kk-KK" if user_language == "kk" else "ru-RU"
        )
        logger.info(f"Speech recognition result: {text}")
        return text

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        return None


async def process_audio_and_text(message_data, user_language):
    """
    Обрабатывает аудио и текст из сообщения. Внедрена обработка в фоне.
    """
    tasks = []
    text_result = None

    # Если есть аудио, запускаем фоновую задачу на его обработку
    if "audio" in message_data and message_data["audio"]:
        tasks.append(
            asyncio.create_task(
                process_audio(message_data["audio"], user_language)
            )
        )
    else:
        text_result = message_data.get("text", None)

    # Дожидаемся выполнения задач
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Логируем ошибки и собираем результаты
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Error in background task: {result}")
        else:
            text_result = result

    return text_result
