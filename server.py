import asyncio
import httpx
import websockets
import json
from crud import Postgres
from handlers.process_message import (
    process_user_message,
    register_user_if_not_exists,
)
from services.create_realtime_session import create_realtime_session
from services.survey_service import update_survey_data_live_barsik
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
        url = "https://backoffice.daribar.com/api/v1/users"
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
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                token = data.get("token")
                user_data = None

                # Обработка токена
                if token:
                    try:
                        user_data = await asyncio.create_task(
                            verify_token_with_auth_server(token)
                        )
                    except Exception as token_error:
                        logger.error(f"Error verifying token: {token_error}")
                        response = {
                            "type": "response",
                            "status": "error",
                            "error": "token_verification_error",
                            "message": "Failed to verify authentication token.",
                        }
                        await websocket.send(
                            json.dumps(response, ensure_ascii=False)
                        )
                        continue

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
                    await websocket.send(
                        json.dumps(response, ensure_ascii=False)
                    )
                    continue

                # Проверяем наличие user_data
                if user_data:
                    user_id = user_data["result"]["phone"]
                    action = data.get("action")
                    message_type = data.get("type")
                else:
                    response = {
                        "type": "response",
                        "status": "error",
                        "error": "missing_user_data",
                        "message": "User data not available. Cannot extract user_id.",
                    }
                    await websocket.send(
                        json.dumps(response, ensure_ascii=False)
                    )
                    continue

                # if action == "initial_chat":
                #     response = await handle_command(action, user_id, db)
                #     await websocket.send(json.dumps(response, ensure_ascii=False))

                if action == "initial_voice_chat":
                    try:
                        asyncio.create_task(  # noqa
                            register_user_if_not_exists(db, user_id)  # noqa
                        )  # noqa
                        response = await create_realtime_session()
                        # Извлекаем client_secret
                        client_secret = response.get("client_secret")

                        # Формируем ответ в нужном формате
                        response_data = {
                            "type": "system",
                            "status": "success",
                            "action": "initial_voice_chat",
                            "data": {
                                "client_secret": {
                                    "value": client_secret.get("value"),
                                    "expires_at": client_secret.get(
                                        "expires_at"
                                    ),
                                }
                            },
                        }

                        await websocket.send(
                            json.dumps(response_data, ensure_ascii=False)
                        )

                    except Exception as command_error:
                        logger.error(
                            f"Error handling command 'initial_voice_chat': {command_error}"
                        )
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "response",
                                    "status": "error",
                                    "error": "command_error",
                                    "message": "Failed to process the 'initial_voice_chat' command.",
                                },
                                ensure_ascii=False,
                            )
                        )
                        continue

                if action == "save_voice_chat_results":
                    try:
                        message_data = data.get("data", {}).get("json", {})
                        # Корректируем только строковые значения в словаре
                        message_data_fixed = {
                            key: (
                                ftfy.fix_text(value)
                                if isinstance(value, str)
                                else str(value)
                            )
                            for key, value in message_data.items()
                        }
                        logger.info(
                            f"message_data_save_voice_chat_results: {message_data_fixed}"
                        )
                        asyncio.create_task(  # noqa
                            register_user_if_not_exists(db, user_id)  # noqa
                        )  # noqa

                        await update_survey_data_live_barsik(
                            db, user_id, message_data_fixed
                        )
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "response",
                                    "status": "success",
                                    "action": "save_voice_chat_results",
                                },
                                ensure_ascii=False,
                            )
                        )

                    except Exception as command_error:
                        logger.error(
                            f"Error handling command 'save_voice_chat_results': {command_error}"
                        )
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "response",
                                    "status": "error",
                                    "error": "command_error",
                                    "message": "Failed to process the 'save_voice_chat_results' command.",
                                },
                                ensure_ascii=False,
                            )
                        )
                        continue

                # Обработка команды export_stats
                if action == "export_stats":
                    try:
                        response = await handle_command(action, user_id, db)
                        await websocket.send(
                            json.dumps(response, ensure_ascii=False)
                        )
                    except Exception as command_error:
                        logger.error(
                            f"Error handling command 'export_stats': {command_error}"
                        )
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "response",
                                    "status": "error",
                                    "error": "command_error",
                                    "message": "Failed to process the 'export_stats' command.",
                                },
                                ensure_ascii=False,
                            )
                        )
                        continue

                # Обработка сообщений
                if message_type == "message" or (
                    message_type == "command"
                    and action == "all_in_one_message"
                ):
                    try:
                        message_data = data.get("data", {})
                        message_data["action"] = action

                        if "text" in message_data:
                            fixed_text = ftfy.fix_text(message_data["text"])
                            message_data["text"] = fixed_text

                        response = await process_user_message(
                            user_id, message_data, db
                        )
                        await websocket.send(
                            json.dumps(response, ensure_ascii=False)
                        )
                        logger.info(f"Response_sent: {response}")
                    except Exception as message_error:
                        logger.error(
                            f"Error processing user message: {message_error}"
                        )
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "response",
                                    "status": "error",
                                    "error": "message_processing_error",
                                    "message": "Failed to process the user message.",
                                },
                                ensure_ascii=False,
                            )
                        )
            except websockets.exceptions.ConnectionClosedError as e:
                logger.warning(f"Connection closed unexpectedly: {e}")
                break
            except Exception as message_processing_error:
                logger.error(
                    f"Error processing message: {message_processing_error}"
                )
                await websocket.send(
                    json.dumps(
                        {
                            "type": "response",
                            "status": "error",
                            "error": "message_error",
                            "message": str(message_processing_error),
                        },
                        ensure_ascii=False,
                    )
                )
    except websockets.exceptions.ConnectionClosedError as e:
        logger.warning(f"WebSocket connection closed unexpectedly: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket handler: {e}")
    finally:
        logger.info("WebSocket connection handler finished.")


async def main():
    try:
        # Увеличиваем время ожидания пинга (интервал и тайм-аут)
        server = await websockets.serve(
            handle_connection,
            "0.0.0.0",
            8083,
            ping_interval=60,  # Интервал между пингами (в секундах)
            ping_timeout=30,  # Время ожидания ответа на пинг (в секундах)
        )
        print("WebSocket server started on ws://0.0.0.0:8083")
        await server.wait_closed()
    except Exception as e:
        logger.error(f"Error starting WebSocket server: {e}")


if __name__ == "__main__":
    asyncio.run(main())
