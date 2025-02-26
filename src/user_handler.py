import asyncio
import json
from telethon import events, TelegramClient

class UserHandler:
    def __init__(self, config_path="../config/keys.json", channels_path="../config/all_channels.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.API_ID = config["API_ID"]
        self.API_HASH = config["API_HASH"]
        self.BOT_USERNAME = config["BOT_USERNAME"]

        with open(channels_path, "r", encoding="utf-8") as f:
            channels_config = json.load(f)

        self.channel_ids = [channel["id"] for channel in channels_config]

        self.user_client = TelegramClient("user_session", self.API_ID, self.API_HASH)
        self.lock = asyncio.Lock()

        self.user_client.on(events.NewMessage(chats=self.channel_ids))(self.handle_channel_message)

    async def handle_channel_message(self, event):
        async with self.lock:
            print("Пользовательский клиент: получено сообщение из канала.")
            try:
                # Сначала отправляем информацию о канале
                channel_name = event.chat.title if event.chat else "Неизвестный канал"
                message_text = f"Сообщение из канала: 🔁 {channel_name}"
                channel_info_msg = await self.user_client.send_message(self.BOT_USERNAME, message_text)
                print(f"Информация о канале {channel_name} отправлена боту.")

                # Теперь пересылаем само сообщение
                forwarded_msg = await self.user_client.forward_messages(self.BOT_USERNAME, event.message)
                print(f"Сообщение из канала {channel_name} переслано боту.")

                # Если пересланных сообщений несколько, собираем их id
                if isinstance(forwarded_msg, list):
                    msg_ids = [msg.id for msg in forwarded_msg]
                else:
                    msg_ids = [forwarded_msg.id]

                msg_ids.append(channel_info_msg.id)

                # Удаляем пересланное сообщение из чата с ботом (в вашем аккаунте)
                await asyncio.sleep(0.5)
                await self.user_client.delete_messages(self.BOT_USERNAME, msg_ids, revoke=True)
                print("Пересланное сообщение удалено из вашего аккаунта.")
            except Exception as e:
                print("Ошибка при пересылке сообщения боту:", e)

    async def start(self):
        await self.user_client.start()
        print("Пользовательский клиент запущен.")

    async def start_and_wait(self):
        await self.start()
        await self.user_client.run_until_disconnected()