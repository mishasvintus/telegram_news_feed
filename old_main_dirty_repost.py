import json
import asyncio
import requests
import os
from telethon import TelegramClient, events

# Загружаем ключи и токены из keys.json
with open("keys.json") as f:
    config = json.load(f)

API_ID = config["API_ID"]
API_HASH = config["API_HASH"]
BOT_TOKEN = config["BOT_API_TOKEN"]
USER_ID = config["USER_ID"]

# Загружаем информацию о каналах из all_channels.json
with open("all_channels.json") as f:
    channels_config = json.load(f)

channels = channels_config
channel_ids = [channel["id"] for channel in channels]
channel_names = {channel["id"]: channel["name"] for channel in channels}

client = TelegramClient("session", API_ID, API_HASH)

# Множество для отслеживания обработанных групп альбомов
processed_group_ids = set()

async def remove_group_id(grouped_id, delay=60):
    """Удаляет grouped_id через некоторое время, чтобы не накапливать память."""
    await asyncio.sleep(delay)
    processed_group_ids.discard(grouped_id)

def send_text(text):
    """Отправка простого текстового сообщения."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": USER_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    requests.post(url, data=payload)

def send_photo(caption, file_path):
    """Отправка одиночного фото с подписью и удалением файла после отправки."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": USER_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }
    with open(file_path, "rb") as photo_file:
        requests.post(url, data=payload, files={"photo": photo_file})
    os.remove(file_path)

def send_video(caption, file_path):
    """Отправка одиночного видео с подписью и удалением файла после отправки."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    payload = {
        "chat_id": USER_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }
    with open(file_path, "rb") as video_file:
        requests.post(url, data=payload, files={"video": video_file})
    os.remove(file_path)

def send_media_group(media_files, caption):
    """
    Отправка группы медиа как альбома.
    Для первого элемента устанавливаем caption, остальные без подписи.
    После отправки все файлы закрываются и удаляются.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
    media_group = []
    files_dict = {}
    file_objs = {}
    for idx, media in enumerate(media_files):
        media_type = "photo" if media["type"] == "photo" else "video"
        key = f"file{idx}"
        item = {
            "type": media_type,
            "media": f"attach://{key}"
        }
        if idx == 0 and caption:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
        media_group.append(item)
        f = open(media["file"], "rb")
        file_objs[key] = f
        files_dict[key] = f
    payload = {
        "chat_id": USER_ID,
        "media": json.dumps(media_group)
    }
    requests.post(url, data=payload, files=files_dict)
    # Закрываем файлы
    for f in file_objs.values():
        f.close()
    # Удаляем файлы
    for media in media_files:
        os.remove(media["file"])

@client.on(events.NewMessage(chats=channel_ids))
async def new_post_handler(event):
    message = event.message
    channel_name = channel_names.get(event.chat_id, "Канал")
    text = message.message or ""
    caption = f"<b>Новый пост в {channel_name}:</b>\n\n{text}" if text else f"<b>Новый пост в {channel_name}:</b>"

    media_files = []

    if message.media:
        if message.grouped_id:
            if message.grouped_id in processed_group_ids:
                return
            processed_group_ids.add(message.grouped_id)
            asyncio.create_task(remove_group_id(message.grouped_id))
            messages = await event.client.get_messages(
                event.chat_id, min_id=event.id - 10, max_id=event.id + 10
            )
            for msg in messages:
                if msg.grouped_id == message.grouped_id and msg.media:
                    media_path = await msg.download_media()
                    media_type = "photo" if msg.photo else "video"
                    media_files.append({"file": media_path, "type": media_type})
        else:
            media_path = await message.download_media()
            media_type = "photo" if message.photo else "video"
            media_files.append({"file": media_path, "type": media_type})

    if media_files:
        if len(media_files) == 1:
            if media_files[0]["type"] == "photo":
                send_photo(caption, media_files[0]["file"])
            else:
                send_video(caption, media_files[0]["file"])
        else:
            send_media_group(media_files, caption)
    else:
        send_text(caption)

async def main():
    await client.start()
    print("Телеграм клиент запущен...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
