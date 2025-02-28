import json
import asyncio
import os
from telethon import events, TelegramClient, types
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand
from telethon.tl.custom import Button


class BotHandler:
    def __init__(self, queue_from_bot, queue_to_bot, keys_path="../config/keys.json", subscribed_channels_path="../config/subscribed_channels.json", all_channels_path="../config/all_channels.json"):
        if not os.path.exists(keys_path):
            raise Exception(f"Invalid keys_path: {keys_path} doesn't exist")

        try:
            with open(keys_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.API_ID = config["API_ID"]
            self.API_HASH = config["API_HASH"]
            self.BOT_TOKEN = config["BOT_API_TOKEN"]
            self.SOURCE_USER_ID = config["SOURCE_USER_ID"]
            self.TARGET_USER_ID = config["TARGET_USER_ID"]
        except Exception as e:
            raise Exception(f"Some of keys in {keys_path} seems to be invalid: {e}")

        self.SUBSRIBED_CHANNELS_PATH = subscribed_channels_path
        self.ALL_CHANNELS_PATH = all_channels_path
        self.queue_from_bot = queue_from_bot
        self.queue_to_bot = queue_to_bot
        self.media_groups = {}
        self.channels_per_page = 15
        self.lock = asyncio.Lock()
        self.reload_event = asyncio.Event()
        self.initialize_event = asyncio.Event()
        self.all_channels_buffer = {}
        self.subscribed_channels_buffer = {}


        self.bot_client = TelegramClient("bot_session", self.API_ID, self.API_HASH, system_version='4.16.30-vxCUSTOM')
        self.bot_client.on(events.NewMessage())(self.handle_message)
        self.bot_client.on(events.CallbackQuery())(self.handle_callback_query)


    async def set_bot_commands(self):
        commands = [
            BotCommand(command="add_channel", description="Добавить канал по номеру из списка"),
            BotCommand(command="remove_channel", description="Удалить канал по номеру из списка"),
            BotCommand(command="subscribed_channels", description="Список добавленных каналов"),
            BotCommand(command="all_channels", description="Список всех доступных каналов"),
            BotCommand(command="refresh_channels", description="Обновить список всех доступных каналов")
        ]
        await self.bot_client(
            SetBotCommandsRequest(scope=types.BotCommandScopeDefault(), lang_code='en', commands=commands))

    async def handle_message(self, event):
        if event.message.text and event.message.text.startswith("/"):
            if event.sender_id != self.TARGET_USER_ID:
                await self.bot_client.send_message(event.sender_id, "У вас нет прав на команды")
                return
            await self.handle_command_message(event)
            return

        if event.sender_id != self.SOURCE_USER_ID:
            await self.bot_client.send_message(event.sender_id, "Не присылай мне ничего")
            return

        group_id = getattr(event.message, "grouped_id", None)
        if group_id is None or group_id not in self.media_groups:
            if group_id is not None:
                self.media_groups[group_id] = [event.message.id]
            if event.message.text and event.message.text.startswith("Сообщение из канала:"):
                message_text = event.message.text.replace("Сообщение из канала:", "").strip()
                message_text = "🔁 **" + message_text + "**"
                await self.bot_client.send_message(self.TARGET_USER_ID, message_text)
                await self.queue_from_bot.put("MSG_ACK")
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
            for i in range(len(msg_ids_to_forward)):
                await self.queue_from_bot.put("MSG_ACK")
        else:
            self.media_groups[group_id].append(event.message.id)

    async def handle_command_message(self, event):
        if event.message.text and event.message.text.startswith("/"):
            command_parts = event.message.text.strip().split()
            cmd = command_parts[0].lower()

            if cmd == "/add_channel":
                if len(command_parts) < 2:
                    await self.bot_client.send_message(self.TARGET_USER_ID,
                                                       "Usage: /add_channel <channel_number>")
                    return
                try:
                    channel_number = int(command_parts[1]) - 1
                    if channel_number < 0 or channel_number >= len(self.all_channels_buffer):
                        await self.bot_client.send_message(self.TARGET_USER_ID, "Неверный номер канала.")
                        return
                    channel_to_add = self.all_channels_buffer[channel_number]

                    if any(ch["id"] == channel_to_add["id"] for ch in self.subscribed_channels_buffer):
                        await self.bot_client.send_message(self.TARGET_USER_ID, "Этот канал уже добавлен.")
                    else:
                        self.subscribed_channels_buffer.append(channel_to_add)
                        with open(self.SUBSRIBED_CHANNELS_PATH, "w", encoding="utf-8") as f:
                            json.dump(self.subscribed_channels_buffer, f, indent=4)
                        await self.bot_client.send_message(self.TARGET_USER_ID,
                                                           f"Канал {channel_to_add['name']} добавлен.")
                        await self.queue_from_bot.put("RELOAD_CHANNELS")
                        self.reload_event.clear()
                        await self.reload_event.wait()

                except Exception as e:
                    print(f"🔴BotHandler🔴: handle_command_message {e}")
                    await self.bot_client.send_message(self.TARGET_USER_ID, f"Ошибка: {e}")

            elif cmd == "/remove_channel":
                if len(command_parts) < 2:
                    await self.bot_client.send_message(self.TARGET_USER_ID,
                                                       "Usage: /remove_channel <channel_number>")
                    return
                try:
                    channel_number = int(command_parts[1]) - 1
                    if channel_number < 0 or channel_number >= len(self.subscribed_channels_buffer):
                        await self.bot_client.send_message(self.TARGET_USER_ID, "Неверный номер канала.")
                        return
                    channel_to_remove = self.subscribed_channels_buffer.pop(channel_number)

                    with open(self.SUBSRIBED_CHANNELS_PATH, "w", encoding="utf-8") as f:
                        json.dump(self.subscribed_channels_buffer, f, indent=4)
                    await self.bot_client.send_message(self.TARGET_USER_ID,
                                                       f"Канал {channel_to_remove['name']} удалён.")
                    await self.queue_from_bot.put("RELOAD_CHANNELS")
                    self.reload_event.clear()
                    await self.reload_event.wait()

                except Exception as e:
                    print(f"🔴BotHandler🔴: handle_command_message {e}")
                    await self.bot_client.send_message(self.TARGET_USER_ID, f"Ошибка: {e}")

            elif cmd == "/subscribed_channels":
                try:
                    if self.subscribed_channels_buffer:
                        pages = [self.subscribed_channels_buffer[i:i + self.channels_per_page] for i in
                                 range(0, len(self.subscribed_channels_buffer), self.channels_per_page)]
                        await self.send_page_function(pages, 0, "sub")
                    else:
                        msg = "Нет доступных каналов."
                        await self.bot_client.send_message(self.TARGET_USER_ID, msg)
                except Exception as e:
                    print(f"🔴BotHandler🔴: handle_command_message {e}")
                    await self.bot_client.send_message(self.TARGET_USER_ID, f"Ошибка: {e}")

            elif cmd == "/all_channels":
                try:
                    if self.all_channels_buffer:
                        pages = [self.all_channels_buffer[i:i + self.channels_per_page] for i in
                                 range(0, len(self.all_channels_buffer), self.channels_per_page)]
                        await self.send_page_function(pages, 0, "all")
                    else:
                        msg = "Нет доступных каналов."
                        await self.bot_client.send_message(self.TARGET_USER_ID, msg)
                except Exception as e:
                    print(f"🔴BotHandler🔴: handle_command_message {e}")
                    await self.bot_client.send_message(self.TARGET_USER_ID, f"Ошибка: {e}")

            elif cmd == "/refresh_channels":
                await self.queue_from_bot.put("INITIALIZE_CHANNELS")
                self.initialize_event.clear()
                await self.initialize_event.wait()

                with open(self.ALL_CHANNELS_PATH, "r", encoding="utf-8") as f:
                    self.all_channels_buffer = json.load(f)

                await self.bot_client.send_message(self.TARGET_USER_ID, "Список доступных каналов обновлен")

    async def handle_callback_query(self, event):
        query = event.query
        data = query.data.decode("utf-8")

        if "_" in data:
            list_type, page_str = data.split("_")
            current_page = int(page_str)
        else:
            await event.answer("Некорректный запрос.", alert=True)
            return

        if list_type == "all":
            channels = self.all_channels_buffer
        elif list_type == "sub":
            channels = self.subscribed_channels_buffer
        else:
            await event.answer("Некорректный тип списка.", alert=True)
            return

        pages = [channels[i:i + self.channels_per_page] for i in range(0, len(channels), self.channels_per_page)]

        if current_page < 0:
            current_page = 0
        elif current_page >= len(pages):
            current_page = len(pages) - 1

        await self.send_page_function(pages, current_page, list_type, event.message_id)
        await event.answer()

    async def send_page_function(self, pages, current_page, list_type, message_id=None):
        page = pages[current_page]
        first_index = current_page * self.channels_per_page + 1
        if list_type == "all":
            msg = "**Список доступных каналов**\n"
        elif list_type == "sub":
            msg = "**Список отслеживаемых каналов**\n"
        else:
            msg = "**Неизвестный список**\n"
        msg += "\n".join(f"{first_index + idx}. {ch['name']} (ID: {ch['id']})" for idx, ch in enumerate(page))

        keyboard = []

        if current_page > 0:
            keyboard.append(Button.inline("⬅️", data=f"{list_type}_{current_page - 1}"))
        if current_page < len(pages) - 1:
            keyboard.append(Button.inline("➡️", data=f"{list_type}_{current_page + 1}"))

        if len(keyboard) == 0:
            keyboard = None

        if message_id:
            await self.bot_client.edit_message(self.TARGET_USER_ID, message_id, msg, buttons=keyboard)
        else:
            await self.bot_client.send_message(self.TARGET_USER_ID, msg, buttons=keyboard)

    async def start(self):
        await self.bot_client.start(bot_token=self.BOT_TOKEN)
        await self.set_bot_commands()

        with open(self.ALL_CHANNELS_PATH, "r", encoding="utf-8") as f:
            self.all_channels_buffer = json.load(f)
        with open(self.SUBSRIBED_CHANNELS_PATH, "r", encoding="utf-8") as f:
            self.subscribed_channels_buffer = json.load(f)

        print("🔴BotHandler🔴: Бот-клиент запущен.")

    async def run_until_disconnected(self):
        await asyncio.gather(
            self.bot_client.run_until_disconnected(),
            self.listen_for_signals()
        )

    async def listen_for_signals(self):
        while True:
            signal = await self.queue_to_bot.get()
            if signal == "RELOAD_ACK":
                self.reload_event.set()
            elif signal == "INITIALIZE_ACK":
                self.initialize_event.set()
