import asyncio
from user_handler import UserHandler
from bot_handler import BotHandler

async def main():
    # Создаем обработчики
    user_handler = UserHandler()
    bot_handler = BotHandler()

    # Запускаем обработчики
    await asyncio.gather(
        user_handler.start_and_wait(),
        bot_handler.start_and_wait()
    )

if __name__ == "__main__":
    asyncio.run(main())
