import json
from telethon import events, TelegramClient

class BotHandler:
    def __init__(self, event_queue, config_path="../config/keys.json"):
        self.event_queue = event_queue

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.API_ID = config["API_ID"]
        self.API_HASH = config["API_HASH"]
        self.BOT_TOKEN = config["BOT_API_TOKEN"]
        self.TARGET_USER_ID = config["TARGET_USER_ID"]

        self.bot_client = TelegramClient("bot_session", self.API_ID, self.API_HASH)

        # Регистрируем обработчик сообщений
        self.bot_client.on(events.NewMessage())(self.handle_bot_message)

    async def handle_bot_message(self, event):
        print("🔴BotHandler🔴: Получено сообщение.")
        try:
            if event.message.text.startswith("Сообщение из канала:"):
                message_text = event.message.text.replace("Сообщение из канала:", "").strip()
                await self.bot_client.send_message(self.TARGET_USER_ID, message_text)
                print(f"🔴BotHandler🔴: Отправлен текст сообщения: {message_text}")
            else:
                await self.bot_client.forward_messages(self.TARGET_USER_ID, event.message)
                print("🔴BotHandler🔴: Бот переслал сообщение вам.")
            await self.event_queue.put("ACK")
        except Exception as e:
            print("🔴BotHandler🔴: Ошибка при пересылке сообщения вам:", e)

    async def start(self):
        await self.bot_client.start(bot_token=self.BOT_TOKEN)
        print("🔴BotHandler🔴: Бот-клиент запущен.")

    async def start_and_wait(self):
        await self.start()
        await self.bot_client.run_until_disconnected()