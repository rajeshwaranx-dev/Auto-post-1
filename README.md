# 🎬 Movie Auto Post Bot

A production-ready Telegram bot that automatically detects movie metadata from
filenames, fetches TMDB posters, and posts beautifully formatted messages to a
public channel.  Files are **never sent directly** — the bot generates deep
links to your existing **File Store Bot**.

---

## ✨ Features

| Feature | Details |
|---|---|
| 📂 Source channel listener | Watches a private channel for uploaded videos/documents |
| 🧠 Smart filename parsing | Title, year, quality, resolution, codec, languages, audio format, file size |
| 🖼️ TMDB poster fetch | Auto-fetches poster using movie name + year; falls back gracefully |
| 🔗 Deep-link generation | Generates `https://t.me/FileStoreBot?start=<group_id>` — no files sent by this bot |
| 🗄️ MongoDB grouping | Groups multiple qualities under one post; edits existing post on new upload |
| ⚡ Async throughout | Pyrogram + Motor + aiohttp — fully non-blocking |
| 🐳 Docker ready | Single `docker-compose up` on any VPS |
| ☁️ Koyeb ready | `koyeb.yaml` included for one-click cloud deploy |

---

## 📤 Output Format

```
🎬 Title: Avengers Endgame
📅 Year : 2019
📀 Quality: BluRay
🎧 Audio: Tamil + Telugu + Hindi + English

🔺 Telegram File 🔻

♨️ Avengers Endgame (2019) BRRip - x264 - [Tamil + Telugu + Hindi] - (AAC 2.0) - 450MB - ESub.mkv
♨️ Avengers Endgame (2019) BluRay - 720p - x264 - [Tamil + Telugu + Hindi + Eng] - (DD+5.1 - 192Kbps) - 1.3GB - ESub.mkv
♨️ Avengers Endgame (2019) BluRay - 1080p - x264 - [Tamil + Telugu + Hindi + Eng] - (DD+5.1 - 640Kbps) - 3.3GB - ESub.mkv

📦 Get all files in one link:
https://t.me/YourFileStoreBot?start=a3f9d1c20e44

Note ❗: If the link is not working, copy it and paste into your browser.
```

---

## 🗂️ Project Structure

```
movie-auto-post-bot/
├── main.py                       # Entry point
├── config.py                     # All env-var based config
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── koyeb.yaml
├── .env.example                  # Template — copy to .env
└── bot/
    ├── __init__.py
    ├── client.py                 # Pyrogram Client singleton
    ├── handlers/
    │   ├── __init__.py           # Registers all handlers
    │   └── channel_post.py      # Core logic: detect → parse → post/edit
    ├── utils/
    │   ├── __init__.py
    │   ├── file_parser.py        # Filename → MovieMeta dataclass
    │   ├── tmdb.py               # TMDB API client (async)
    │   ├── link_generator.py     # group_id + deep-link builder
    │   └── caption_builder.py   # Final formatted caption
    └── database/
        ├── __init__.py
        └── mongo.py              # Motor async MongoDB wrapper
```

---

## 🚀 Deployment

### Prerequisites

- A Telegram Bot token from [@BotFather](https://t.me/BotFather)
- `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org/apps)
- A running **File Store Bot** (this bot just generates links to it)
- MongoDB Atlas (free tier works) or self-hosted MongoDB
- TMDB API key (free) from [themoviedb.org](https://www.themoviedb.org/settings/api)

---

### 1️⃣ Local / VPS (Docker)

```bash
# Clone
git clone https://github.com/YOUR_USER/movie-auto-post-bot.git
cd movie-auto-post-bot

# Configure
cp .env.example .env
nano .env          # fill in all values

# Run
docker-compose up -d --build

# Logs
docker-compose logs -f bot
```

---

### 2️⃣ Local (without Docker)

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env …

python main.py
```

---

### 3️⃣ Koyeb (Cloud)

1. Fork this repo on GitHub.
2. Go to [koyeb.com](https://www.koyeb.com) → **Create app** → **GitHub**.
3. Select your fork.
4. Set all secrets in the Koyeb dashboard (see Environment Variables below).
5. Deploy.  Koyeb reads `koyeb.yaml` automatically.

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `API_ID` | ✅ | Telegram API ID |
| `API_HASH` | ✅ | Telegram API hash |
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `SOURCE_CHANNEL` | ✅ | Channel ID or @username where you upload files |
| `DEST_CHANNEL` | ✅ | Public channel ID or @username for formatted posts |
| `FILE_STORE_BOT` | ✅ | Username of your File Store Bot (without @) |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `DB_NAME` | ❌ | MongoDB database name (default: `movie_bot`) |
| `TMDB_API_KEY` | ✅ | TMDB API key |
| `TMDB_LANGUAGE` | ❌ | TMDB response language (default: `en-US`) |
| `FALLBACK_POSTER` | ❌ | Poster URL when TMDB finds nothing |
| `GROUP_WAIT_SECONDS` | ❌ | Seconds to wait before posting (default: `30`) |
| `LOG_LEVEL` | ❌ | Logging level (default: `INFO`) |

---

## 🔧 Bot Permissions Required

| Channel | Permission |
|---|---|
| `SOURCE_CHANNEL` | Admin → **Read messages** |
| `DEST_CHANNEL` | Admin → **Post messages**, **Edit messages** |

---

## 🤝 Integration with File Store Bot

This bot stores a `group_id` in MongoDB and generates a deep link:

```
https://t.me/<FILE_STORE_BOT>?start=<group_id>
```

Your **File Store Bot** must:
1. Accept the `group_id` as a `/start` parameter.
2. Query the same MongoDB collection `movies` → find doc by `group_id`.
3. Extract `qualities[].file_id` list.
4. Forward / send those files to the user.

A minimal File Store Bot handler:

```python
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    if len(message.command) < 2:
        await message.reply("Hello!")
        return
    group_id = message.command[1]
    doc = await db.movies.find_one({"group_id": group_id})
    if not doc:
        await message.reply("Link expired or invalid.")
        return
    for q in doc["qualities"]:
        await client.send_document(message.chat.id, q["file_id"])
```

---

## 📄 License

MIT — free to use and modify.
