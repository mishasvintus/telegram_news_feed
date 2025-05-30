---

# Telegram Feed Bot 

A Telegram bot that aggregates news from your subscribed channels into a single news feed, similar to the way most
social networks operate.

- Built using **Telethon** using both **Telegram API** **Telegram Bot API**.

---

## Features 

- Automatically forwards new messages from subscribed channels to your personal chat.
- Add/remove channels via bot commands.
- Paginated lists for easy navigation.
- Using two accounts for separating channels and news feed is available.
- Bot can mark new messages from your subscribed channels as read while forwarding based on
  configuration.
- Bot can remain your account offline (not update status to online) during operation if configured.

### Using Two Accounts (optional) 

You can use two accounts for this bot:

- One for receiving news **from** the bot (aka **target Telegram account**).
- Another for monitoring channels **for** the bot (aka **source Telegram account**).

This setup allows you to separate the channels and view posts on your main account only through the news feed, without
cluttering it with direct subscriptions.

---

## Prerequisites 

- Python 3.8+
- Telegram API credentials
- Bot Token from [@BotFather](https://t.me/BotFather)

---

## Installation 

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

## Configuration 

Create a `config` directory and the necessary files:

### Directory Structure 

```
config/
│
├── keys.json                 │ Set this file manually
│
├── config.json               │ Generated automatically if does not exist
└── all_channels.json         │ Generated automatically if does not exist
└── subscribed_channels.json  │ Generated automatically if does not exist
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

- `API_ID` & `API_HASH`: Create an application on [my.telegram.org](https://my.telegram.org) in the **API Development
  Tools** section.
- `BOT_API_TOKEN` & `BOT_USERNAME`: Create a bot using [@BotFather](https://t.me/BotFather).
- `SOURCE_USER_ID`: This is the ID of your Telegram account from which the channels will be monitored (you can get it
  via @userinfobot).
- `TARGET_USER_ID`: This is the ID of your Telegram account to which the posts will be forwarded (you can get it via
  @userinfobot).

---
**Note:**

`SOURCE_USER_ID` and `TARGET_USER_ID` can be the same if you are using a single account.

### 2. config.json

```json
{
  "READ_NEW_POSTS": true,
  "STAY_OFFLINE": true
}
```

| Parameter        | Description                                                                                                                                                                                                       |
|------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `READ_NEW_POSTS` | **true** - The bot marks new messages from subscribed channels as read. **false** - The bot forwards new posts but does not mark them as read.                                                                    |
| `STAY_OFFLINE`   | **true** - The bot does not update your status to online when running and waits for forwarding until you're online. **false** - The bot forwards new posts instantly but updates your status to online each time. |

### 3. subscribed_channels.json & all_channels.json

- These files are generated **automatically** if they do not exist.
- `subscribed_channels.json` contains data about channels that you are subscribed to via the bot using your **target
  Telegram account**.
- `all_channels.json` contains data about all the channels you can subscribe to via the bot. In other words, these are
  the channels that your **source Telegram account** is subscribed to.

---

## Running the Bot 

```bash
cd /path/to/telegram_news_feed/src
python main.py
```

On the first run:

1. You'll be prompted to authenticate your user account. You will need to log in to the **source Telegram account**.
2. `all_channels.json` and `subscribed_channels.json` will be automatically generated, containing all available
   channels.

### Running the Bot in the Background:

To run the bot in the background on Linux, you can use `tmux` to create a persistent session. This way, the bot will
continue running even if you close the terminal.

1. **Install `tmux`** if it's not already installed:

   On Ubuntu/Debian-based systems:

   ```bash
   sudo apt update
   sudo apt install tmux
   ```

   On CentOS/Fedora/RHEL-based systems:

   ```bash
   sudo yum install tmux
   ```

2. Start a new `tmux` session:

   ```bash
   tmux new-session -s telegram_feed_bot
   ```

3. Inside the `tmux` session, navigate to your bot's directory:

   ```bash
   cd /path/to/telegram_news_feed/src
   ```

4. Run the bot:

   ```bash
   python main.py
   ```

5. To detach from the `tmux` session (keeping the bot running), press `Ctrl + B`, then release both keys and press `D`.

6. To reattach to the `tmux` session later, use:

   ```bash
   tmux attach-session -t telegram_feed_bot
   ```

7. If you want to kill the `tmux` session after you're done, run:

   ```bash
   tmux kill-session -t telegram_feed_bot
   ```

---

## Bot Interface 

The bot now features a convenient interactive interface with button menus instead of text commands. This makes interacting with the bot much simpler and more intuitive.

### Main Menu

Start the bot with the `/start` command to open the main menu with buttons:

| Button | Description |
|--------|-------------|
| **⚙️ Manage channels** | Manage subscriptions: add/remove channels with pagination (10 channels per page) |
| **🔍 Search channels** | Search channels by name using inline query - just start typing `@your_bot_name channel_name` |
| **📄 All channels** | View all available channels with pagination and "Subscribe" buttons |
| **🔄 Refresh** | Refresh the list of all available channels |
| **❌ Close** | Close the menu |

### Inline Channel Search

A particularly convenient feature - channel search in any chat:

1. Type `@your_bot_name` (your bot's username)
2. Add a space and start typing the channel name
3. Select the desired channel from the dropdown list
4. Use "➕ Subscribe" or "➖ Unsubscribe" buttons

This method works in any Telegram chat and allows you to quickly manage subscriptions without switching to private messages with the bot.

---

## How It Works 

1. The **source Telegram account** monitors the subscribed channels for new messages.
2. New messages from the monitored channels are forwarded to the bot in the background.
3. The bot forwards the new messages to the **target Telegram account** (the account where the news feed is displayed).
4. Service messages (between **source Telegram account** and **bot**) are immediately cleaned up to keep the feed tidy.

---

## Notes 

- The **source Telegram account** must be subscribed to the channels you want to subscribe to via the bot.

---

## Disclaimer ⚠️

This project is for educational purposes only. Please respect Telegram's Terms of Service and channel privacy policies.
