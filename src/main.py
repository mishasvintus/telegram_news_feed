import asyncio
from user_handler import UserHandler
from bot_handler import BotHandler

async def main():
    queue_from_bot = asyncio.Queue()
    queue_to_bot = asyncio.Queue()

    user_handler = UserHandler(queue_from_bot, queue_to_bot)
    bot_handler = BotHandler(queue_from_bot, queue_to_bot)

    # Запускаем обработчики
    await asyncio.gather(
        user_handler.start_and_wait(),
        bot_handler.start_and_wait()
    )

if __name__ == "__main__":
    asyncio.run(main())
