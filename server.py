import asyncio
import httpx
import websockets
import json
from crud import Postgres
from handlers.process_message import process_user_message
from models import User
import logging
from services.database import async_session
import ftfy

from services.statistics_service import generate_statistics_file
from utils.redis_client import (
    save_registration_status,
    delete_user_dialogue_history,
)

db = Postgres(async_session)
logger = logging.getLogger(__name__)


async def verify_token_with_auth_server(token):
    """
    Проверка токена через внешний сервис аутентификации.
    """
    try:
        url = "https://backoffice.daribar.com/api/v1/users"
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()  # Возвращаем данные пользователя
            else:
                return None
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None


async def handle_command(action, user_id, database: Postgres):
    """
    Обрабатывает команду, связанную с инициализацией чата или другими действиями.
    """
    # if action == "initial_chat":
    #     try:
    #         await delete_user_dialogue_history(user_id)
    #
    #         user = await database.get_entity_parameter(
    #             User, {"userid": user_id}
    #         )
    #
    #         if user:
    #             is_registration = False
    #         else:
    #             is_registration = True
    #
    #         # Сохранить статус регистрации в Redis
    #         await save_registration_status(user_id, is_registration)
    #
    #         return {
    #             "type": "response",
    #             "status": "success",
    #             "action": "initial_chat",
    #             "data": {
    #                 "is_registration": is_registration,
    #             },
    #         }
    #
    #     except Exception as e:
    #         logger.error(f"Error processing initial chat: {e}")
    #         return {
    #             "type": "response",
    #             "status": "error",
    #             "error": "server_error",
    #             "message": "An internal server error occurred.",
    #         }
    if action == "export_stats":
        try:
            stats = await generate_statistics_file(user_id, database)
            if not stats:
                return {
                    "type": "response",
                    "status": "error",
                    "action": "export_stats",
                    "error": "no_stats",
                    "message": "No stats available.",
                }
            return {
                "type": "response",
                "status": "success",
                "action": "export_stats",
                "data": {"file_json": stats},
            }
        except Exception as e:
            logger.error(f"Error generating export stats: {e}")
            return {
                "type": "response",
                "status": "error",
                "action": "export_stats",
                "error": "server_error",
                "message": "An internal server error occurred. Please try again later.",
            }


async def handle_connection(websocket, path):
    """
    Основная логика обработки сообщений по WebSocket.
    """
    async for message in websocket:
        try:
            data = json.loads(message)
            token = data.get("token")

            # Проверяем токен через внешний сервис аутентификации
            user_data = await verify_token_with_auth_server(token)
            if not user_data:
                response = {
                    "type": "response",
                    "status": "error",
                    "error": "invalid_token",
                    "message": "Invalid or expired JWT token. Please re-authenticate.",
                }
                await websocket.send(json.dumps(response, ensure_ascii=False))
                continue

            user_id = user_data["result"]["phone"]
            action = data.get("action")
            type = data.get("type")

            # if action == "initial_chat":
            #     response = await handle_command(action, user_id, db)
            #     await websocket.send(json.dumps(response, ensure_ascii=False))
            if action == "export_stats":
                response = await handle_command(action, user_id, db)
                await websocket.send(json.dumps(response, ensure_ascii=False))

            # Обработка сообщений (например, ответы на вопросы опроса)
            if type == "message":
                message_data = data.get("data")
                if "text" in message_data:
                    fixed_text = ftfy.fix_text(message_data["text"])
                    message_data["text"] = fixed_text

                response = await process_user_message(
                    user_id, message_data, db
                )
                await websocket.send(json.dumps(response, ensure_ascii=False))

        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"Connection closed unexpectedly: {e}")
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
            try:
                await websocket.send(
                    json.dumps(
                        {
                            "type": "response",
                            "status": "error",
                            "error": "server_error",
                            "message": str(e),
                        },
                        ensure_ascii=False,
                    )
                )
            except websockets.exceptions.ConnectionClosedError:
                logger.warning(
                    "Tried to send error message, but the connection was already closed."
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")


async def main():
    try:
        server = await websockets.serve(handle_connection, "0.0.0.0", 8083)
        print("WebSocket server started on ws://0.0.0.0:8083")
        await server.wait_closed()
    except Exception as e:
        logger.error(f"Error starting WebSocket server: {e}")


if __name__ == "__main__":
    asyncio.run(main())
