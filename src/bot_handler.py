import json
import asyncio
import os
from telethon import events, TelegramClient, types
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand
from telethon.tl.custom import Button
from collections import deque
import datetime


class BotHandler:
    def __init__(self, queue_from_bot, queue_to_bot, keys_path="../config/keys.json",
                 subscribed_channels_path="../config/subscribed_channels.json",
                 all_channels_path="../config/all_channels.json",
                 bot_session_path="../config/bot_session.session"):
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
            self.BOT_USERNAME = config.get("BOT_USERNAME", "")
        except Exception as e:
            raise Exception(
                f"Some of keys in {keys_path} seems to be invalid: {e}")

        self.SUBSCRIBED_CHANNELS_PATH = subscribed_channels_path
        self.ALL_CHANNELS_PATH = all_channels_path
        self.queue_from_bot = queue_from_bot
        self.queue_to_bot = queue_to_bot
        self.media_groups = {}
        self.channels_per_page = 15
        self.management_channels_per_page = 10
        self.lock = asyncio.Lock()
        self.reload_event = asyncio.Event()
        self.initialize_event = asyncio.Event()
        self.all_channels_buffer = []
        self.subscribed_channels_buffer = []
        self.channel_info_msgs_buffer = deque(maxlen=10)
        self.bot_id = None

        self.bot_client = TelegramClient(
            bot_session_path, self.API_ID, self.API_HASH, system_version='4.16.30-vxCUSTOM')
        self.bot_client.add_event_handler(
            self.handle_message, events.NewMessage())
        self.bot_client.add_event_handler(
            self.handle_callback_query, events.CallbackQuery())
        self.bot_client.add_event_handler(
            self.handle_inline_query, events.InlineQuery())

    async def set_bot_commands(self):
        commands = [
            BotCommand(command="start", description="Открыть главное меню")
        ]
        await self.bot_client(
            SetBotCommandsRequest(scope=types.BotCommandScopeDefault(), lang_code='en', commands=commands))

    async def show_main_menu(self, event, message=None):
        buttons = [
            [
                Button.inline("📄 Все каналы", data="all_channels_list"),
                types.KeyboardButtonSwitchInline(
                    "🔍 Поиск каналов", query="", same_peer=True)
            ],
            [
                Button.inline("⚙️ Управление каналами",
                              data="manage_channels_menu")
            ],
            [
                Button.inline("🔄 Обновить список", data="refresh_channels"),
                Button.inline("❌ Закрыть", data="close_menu")
            ]
        ]
        text = "🤖 Главное меню управления каналами:\nВыберите действие:"
        if message:
            await event.edit(text, buttons=buttons)
        else:
            await event.respond(text, buttons=buttons)

    async def show_channel_management_menu(self, event):
        if not self.subscribed_channels_buffer:
            await event.edit("Нет каналов для управления.", buttons=self.back_button())
            return

        await self.send_channel_management_page(event, 0)

    async def send_channel_management_page(self, event, page_num):
        pages = [self.subscribed_channels_buffer[i:i + self.management_channels_per_page]
                 for i in range(0, len(self.subscribed_channels_buffer), self.management_channels_per_page)]
        if page_num < 0 or page_num >= len(pages):
            await event.edit("Некорректная страница.", buttons=self.back_button())
            return

        page = pages[page_num]
        text = f"📋 Страница {page_num + 1}/{len(pages)}\nВыберите канал для управления:\n\n"
        for idx, channel in enumerate(page, start=page_num * self.management_channels_per_page + 1):
            text += f"{idx}. {channel['name']}\n"

        buttons = []
        for idx, channel in enumerate(page):
            channel_index = page_num * self.management_channels_per_page + idx
            buttons.append([Button.inline(
                f"📺 {channel['name']}", data=f"manage_channel_{channel_index}_page_{page_num}")])

        nav_buttons = []
        if page_num > 0:
            nav_buttons.append(Button.inline(
                "⬅️ Назад", data=f"page_manage_{page_num - 1}"))
        if page_num < len(pages) - 1:
            nav_buttons.append(Button.inline(
                "Вперёд ➡️", data=f"page_manage_{page_num + 1}"))
        if nav_buttons:
            buttons.append(nav_buttons)

        buttons.append([self.back_button()])

        await event.edit(text, buttons=buttons)

    async def show_individual_channel_management(self, event, channel_index, page_num):
        if channel_index < 0 or channel_index >= len(self.subscribed_channels_buffer):
            await event.answer("Канал не найден!", alert=True)
            return

        channel = self.subscribed_channels_buffer[channel_index]
        text = (f"📺 Управление каналом:\n\n"
                f"Название: {channel['name']}\n"
                f"ID: {channel['id']}\n\n"
                f"Выберите действие:")
        buttons = [
            [Button.inline(
                "❌ Удалить канал", data=f"remove_channel_{channel_index}_page_{page_num}")],
            [Button.inline("🔙 Назад", data=f"page_manage_{page_num}")]
        ]
        await event.edit(text, buttons=buttons)

    def back_button(self):
        return Button.inline("🔙 Назад", data="back_to_menu")

    async def handle_inline_query(self, event):
        builder = event.builder
        query_text = (event.text or "").lower()
        results = []

        for channel in self.all_channels_buffer:
            if query_text in channel["name"].lower():
                article = builder.article(
                    title=channel["name"],
                    text=f"Канал: {channel['name']} (ID: {channel['id']})",
                    description=f"ID: {channel['id']}",
                    buttons=[
                        [Button.inline(
                            "➕ Добавить", data=f"add_channel_{channel['id']}")],
                        [Button.inline(
                            "➖ Удалить", data=f"remove_channel_from_inline_{channel['id']}")],
                        [Button.inline(
                            "❌ Закрыть", data="close_inline_message")]
                    ]
                )
                results.append(article)
                if len(results) >= 15:
                    break

        await event.answer(results, cache_time=0)

    async def handle_message(self, event):
        if event.message.via_bot_id and self.bot_id:
            if event.message.via_bot_id == self.bot_id:
                return

        if event.message.text and event.message.text.startswith("/"):
            if event.sender_id != self.TARGET_USER_ID:
                await self.bot_client.send_message(event.sender_id, "У вас нет прав на команды")
                return

            await self.handle_command_message(event)
            return

        if event.sender_id != self.SOURCE_USER_ID:
            await self.bot_client.send_message(event.sender_id, "Не присылай мне ничего")
            return

        if event.message.text and event.message.text.startswith("Сообщение из канала:"):
            await self.send_channel_info_msg(event.message)
            return

        group_id = getattr(event.message, "grouped_id", None)
        async with self.lock:
            if group_id is not None:
                if group_id in self.media_groups:
                    self.media_groups[group_id].append(event.message.id)
                else:
                    self.media_groups[group_id] = [event.message.id]
                    asyncio.create_task(
                        self.forward_group_later(group_id, event.chat))
                return

        await self.forward_messages(event.chat, [event.message.id])

    async def forward_group_later(self, group_id, chat):
        await asyncio.sleep(0.5)
        async with self.lock:
            msg_ids = self.media_groups.pop(group_id, None)
            if not msg_ids:
                return
        await self.forward_messages(chat, msg_ids)

    async def forward_messages(self, chat, msg_ids):
        try:
            await self.bot_client.forward_messages(
                self.TARGET_USER_ID,
                msg_ids,
                from_peer=chat
            )
        except Exception as e:
            print(
                f"{datetime.datetime.now()}\n🔴BotHandler🔴: error while forwarding msgs {msg_ids} from {chat}: {e}"
            )

        for _ in range(len(msg_ids)):
            await self.queue_from_bot.put("MSG_ACK")

    async def send_channel_info_msg(self, message):
        message_text = message.text.replace("Сообщение из канала:", "").strip()
        message_text = "🔁 " + message_text
        try:
            channel_info_message = await self.bot_client.send_message(self.TARGET_USER_ID, message_text)
            self.channel_info_msgs_buffer.append(channel_info_message)
        except Exception as e:
            print(
                f'{datetime.datetime.now()}\n🔴BotHandler🔴: Ошибка при отправке подготовительного сообщения'
                f'"{message_text}": {e}'
            )
        await self.queue_from_bot.put("MSG_ACK")
        return

    async def handle_command_message(self, event):
        if not event.message.text or not event.message.text.startswith("/"):
            return

        command_parts = event.message.text.strip().split()
        cmd = command_parts[0].lower()

        match cmd:
            case "/start":
                try:
                    await event.delete()
                except Exception:
                    pass
                await self.show_main_menu(event)
            case _:
                await self.unknown_command(command_parts)

    async def add_channel_command(self, command_parts):
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
                with open(self.SUBSCRIBED_CHANNELS_PATH, "w", encoding="utf-8") as f:
                    json.dump(self.subscribed_channels_buffer, f, indent=4)
                await self.bot_client.send_message(self.TARGET_USER_ID,
                                                   f"Канал {channel_to_add['name']} добавлен.")
                await self.queue_from_bot.put("RELOAD_CHANNELS")
                self.reload_event.clear()
                await self.reload_event.wait()

        except Exception as e:
            print(
                f"{datetime.datetime.now()}\n🔴BotHandler🔴: handle_command_message /add_channel {e}")
            await self.bot_client.send_message(self.TARGET_USER_ID, f"Ошибка: {e}")

    async def remove_channel_command(self, command_parts):
        if len(command_parts) < 2:
            await self.bot_client.send_message(self.TARGET_USER_ID,
                                               "Usage: /remove_channel <channel_number>")
            return
        try:
            channel_number = int(command_parts[1]) - 1
            if channel_number < 0 or channel_number >= len(self.subscribed_channels_buffer):
                await self.bot_client.send_message(self.TARGET_USER_ID, "Неверный номер канала.")
                return
            channel_to_remove = self.subscribed_channels_buffer.pop(
                channel_number)

            with open(self.SUBSCRIBED_CHANNELS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.subscribed_channels_buffer, f, indent=4)
            await self.bot_client.send_message(self.TARGET_USER_ID,
                                               f"Канал {channel_to_remove['name']} удалён.")
            await self.queue_from_bot.put("RELOAD_CHANNELS")
            self.reload_event.clear()
            await self.reload_event.wait()

        except Exception as e:
            print(
                f"{datetime.datetime.now()}\n🔴BotHandler🔴: handle_command_message /remove_channel {e}")
            await self.bot_client.send_message(self.TARGET_USER_ID, f"Ошибка: {e}")

    async def subscribed_channels_command(self, command_parts):
        try:
            if self.subscribed_channels_buffer:
                pages = [self.subscribed_channels_buffer[i:i + self.channels_per_page] for i in
                         range(0, len(self.subscribed_channels_buffer), self.channels_per_page)]
                await self.send_page_function(pages, 0, "sub")
            else:
                await self.bot_client.send_message(self.TARGET_USER_ID, "Нет доступных каналов.")
        except Exception as e:
            print(
                f"{datetime.datetime.now()}\n🔴BotHandler🔴: handle_command_message /subscribed_channels {e}")
            await self.bot_client.send_message(self.TARGET_USER_ID, f"Ошибка: {e}")

    async def all_channels_command(self, command_parts):
        try:
            if self.all_channels_buffer:
                pages = [self.all_channels_buffer[i:i + self.channels_per_page] for i in
                         range(0, len(self.all_channels_buffer), self.channels_per_page)]
                await self.send_page_function(pages, 0, "all")
            else:
                await self.bot_client.send_message(self.TARGET_USER_ID, "Нет доступных каналов.")
        except Exception as e:
            print(
                f"{datetime.datetime.now()}\n🔴BotHandler🔴: handle_command_message /all_channels {e}")
            await self.bot_client.send_message(self.TARGET_USER_ID, f"Ошибка: {e}")

    async def refresh_channels_command(self):
        await self.queue_from_bot.put("INITIALIZE_CHANNELS")
        self.initialize_event.clear()
        await self.initialize_event.wait()

        with open(self.ALL_CHANNELS_PATH, "r", encoding="utf-8") as f:
            self.all_channels_buffer = json.load(f)

    async def unknown_command(self, command_parts):
        await self.bot_client.send_message(self.TARGET_USER_ID, "Некорректная команда")

    async def handle_callback_query(self, event):
        data = event.data.decode("utf-8")

        if data == "manage_channels_menu":
            await self.show_channel_management_menu(event)
        elif data == "all_channels_list":
            if self.all_channels_buffer:
                pages = [self.all_channels_buffer[i:i + self.channels_per_page] for i in
                         range(0, len(self.all_channels_buffer), self.channels_per_page)]
                await self.send_page_function(pages, 0, "all", event.message_id)
            else:
                await event.edit("Нет доступных каналов.", buttons=self.back_button())
        elif data == "refresh_channels":
            await self.refresh_channels_command()
            await event.answer("Список каналов обновлён!", alert=True)
        elif data == "back_to_menu":
            await self.show_main_menu(event, message=True)
        elif data == "close_menu":
            try:
                await event.delete()
            except Exception as e:
                await event.edit("Меню закрыто.")
        elif data == "close_inline_message":
            await event.edit(buttons=None)
        elif data.startswith("page_manage_"):
            parts = data.split("_")
            page_num = int(parts[-1])
            await self.send_channel_management_page(event, page_num)
        elif data.startswith("manage_channel_"):
            parts = data.split("_")
            channel_index = int(parts[2])
            page_num = int(parts[4])
            await self.show_individual_channel_management(event, channel_index, page_num)
        elif data.startswith("remove_channel_from_inline_"):
            await self.remove_channel_from_inline(event, data)
        elif data.startswith("remove_channel_") and "_page_" in data:
            await self.remove_channel_from_callback(event, data)
        elif data.startswith("add_channel_"):
            await self.add_channel_from_callback(event, data)
        elif "_" in data:
            list_type, page_str = data.split("_")
            current_page = int(page_str)

            if list_type == "all":
                channels = self.all_channels_buffer
            elif list_type == "sub":
                channels = self.subscribed_channels_buffer
            else:
                await event.answer("Некорректный тип списка.", alert=True)
                return

            pages = [channels[i:i + self.channels_per_page]
                     for i in range(0, len(channels), self.channels_per_page)]

            if current_page < 0:
                current_page = 0
            elif current_page >= len(pages):
                current_page = len(pages) - 1

            await self.send_page_function(pages, current_page, list_type, event.message_id)
        else:
            await event.answer("Некорректный запрос.", alert=True)
            return

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
        msg += "\n".join(
            f"{first_index + idx}. {ch['name']} (ID: {ch['id']})" for idx, ch in enumerate(page))

        keyboard = []

        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(Button.inline(
                "⬅️", data=f"{list_type}_{current_page - 1}"))
        if current_page < len(pages) - 1:
            nav_buttons.append(Button.inline(
                "➡️", data=f"{list_type}_{current_page + 1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        if list_type == "all":
            keyboard.append([Button.inline("🔙 Назад", data="back_to_menu")])

        if len(keyboard) == 0:
            keyboard = None
        try:
            if message_id:
                await self.bot_client.edit_message(self.TARGET_USER_ID, message_id, msg, buttons=keyboard)
            else:
                await self.bot_client.send_message(self.TARGET_USER_ID, msg, buttons=keyboard)
        except Exception as e:
            print(f"{datetime.datetime.now()}\n🔴BotHandler🔴: send_page_function: {e}")

    async def start(self):
        await self.bot_client.start(bot_token=self.BOT_TOKEN)
        await self.set_bot_commands()

        bot_me = await self.bot_client.get_me()
        self.bot_id = bot_me.id

        with open(self.ALL_CHANNELS_PATH, "r", encoding="utf-8") as f:
            self.all_channels_buffer = json.load(f)
        with open(self.SUBSCRIBED_CHANNELS_PATH, "r", encoding="utf-8") as f:
            self.subscribed_channels_buffer = json.load(f)

        print(f"{datetime.datetime.now()}\n🔴BotHandler🔴: Бот-клиент запущен.")

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
            elif signal == "DELETE_CHANNEL_INFO_MSG":
                try:
                    last_message = self.channel_info_msgs_buffer[-1]
                    await self.bot_client.delete_messages(last_message.chat, last_message.id)
                except Exception as e:
                    print(
                        f"{datetime.datetime.now()}\n🔴BotHandler🔴: DELETE_CHANNEL_INFO_MSG не получилось удалить сообщение: {e}")

    async def add_channel_from_callback(self, event, data):
        channel_id = int(data.split("_")[2])
        channel_to_add = next(
            (ch for ch in self.all_channels_buffer if ch["id"] == int(channel_id)), None)

        if not channel_to_add:
            await event.answer("Канал не найден!", alert=True)
            return

        if any(ch["id"] == channel_to_add["id"] for ch in self.subscribed_channels_buffer):
            await event.answer("Этот канал уже добавлен!", alert=True)
            return

        self.subscribed_channels_buffer.append(channel_to_add)
        with open(self.SUBSCRIBED_CHANNELS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.subscribed_channels_buffer, f, indent=4)

        await self.queue_from_bot.put("RELOAD_CHANNELS")
        self.reload_event.clear()
        await self.reload_event.wait()
        await event.answer(f"Канал {channel_to_add['name']} добавлен!", alert=True)

    async def remove_channel_from_callback(self, event, data):
        parts = data.split("_")
        channel_index = int(parts[2])
        page_num = int(parts[4])

        if channel_index < 0 or channel_index >= len(self.subscribed_channels_buffer):
            await event.answer("Канал не найден!", alert=True)
            return

        channel_removed = self.subscribed_channels_buffer.pop(channel_index)
        with open(self.SUBSCRIBED_CHANNELS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.subscribed_channels_buffer, f, indent=4)

        await self.queue_from_bot.put("RELOAD_CHANNELS")
        self.reload_event.clear()
        await self.reload_event.wait()
        await event.answer(f"Канал {channel_removed['name']} удалён!", alert=True)

        if page_num == -1:
            return

        pages = [self.subscribed_channels_buffer[i:i + self.management_channels_per_page]
                 for i in range(0, len(self.subscribed_channels_buffer), self.management_channels_per_page)]

        if pages:
            if page_num >= len(pages):
                page_num = max(0, len(pages) - 1)
            await self.send_channel_management_page(event, page_num)
        else:
            await event.edit("Нет каналов для управления.", buttons=self.back_button())

    async def remove_channel_from_inline(self, event, data):
        channel_id = int(data.split("_")[4])

        channel_index = -1
        for idx, channel in enumerate(self.subscribed_channels_buffer):
            if channel["id"] == channel_id:
                channel_index = idx
                break

        if channel_index == -1:
            await event.answer("Канал не найден в подписках!", alert=True)
            return

        channel_removed = self.subscribed_channels_buffer.pop(channel_index)
        with open(self.SUBSCRIBED_CHANNELS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.subscribed_channels_buffer, f, indent=4)

        await self.queue_from_bot.put("RELOAD_CHANNELS")
        self.reload_event.clear()
        await self.reload_event.wait()
        await event.answer(f"Канал {channel_removed['name']} удалён из подписок!", alert=True)
