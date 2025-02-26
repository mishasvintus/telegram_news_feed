import asyncio
import json
from telethon import TelegramClient

with open("../config/keys.json", "r", encoding="utf-8") as f:
    config = json.load(f)

API_ID = config["API_ID"]
API_HASH = config["API_HASH"]
USER_ID = config["SOURCE_USER_ID"]

channels = dict()
async def main():
    async with TelegramClient("session_name", API_ID, API_HASH) as client:
        dialogs = await client.get_dialogs()  # Ждём выполнение корутины
        for chat in dialogs:
            if chat.is_channel:
                channels[chat.title] = chat.id
                # print(f"{chat.title}: {chat.id}")

        formatted_channels = [{"name": key, "id": value} for key, value in channels.items()]

        with open("../config/all_channels.json", "w", encoding="utf-8") as f:
            json.dump(formatted_channels, f, ensure_ascii=False, indent=4)

asyncio.run(main())
