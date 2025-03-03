import httpx
from fastapi import HTTPException
from utils.config import REALTIME_INSTRUCTIONS, OPENAI_API_KEY_REALTIME
from utils.logging_config import get_logger


logger = get_logger(name="realtime_api")

REALTIME_MODEL = "gpt-4o-realtime-preview-2024-12-17"


async def create_realtime_session():
    """
    Создает сессию OpenAI Realtime API с инструкцией для GPT.
    """
    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY_REALTIME}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": REALTIME_MODEL,
        "modalities": ["text", "audio"],
        "instructions": REALTIME_INSTRUCTIONS,
        "voice": "verse",
        "input_audio_transcription": {"model": "whisper-1", "language": "ru"},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        session_data = response.json()
        logger.info(f"Realtime session created: {session_data}")
        return session_data
    else:
        logger.error(f"Error creating realtime session: {response.text}")
        raise HTTPException(
            status_code=response.status_code, detail=response.text
        )
