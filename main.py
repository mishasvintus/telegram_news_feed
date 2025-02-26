import json
import asyncio
from telethon import TelegramClient, events


async def main():
    with open("keys.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    API_ID = config["API_ID"]
    API_HASH = config["API_HASH"]
    BOT_TOKEN = config["BOT_API_TOKEN"]
    TARGET_USER_ID = config["TARGET_USER_ID"]
    BOT_USERNAME = config["BOT_USERNAME"]

    with open("all_channels.json", "r", encoding="utf-8") as f:
        channels_config = json.load(f)
    channel_ids = [channel["id"] for channel in channels_config]

    user_client = TelegramClient("user_session", API_ID, API_HASH)
    bot_client = TelegramClient("bot_session", API_ID, API_HASH)

    # Мьютекс для блокировки в handle_channel_message
    lock = asyncio.Lock()

    processed_group_ids = set()

    @user_client.on(events.NewMessage(chats=channel_ids))
    async def handle_channel_message(event):
        async with lock:
            print("Пользовательский клиент: получено сообщение из канала.")
            try:
                nonlocal BOT_USERNAME

                if not BOT_USERNAME:
                    me = await bot_client.get_me()
                    BOT_USERNAME = me.username
                    print("Получен username бота:", BOT_USERNAME)

                # Сначала отправляем информацию о канале
                channel_name = event.chat.title if event.chat else "Неизвестный канал"
                message_text = f"Сообщение из канала: 🔁 {channel_name}"
                channel_info_msg = await user_client.send_message(BOT_USERNAME, message_text)
                print(f"Информация о канале {channel_name} отправлена боту.")

                # Теперь пересылаем само сообщение
                forwarded_msg = await user_client.forward_messages(BOT_USERNAME, event.message)
                print(f"Сообщение из канала {channel_name} переслано боту.")

                # Если пересланных сообщений несколько, собираем их id
                if isinstance(forwarded_msg, list):
                    msg_ids = [msg.id for msg in forwarded_msg]
                else:
                    msg_ids = [forwarded_msg.id]

                msg_ids.append(channel_info_msg.id)

                # Удаляем пересланное сообщение из чата с ботом (в вашем аккаунте)
                await asyncio.sleep(0.5)
                await user_client.delete_messages(BOT_USERNAME, msg_ids, revoke=True)
                print("Пересланное сообщение удалено из вашего аккаунта.")
            except Exception as e:
                print("Ошибка при пересылке сообщения боту:", e)

    @bot_client.on(events.NewMessage)
    async def handle_bot_message(event):
        print("Бот: получено сообщение.")
        try:
            # Если сообщение начинается с "Сообщение из канала:", не пересылаем его, а просто отправляем текст
            if event.message.text.startswith("Сообщение из канала:"):
                # Отправляем только текст, без пересылки сообщения
                message_text = event.message.text.replace("Сообщение из канала:", "").strip()
                await bot_client.send_message(TARGET_USER_ID, message_text)
                print(f"Отправлен текст сообщения: {message_text}")
            else:
                # Если это не сообщение о канале, пересылаем его как обычно
                await bot_client.forward_messages(TARGET_USER_ID, event.message)
                print("Бот переслал сообщение вам.")
        except Exception as e:
            print("Ошибка при пересылке сообщения вам:", e)

    await user_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Клиенты запущены.")

    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )


if __name__ == '__main__':
    asyncio.run(main())
