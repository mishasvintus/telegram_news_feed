import asyncio
import json
from telethon import events, TelegramClient

class UserHandler:
    def __init__(self, event_queue, config_path="../config/keys.json", channels_path="../config/channels.json"):
        self.event_queue = event_queue
        # Словарь для накопления id сообщений по grouped_id
        self.media_groups = {}

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
        group_id = getattr(event.message, "grouped_id", None)
        if group_id is None or group_id not in self.media_groups:
            async with self.lock:
                print("заблокировался")
                if group_id is not None and group_id not in self.media_groups:
                    self.media_groups[group_id] = [event.message.id]
                print("🔷UserHandler🔷: Получено сообщение из канала.")
                try:
                    channel_name = event.chat.title if event.chat else "Неизвестный канал"
                    info_text = f"Сообщение из канала: 🔁 {channel_name}"
                    channel_info_msg = await self.user_client.send_message(self.BOT_USERNAME, info_text)
                    print(f"🔷UserHandler🔷: Информация о канале {channel_name} отправлена боту.")
                    await self.event_queue.get()
                    await self.user_client.delete_messages(self.BOT_USERNAME, [channel_info_msg.id], revoke=True)

                    if group_id is not None:
                        await asyncio.sleep(0.5)
                        msg_ids_to_forward = self.media_groups.pop(group_id, [])
                    else:
                        msg_ids_to_forward = [event.message.id]

                    forwarded_msgs = await self.user_client.forward_messages(
                        self.BOT_USERNAME,
                        msg_ids_to_forward,
                        from_peer=event.chat
                    )
                    msg_ids_to_delete = [msg.id for msg in forwarded_msgs]

                    for i in range(len(msg_ids_to_forward)):
                        await self.event_queue.get()

                    await self.user_client.delete_messages(self.BOT_USERNAME, msg_ids_to_delete, revoke=True)

                    print(f"🔷UserHandler🔷: Сообщение из канала {channel_name} переслано боту.")
                except Exception as e:
                    print("🔷UserHandler🔷: Ошибка при обработке сообщения:", e)
        else:
            self.media_groups[group_id].append(event.message.id)
            print(f"🔷UserHandler🔷: Сообщение с group_id {group_id} аккумулировано, обработка завершена.")

    async def start(self):
        await self.user_client.start()
        print("🔷UserHandler🔷: Пользовательский клиент запущен.")

    async def start_and_wait(self):
        await self.start()
        await self.user_client.run_until_disconnected()
