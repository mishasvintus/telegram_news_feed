import asyncio
from user_handler import UserHandler
from bot_handler import BotHandler

async def main():
    event_queue = asyncio.Queue()

    user_handler = UserHandler(event_queue)
    bot_handler = BotHandler(event_queue)

    # Запускаем обработчики
    await asyncio.gather(
        user_handler.start_and_wait(),
        bot_handler.start_and_wait()
    )

if __name__ == "__main__":
    asyncio.run(main())
