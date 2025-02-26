import json
import asyncio
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
        # Словарь для аккумулирования id сообщений по grouped_id
        self.media_groups = {}

        # Регистрируем обработчик сообщений
        self.bot_client.on(events.NewMessage())(self.handle_bot_message)

    async def handle_bot_message(self, event):
        group_id = getattr(event.message, "grouped_id", None)

        if group_id is None or group_id not in self.media_groups:
            if group_id is not None:
                self.media_groups[group_id] = [event.message.id]

            if event.message.text and event.message.text.startswith("Сообщение из канала:"):
                message_text = event.message.text.replace("Сообщение из канала:", "").strip()
                await self.bot_client.send_message(self.TARGET_USER_ID, message_text)
                await self.event_queue.put("ACK")
                return

            if group_id is not None:
                await asyncio.sleep(0.5)
                msg_ids_to_forward = self.media_groups.pop(group_id, [])
            else:
                msg_ids_to_forward = [event.message.id]

            await self.bot_client.forward_messages(
                self.TARGET_USER_ID,
                msg_ids_to_forward,
                from_peer=event.chat
            )

            print("🔴BotHandler🔴: Сообщение переслано пользователю.")
            for i in range(len(msg_ids_to_forward)):
                await self.event_queue.put("ACK")
        else:
            self.media_groups[group_id].append(event.message.id)
            print(f"🔴BotHandler🔴: Сообщение с group_id {group_id} аккумулировано, обработка завершена.")

    async def start(self):
        await self.bot_client.start(bot_token=self.BOT_TOKEN)
        print("🔴BotHandler🔴: Бот-клиент запущен.")

    async def start_and_wait(self):
        await self.start()
        await self.bot_client.run_until_disconnected()
