import asyncio
import json
import os
from telethon import events, TelegramClient
from telethon.tl.types import UserStatusOnline
import datetime


class UserHandler:
    def __init__(self, queue_from_bot, queue_to_bot, keys_path="../config/keys.json",
                 subscribed_channels_path="../config/subscribed_channels.json",
                 all_channels_path="../config/all_channels.json"):
        if not os.path.exists(keys_path):
            raise Exception(f"Invalid keys_path: {keys_path} doesn't exist")

        try:
            with open(keys_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.API_ID = config["API_ID"]
            self.API_HASH = config["API_HASH"]
            self.BOT_USERNAME = config["BOT_USERNAME"]
            self.SOURCE_USER_ID = config["SOURCE_USER_ID"]
            self.TARGET_USER_ID = config["TARGET_USER_ID"]
        except Exception as e:
            raise Exception(f"Some of keys in {keys_path} seems to be invalid: {e}")

        self.SUBSRIBED_CHANNELS_PATH = subscribed_channels_path
        self.ALL_CHANNELS_PATH = all_channels_path

        self.queue_from_bot = queue_from_bot
        self.queue_to_bot = queue_to_bot
        self.media_groups = {}
        self.channel_ids = []
        self.lock = asyncio.Lock()
        self.ack_counter = 0
        self.ack_counter_aim = 0
        self.ack_event = asyncio.Event()
        self.user_client = TelegramClient("user_session", self.API_ID, self.API_HASH, system_version='4.16.30-vxCUSTOM')
        self.unread_queue = asyncio.Queue()

        self.user_client.on(events.UserUpdate(chats=self.SOURCE_USER_ID))(self.handle_user_update)

    async def handle_channel_message(self, event):
        group_id = getattr(event.message, "grouped_id", None)

        if group_id is not None and group_id in self.media_groups:
            self.media_groups[group_id].append(event.message)
            return

        async with self.lock:
            if group_id is not None:
                self.media_groups[group_id] = [event.message]
                await asyncio.sleep(0.5)
                msgs_to_forward = self.media_groups.pop(group_id, [])
            else:
                msgs_to_forward = [event.message]

            status = (await self.user_client.get_me()).status
            if isinstance(status, UserStatusOnline):
                await self.new_post_transmission(event.chat, msgs_to_forward)
            else:
                await self.unread_queue.put((event.chat, msgs_to_forward))

    async def handle_user_update(self, event):
        if isinstance(event.status, UserStatusOnline):
            while not self.unread_queue.empty():
                chat, msgs_to_forward = await self.unread_queue.get()
                await self.new_post_transmission(chat, msgs_to_forward)

    async def new_post_transmission(self, chat, msgs_to_forward):
        try:
            await self.user_client.send_read_acknowledge(chat.id, msgs_to_forward)
            msg_date = msgs_to_forward[0].date + datetime.timedelta(hours=3)
            await self.send_channel_info_msg(chat, msg_date)
            await self.forward_messages(chat, msgs_to_forward)
        except Exception as e:
            print(f"{datetime.datetime.now()}\n🔷UserHandler🔷: new_post_transmission {e}")

    async def send_channel_info_msg(self, chat, msg_date):
        channel_name = chat.title if chat else "Неизвестный канал"

        info_text = f"Сообщение из канала:**{channel_name}**\n {msg_date.strftime("%H:%M")}"

        self.prepare_wait_ack(acks_to_wake=1)
        try:
            channel_info_msg = await self.user_client.send_message(self.BOT_USERNAME, info_text, background=True)
        except Exception as e:
            raise Exception(f'🔷UserHandler🔷: send_channel_info_msg "{info_text}": {e}')

        await self.wait_ack()
        await self.user_client.delete_messages(self.BOT_USERNAME, [channel_info_msg.id])

    async def forward_messages(self, chat, msgs_to_forward):
        self.prepare_wait_ack(acks_to_wake=len(msgs_to_forward))
        try:
            forwarded_msgs = await self.user_client.forward_messages(
                self.BOT_USERNAME,
                msgs_to_forward,
                from_peer=chat,
                background=True
            )
            if all(msg is None for msg in forwarded_msgs):
                raise Exception("🔷UserHandler🔷: отправленные сообщения были удалены")
        except Exception as e:
            await self.queue_to_bot.put("DELETE_CHANNEL_INFO_MSG")
            raise Exception(
                f"🔷UserHandler🔷: error while forwarding msgs with ids {msgs_to_forward}, "
                f"from '{chat.title}' with id: {chat.id}: {e}"
            )
        await self.wait_ack()
        msg_ids_to_delete = [msg.id for msg in forwarded_msgs]
        await self.user_client.delete_messages(self.BOT_USERNAME, msg_ids_to_delete)

    def prepare_wait_ack(self, acks_to_wake=0):
        self.ack_counter = 0
        self.ack_counter_aim = acks_to_wake
        self.ack_event.clear()

    async def wait_ack(self):
        await self.ack_event.wait()

    def reload_subscribed_channels(self):
        if not os.path.exists(self.SUBSRIBED_CHANNELS_PATH):
            with open(self.SUBSRIBED_CHANNELS_PATH, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=4)

        with open(self.SUBSRIBED_CHANNELS_PATH, "r", encoding="utf-8") as f:
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

        with open(self.ALL_CHANNELS_PATH, "w", encoding="utf-8") as f:
            json.dump(formatted_channels, f, ensure_ascii=False, indent=4)

    async def start(self):
        await self.user_client.start()
        await self.initialize_all_channels()
        self.reload_subscribed_channels()
        print(f"{datetime.datetime.now()}\n🔷UserHandler🔷: Пользовательский клиент запущен.")

    async def run_until_disconnected(self):
        await asyncio.gather(
            self.user_client.run_until_disconnected(),
            self.listen_for_signals()
        )

    async def listen_for_signals(self):
        while True:
            signal = await self.queue_from_bot.get()
            if signal == "RELOAD_CHANNELS":
                self.reload_subscribed_channels()
                await self.queue_to_bot.put("RELOAD_ACK")
            elif signal == "INITIALIZE_CHANNELS":
                await self.initialize_all_channels()
                await self.queue_to_bot.put("INITIALIZE_ACK")
            elif signal == "MSG_ACK":
                self.ack_counter += 1
                if self.ack_counter >= self.ack_counter_aim:
                    self.ack_event.set()
