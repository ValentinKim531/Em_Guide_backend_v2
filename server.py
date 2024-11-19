import asyncio
import httpx
import websockets
import json
from crud import Postgres
from handlers.process_message import process_user_message
from models import User
from utils.logging_config import get_logger
from services.database import async_session
import ftfy

from services.statistics_service import generate_statistics_file
from utils.redis_client import (
    save_registration_status,
    delete_user_dialogue_history,
)

db = Postgres(async_session)


logger = get_logger(name="server")


async def verify_token_with_auth_server(token):
    """
    Проверка токена через внешний сервис аутентификации.
    """
    try:
        url = "https://prod-backoffice.daribar.com/api/v1/users"
        headers = {"Authorization": f"Bearer {token}"}
        logger.info(f"Token: {token}")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                logger.info(f"responseJWT: {response.json()}")
                return response.json()  # Возвращаем данные пользователя
            else:
                logger.error(
                    f"Error: {response.status_code} - {response.text}"
                )
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
            user_data = None
            if token:
                task = asyncio.create_task(
                    verify_token_with_auth_server(token)
                )
                user_data = await task

                if not user_data:
                    response = {
                        "type": "response",
                        "status": "error",
                        "error": "invalid_token",
                        "message": "Invalid or expired JWT token. Please re-authenticate.",
                    }
                    await websocket.send(
                        json.dumps(response, ensure_ascii=False)
                    )
                    continue
            else:
                logger.warning("Token not provided in the request.")
                response = {
                    "type": "response",
                    "status": "error",
                    "error": "missing_token",
                    "message": "Authentication token is required but was not provided.",
                }
                await websocket.send(json.dumps(response, ensure_ascii=False))

            # Проверяем наличие user_data перед извлечением user_id
            if user_data:
                user_id = user_data["result"]["phone"]
                action = data.get("action")
                type = data.get("type")
            else:
                # Отправляем сообщение об ошибке, если user_data отсутствует
                response = {
                    "type": "response",
                    "status": "error",
                    "error": "missing_user_data",
                    "message": "User data not available. Cannot extract user_id.",
                }
                await websocket.send(json.dumps(response, ensure_ascii=False))

            # if action == "initial_chat":
            #     response = await handle_command(action, user_id, db)
            #     await websocket.send(json.dumps(response, ensure_ascii=False))
            if action == "export_stats":
                response = await handle_command(action, user_id, db)
                await websocket.send(json.dumps(response, ensure_ascii=False))

            # Обработка сообщений (например, ответы на вопросы опроса)
            if type == "message" or (
                type == "command" and action == "all_in_one_message"
            ):
                message_data = data.get("data")
                message_data["action"] = data.get("action")

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
        # Увеличиваем время ожидания пинга (интервал и тайм-аут)
        server = await websockets.serve(
            handle_connection,
            "0.0.0.0",
            8083,
            ping_interval=30,  # Интервал между пингами (в секундах)
            ping_timeout=20,  # Время ожидания ответа на пинг (в секундах)
        )
        print("WebSocket server started on ws://0.0.0.0:8083")
        await server.wait_closed()
    except Exception as e:
        logger.error(f"Error starting WebSocket server: {e}")


if __name__ == "__main__":
    asyncio.run(main())
