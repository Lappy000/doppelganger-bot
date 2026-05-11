# 🎭 Doppelganger Bot

**AI-powered personality cloning for Telegram groups.**

Doppelganger Bot joins your group chat, silently learns how everyone talks — their slang, opinions, humor style, recurring topics — then uses that knowledge to roast, impersonate, and banter like a real member of the squad.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-blue?logo=telegram)](https://core.telegram.org/bots/api)

---

## ✨ Features

- **🧠 Personality Learning** — Builds rich personality profiles from chat messages using LLM analysis
- **💬 Natural Responses** — Responds contextually with the right tone, slang, and group dynamics
- **🎯 Targeted Roasts** — `/roast @friend` generates personalized burns based on learned quirks
- **👻 Silence Breaker** — Automatically revives dead chats with provocative or funny messages
- **📊 Profile Insights** — View what the bot has learned about each member
- **🔌 Provider Agnostic** — Works with OpenAI, OpenRouter, io.net, or any OpenAI-compatible API
- **⚡ Async Architecture** — Built on `python-telegram-bot` with full async/await support

---

## 🏗️ Architecture

```
doppelganger/
├── __init__.py           # Package entry point
├── config.py             # Configuration & environment loading
├── bot.py                # Application bootstrap & lifecycle
├── handlers/
│   ├── __init__.py
│   ├── messages.py       # Message processing & response triggers
│   └── commands.py       # Bot commands (/profile, /roast, /stats, etc.)
├── ai/
│   ├── __init__.py
│   ├── engine.py         # LLM client & prompt construction
│   └── prompts.py        # System prompts & templates
├── profiles/
│   ├── __init__.py
│   ├── manager.py        # Profile CRUD & AI-driven updates
│   └── models.py         # Profile data models
├── storage/
│   ├── __init__.py
│   └── tracker.py        # SQLite conversation logging & message buffer
└── scheduler/
    ├── __init__.py
    └── background.py     # Periodic tasks (silence breaker, random messages)
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Lappy000/doppelganger-bot.git
cd doppelganger-bot
pip install -r requirements.txt
```

### 2. Configure

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:
| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `GROUP_CHAT_ID` | Target group chat ID (use `/chatid` command to discover) |
| `LLM_API_KEY` | API key for your LLM provider |
| `LLM_BASE_URL` | Base URL (OpenAI-compatible endpoint) |
| `LLM_MODEL` | Model identifier (e.g., `gpt-4o`, `anthropic/claude-3.5-sonnet`) |

### 3. Run

```bash
python -m doppelganger
```

### 4. Add to Group

1. Add the bot to your Telegram group
2. Disable privacy mode via BotFather (`/setprivacy` → Disable) so it can read all messages
3. The bot will start learning immediately

---

## ⚙️ Configuration

All behavior is tunable in `.env`:

```env
# Response probability (0.0 - 1.0)
RANDOM_REPLY_CHANCE=0.15

# Minutes of silence before bot speaks up
SILENCE_THRESHOLD_MINUTES=120

# Minimum minutes between spontaneous messages
MIN_SPONTANEOUS_INTERVAL=10

# Profile analysis frequency (every N messages per user)
PROFILE_UPDATE_INTERVAL=10

# Bot personality template (see docs)
BOT_PERSONA=default
```

---

## 🎮 Commands

| Command | Description |
|---------|-------------|
| `/profile` | View your learned personality profile |
| `/profile @user` | View someone else's profile |
| `/stats` | Group activity leaderboard |
| `/roast @user` | Generate a personalized roast |
| `/impersonate @user` | Bot responds as if it were that person |
| `/forget` | Clear conversation context (keeps profiles) |
| `/chatid` | Display current chat ID (for setup) |

---

## 🧠 How It Works

### Learning Loop

1. **Observe** — Every message is logged and buffered (last 50 in memory, all in SQLite)
2. **Analyze** — Every N messages per user, an LLM extracts personality traits, speech patterns, interests, and roast material
3. **Profile** — Extracted data merges into persistent JSON profiles (deduplication, size limits)
4. **Respond** — When triggered, the bot constructs a prompt with personality context + recent chat history

### Response Triggers

- **@mention** — Always responds when directly addressed
- **Reply** — Responds when someone replies to its messages
- **Random** — Configurable chance to jump into any conversation
- **Silence** — Breaks long silences with provocative or funny messages

### Profile Schema

```json
{
  "user_id": 123456789,
  "name": "Alex",
  "personality_traits": ["sarcastic", "competitive"],
  "interests": ["gaming", "crypto"],
  "dislikes": ["mornings", "small talk"],
  "humor_style": "dry wit with self-deprecation",
  "speech_patterns": ["lowkey", "ngl", "fr fr"],
  "recurring_topics": ["ranked matches", "side projects"],
  "roast_material": ["claims to be grinding but plays games 6h/day"],
  "fun_facts": ["once mass-pinged the whole group at 4am"],
  "mood_history": ["tilted (05/10 23:00)", "chill (05/11 14:00)"],
  "recent_quotes": ["bro I literally cannot", "skill issue"],
  "message_count": 847
}
```

---

## 🔌 LLM Providers

Doppelganger works with any OpenAI-compatible API:

| Provider | Base URL | Notes |
|----------|----------|-------|
| OpenAI | `https://api.openai.com/v1` | GPT-4o recommended |
| OpenRouter | `https://openrouter.ai/api/v1` | Multi-model access |
| io.net | `https://api.intelligence.io.solutions/api/v1` | Free tier available |
| Ollama | `http://localhost:11434/v1` | Local models |
| Any compatible | Your endpoint | Must support `/chat/completions` |

---

## 🛡️ Privacy & Ethics

- **No data leaves your group** — Profiles are stored locally as JSON files
- **Configurable retention** — Set how much history to keep
- **Clear command** — Users can wipe conversation context anytime
- **Open source** — Audit exactly what data is collected and how it's used

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions welcome! Areas of interest:
- Additional LLM provider adapters
- Web dashboard for profile visualization
- Multi-language personality templates
- Voice message transcription & analysis
- Sentiment tracking over time
