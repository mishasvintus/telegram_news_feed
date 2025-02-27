import asyncio
import json
from telethon import events, TelegramClient

class UserHandler:
    def __init__(self, queue_from_bot, queue_to_bot, config_path="../config/keys.json", channels_path="../config/channels.json"):
        self.queue_from_bot = queue_from_bot
        self.queue_to_bot = queue_to_bot
        self.media_groups = {}

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.API_ID = config["API_ID"]
        self.API_HASH = config["API_HASH"]
        self.BOT_USERNAME = config["BOT_USERNAME"]

        with open(channels_path, "r", encoding="utf-8") as f:
            channels_config = json.load(f)
        self.channel_ids = [channel["id"] for channel in channels_config]

        self.user_client = TelegramClient("user_session", self.API_ID, self.API_HASH, system_version='4.16.30-vxCUSTOM')
        self.lock = asyncio.Lock()
        self.ack_counter = 0
        self.ack_counter_aim = 0
        self.ack_event = asyncio.Event()

        self.user_client.on(events.NewMessage(chats=self.channel_ids))(self.handle_channel_message)

    async def handle_channel_message(self, event):
        await self.user_client.send_read_acknowledge(event.chat_id, event.message)
        group_id = getattr(event.message, "grouped_id", None)

        if group_id is None or group_id not in self.media_groups:
            async with self.lock:
                if group_id is not None and group_id not in self.media_groups:
                    self.media_groups[group_id] = [event.message.id]
                try:
                    channel_name = event.chat.title if event.chat else "Неизвестный канал"
                    info_text = f"Сообщение из канала: 🔁 {channel_name}"

                    self.prepare_wait_ack(acks_to_wake=1)
                    channel_info_msg = await self.user_client.send_message(self.BOT_USERNAME, info_text)
                    await self.wait_ack()

                    await self.user_client.delete_messages(self.BOT_USERNAME, [channel_info_msg.id], revoke=True)

                    if group_id is not None:
                        await asyncio.sleep(0.5)
                        msg_ids_to_forward = self.media_groups.pop(group_id, [])
                    else:
                        msg_ids_to_forward = [event.message.id]

                    self.prepare_wait_ack(acks_to_wake=len(msg_ids_to_forward))
                    forwarded_msgs = await self.user_client.forward_messages(
                        self.BOT_USERNAME,
                        msg_ids_to_forward,
                        from_peer=event.chat
                    )
                    await self.wait_ack()

                    msg_ids_to_delete = [msg.id for msg in forwarded_msgs]
                    await self.user_client.delete_messages(self.BOT_USERNAME, msg_ids_to_delete, revoke=True)

                except Exception as e:
                    print(f"🔷UserHandler🔷: {e}")
        else:
            self.media_groups[group_id].append(event.message.id)

    def prepare_wait_ack(self, acks_to_wake=0):
        self.ack_counter = 0
        self.ack_counter_aim = acks_to_wake
        self.ack_event.clear()

    async def wait_ack(self):
        await self.ack_event.wait()

    async def reload_channels(self):
        with open("../config/channels.json", "r", encoding="utf-8") as f:
            channels_config = json.load(f)
        self.channel_ids = [channel["id"] for channel in channels_config]

        self.user_client.remove_event_handler(self.handle_channel_message)
        self.user_client.on(events.NewMessage(chats=self.channel_ids))(self.handle_channel_message)

    async def initialize_all_channels(self):
        channels = dict()
        dialogs = await self.user_client.get_dialogs()
        for chat in dialogs:
            if chat.is_channel:
                channels[chat.title] = chat.id

        formatted_channels = [{"name": key, "id": value} for key, value in channels.items()]

        with open("../config/all_channels.json", "w", encoding="utf-8") as f:
            json.dump(formatted_channels, f, ensure_ascii=False, indent=4)

    async def start(self):
        await self.user_client.start()
        await self.initialize_all_channels()
        print("🔷UserHandler🔷: Пользовательский клиент запущен.")

    async def start_and_wait(self):
        await self.start()
        await asyncio.gather(
            self.user_client.run_until_disconnected(),
            self.listen_for_signals()
        )

    async def listen_for_signals(self):
        while True:
            signal = await self.queue_from_bot.get()
            if signal == "RELOAD_CHANNELS":
                await self.reload_channels()
                await self.queue_to_bot.put("RELOAD_ACK")
            elif signal == "INITIALIZE_CHANNELS":
                await self.initialize_all_channels()
                await self.queue_to_bot.put("INITIALIZE_ACK")
            elif signal == "MSG_ACK":
                self.ack_counter += 1
                if self.ack_counter >= self.ack_counter_aim:
                    self.ack_event.set()
                    self.ack_counter = 0
                    self.ack_counter_aim = 0