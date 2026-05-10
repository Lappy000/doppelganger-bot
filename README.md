# 🎭 Doppelganger Bot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue.svg?logo=telegram)](https://core.telegram.org/bots)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**AI-powered Telegram bot that learns personality patterns from group chats and can impersonate anyone.**

Doppelganger silently observes conversations in your group chat, building detailed personality profiles for each member. It learns their vocabulary, slang, emoji habits, favorite topics, and writing quirks. Then, on command, it can generate messages that sound exactly like any member — or roast them in their own style.

> ⚠️ **Privacy First**: No messages are ever stored. Only statistical features (word frequencies, emoji patterns, style metrics) are extracted and kept.

---

## ✨ Features

- **🧠 Personality Profiling** — Tracks vocabulary, sentence length, emoji usage, topic preferences, slang, and response patterns
- **🎭 Style Mimicry** — Generates messages matching a specific user's writing patterns using LLMs
- **🔥 Roast Mode** — Roasts users *in their own writing style* for maximum comedic effect
- **📊 Profile Viewer** — See what the bot has learned about anyone's communication style
- **🔒 Privacy Controls** — Opt-out anytime, delete your data on command
- **🤖 LLM Agnostic** — Works with OpenAI, Anthropic Claude, or any OpenAI-compatible API (Ollama, Together, etc.)
- **📈 Incremental Learning** — Profiles get more accurate over time using exponential moving averages

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                 Telegram Group Chat              │
└──────────────────────┬──────────────────────────┘
                       │ messages
                       ▼
┌─────────────────────────────────────────────────┐
│              DoppelgangerBot (bot.py)            │
│  ┌─────────────┐  ┌────────────┐  ┌─────────┐  │
│  │  Commands   │  │  Learning  │  │ Privacy │  │
│  │  /profile   │  │  Pipeline  │  │ Manager │  │
│  │  /imperson. │  │ (silent)   │  │ opt-out │  │
│  │  /roast     │  │            │  │ forget  │  │
│  │  /stats     │  │            │  │         │  │
│  └──────┬──────┘  └─────┬──────┘  └─────────┘  │
└─────────┼────────────────┼──────────────────────┘
          │                │
          ▼                ▼
┌──────────────┐  ┌──────────────────┐
│  Response    │  │  Personality     │
│  Generator   │  │  Engine          │
│ (generator)  │  │ (personality.py) │
└──────┬───────┘  └────────┬─────────┘
       │                   │
       ▼                   ▼
┌──────────────┐  ┌──────────────────┐
│  LLM API     │  │  Message         │
│  (OpenAI/    │  │  Analyzer        │
│   Anthropic/ │  │  (analyzer.py)   │
│   Custom)    │  │                  │
└──────────────┘  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  Profile Storage │
                  │  (JSON files)    │
                  │  (storage.py)    │
                  └──────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- A Telegram Bot Token ([get one from @BotFather](https://t.me/BotFather))
- An LLM API key (OpenAI, Anthropic, or compatible)

### Installation

```bash
# Clone the repository
git clone https://github.com/Lappy000/doppelganger-bot.git
cd doppelganger-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your tokens
```

### Configuration

Edit `.env` with your settings:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
LLM_API_KEY=your_openai_or_anthropic_key
LLM_PROVIDER=openai          # or: anthropic, custom
LLM_MODEL=gpt-4o-mini        # or: claude-3-haiku-20240307
LLM_API_BASE=                 # Custom endpoint for Ollama/Together/etc.
```

### Running

```bash
python -m doppelganger.bot
```

---

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f doppelganger
```

---

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/start` | Introduction and help |
| `/profile @user` | View learned personality traits |
| `/impersonate @user [topic]` | Generate a message as that user |
| `/roast @user` | Roast them in their own writing style |
| `/stats` | Group learning statistics |
| `/optout` | Stop bot from learning your style |
| `/optin` | Resume learning |
| `/forget` | Delete all your personality data |

### Examples

```
/impersonate @alice what she thinks about mondays
/impersonate @bob              (random topic they like)
/roast @charlie
/profile @dave
```

---

## 🔧 How It Works

### Learning Pipeline

1. **Message Observation** — Bot silently reads all group messages (no storage)
2. **Feature Extraction** — `MessageAnalyzer` extracts linguistic features:
   - Vocabulary frequency distribution
   - Emoji usage patterns
   - Sentence length and structure
   - Capitalization habits
   - Slang and abbreviation usage
   - Topic keywords
   - Temporal activity patterns
3. **Profile Building** — `PersonalityEngine` maintains rolling profiles using exponential moving averages
4. **Storage** — Only statistical features saved to JSON (never raw messages)

### Generation Pipeline

1. **Profile Retrieval** — Load target user's personality profile
2. **Prompt Construction** — Build detailed style description from profile data
3. **LLM Generation** — Send to configured LLM with style-matching instructions
4. **Response Cleaning** — Strip artifacts and format for Telegram

---

## 📊 What Gets Tracked

| Feature | Description |
|---------|-------------|
| `top_words` | Most frequently used words (relative frequency) |
| `unique_phrases` | Distinctive 2-word patterns |
| `emoji_frequencies` | Emoji usage distribution |
| `slang_terms` | Informal language patterns |
| `abbreviations` | Short forms (u, rn, ngl, etc.) |
| `filler_words` | Discourse markers (like, basically, etc.) |
| `topic_affinities` | Interest scores per topic category |
| `style_metrics` | Message length, caps, punctuation, questions |
| `active_hours` | When they're most active |

---

## 🔒 Privacy

- **No message storage** — Raw messages are never saved to disk
- **Feature-only extraction** — Only statistical patterns are kept
- **User control** — `/optout` stops learning, `/forget` deletes everything
- **Local storage** — All data stays on your server (JSON files)
- **No third-party data sharing** — Only the configured LLM sees profile summaries during generation

---

## 🛠️ Development

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install black isort mypy

# Format code
black doppelganger/
isort doppelganger/

# Type checking
mypy doppelganger/
```

---

## 📁 Project Structure

```
doppelganger-bot/
├── doppelganger/
│   ├── __init__.py          # Package metadata
│   ├── bot.py               # Telegram bot handlers & commands
│   ├── personality.py       # PersonalityEngine - profile building
│   ├── generator.py         # ResponseGenerator - LLM style mimicry
│   ├── storage.py           # ProfileStorage - JSON persistence
│   ├── analyzer.py          # MessageAnalyzer - feature extraction
│   └── config.py            # Settings from environment
├── README.md
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── LICENSE
└── docker-compose.yml
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This bot is meant for fun in friend groups. Always get consent before deploying in a group. Be respectful — the roast feature should bring laughs, not tears. Users can opt out at any time.

---

*Built with ❤️ and questionable ethics by [Lappy000](https://github.com/Lappy000)*
