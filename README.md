
---

# Telegram Feed Bot 🤖📰

A Telegram bot that aggregates news from your subscribed channels into a single news feed, similar to the way most social networks operate.

- Built using **Telethon** (Telegram API) and **Telegram Bot API**.

---

## Features ✨

- Automatically forwards new messages from subscribed channels to your personal chat.
- Add/remove channels via bot commands.
- Paginated lists for easy navigation.
- Using two accounts for separating channels and news feed is available.
## Using Two Accounts 🧑‍🤝‍🧑

You can use two accounts for this bot:

- One for receiving news **from** the bot (aka **target Telegram account**).
- Another for monitoring channels for the bot (aka **source Telegram account**).

This setup allows you to separate the channels and view posts on your main account only through the news feed, without cluttering it with direct subscriptions.

---

## Prerequisites 🛠️

- Python 3.8+
- Telegram API credentials
- Bot Token from [@BotFather](https://t.me/BotFather)

---

## Installation 📦

1. Clone the repository:

```bash
git clone git@github.com:mishasvintus/telegram_news_feed.git
cd telegram_news_feed
```

2. Install dependencies:

```bash
pip install telethon
```

---

## Configuration ⚙️

Create a `config` directory and the necessary files:

### Directory Structure 📂

```
config/
│
├── keys.json                 │ Set this file manually
│
├── subscribed_channels.json  │ Generated automatically
└── all_channels.json         │ Generated automatically
```

### 1. keys.json

```json
{
  "API_ID": "your_api_id",
  "API_HASH": "your_api_hash",
  "BOT_API_TOKEN": "your_bot_token",
  "BOT_USERNAME": "your_bot_username",
  "SOURCE_USER_ID": "source_bot_user_id",
  "TARGET_USER_ID": "your_personal_user_id"
}
```

**How to get credentials:**

- `API_ID` & `API_HASH`: Create an application on [my.telegram.org](https://my.telegram.org) in the **API Development Tools** section.
- `BOT_API_TOKEN` & `BOT_USERNAME`: Create a bot using [@BotFather](https://t.me/BotFather).
- `SOURCE_USER_ID`: This is the ID of your Telegram account from which the channels will be monitored (you can get it via @userinfobot).
- `TARGET_USER_ID`: This is the ID of your Telegram account to which the posts will be forwarded (you can get it via @userinfobot).

---
**Note:**

`SOURCE_USER_ID` and `TARGET_USER_ID` can be the same if you are using a single account.

### 2. subscribed_channels.json & all_channels.json

- These files are generated **automatically** if they do not exist.
- `subscribed_channels.json` contains data about channels that you are subscribed to via the bot using you **target Telegram account**.
- `all_channels.json` contains data about all the channels you can subscribe to via the bot. In other words, these are the channels that your **source Telegram account** is subscribed to.

---

## Running the Bot 🏃

```bash
python main.py
```

On the first run:

1. You'll be prompted to authenticate your user account. You will need to log in to the **source Telegram account**.
2. `all_channels.json` and `subscribed_channels.json` will be automatically generated, containing all available channels.

---

## Bot Commands 🕹️

| Command                                | Description                        |
|----------------------------------------|------------------------------------|
| `/add_channel <number_in_all_list>`    | Add a channel from the "all channels" list |
| `/remove_channel <number_in_sub_list>` | Remove a subscribed channel        |
| `/subscribed_channels`                 | Show your current subscriptions    |
| `/all_channels`                        | Show all available channels        |
| `/refresh_channels`                    | Refresh `all_channels.json`        |

---

## How It Works 🔧
1. The **source Telegram account** monitors the subscribed channels for new messages.
2. New messages from the monitored channels are forwarded to the bot in the background.
3. The bot forwards the new messages to the **target Telegram account** (the account where the news feed is displayed).
4. Service messages (between **source Telegram account** and **bot**) are immediately cleaned up to keep the feed tidy.

---

## Notes 📝

- The **source Telegram account** must be subscribed to the channels you want to subscribe to via the bot.

---

## Disclaimer ⚠️

This project is for educational purposes only. Please respect Telegram's Terms of Service and channel privacy policies.

