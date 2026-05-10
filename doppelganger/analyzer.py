"""
Message Analyzer for Doppelganger Bot.

Extracts linguistic features from raw messages without storing the messages themselves.
Analyzes vocabulary, emoji patterns, sentence structure, slang, and temporal patterns.
"""

import re
import string
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Common English filler words and discourse markers
FILLER_WORDS = {
    "like", "basically", "literally", "actually", "honestly", "seriously",
    "obviously", "clearly", "apparently", "essentially", "definitely",
    "probably", "maybe", "perhaps", "anyway", "anyways", "whatever",
    "idk", "tbh", "ngl", "imo", "imho", "lol", "lmao", "bruh",
    "dude", "bro", "sis", "fam", "lowkey", "highkey", "deadass",
    "fr", "no cap", "bet", "slay", "vibe", "mood", "based",
}

# Common internet abbreviations
ABBREVIATIONS = {
    "u": "you", "r": "are", "ur": "your/you're", "rn": "right now",
    "ngl": "not gonna lie", "tbh": "to be honest", "imo": "in my opinion",
    "idk": "I don't know", "idm": "I don't mind", "smh": "shaking my head",
    "omg": "oh my god", "brb": "be right back", "ttyl": "talk to you later",
    "wyd": "what you doing", "hmu": "hit me up", "ong": "on god",
    "icl": "I can't lie", "istg": "I swear to god", "atp": "at this point",
    "ts": "this shit", "nvm": "nevermind", "ofc": "of course",
    "ik": "I know", "ty": "thank you", "np": "no problem",
    "w": "win", "l": "loss", "pls": "please", "thx": "thanks",
}

# Topic keywords for categorization
TOPIC_KEYWORDS = {
    "gaming": {"game", "games", "gaming", "play", "played", "player", "steam", "console", "pc", "fps", "rpg", "mmo"},
    "tech": {"code", "coding", "programming", "python", "linux", "server", "api", "bug", "deploy", "github"},
    "music": {"music", "song", "album", "artist", "band", "listen", "spotify", "playlist", "track", "beat"},
    "food": {"food", "eat", "eating", "cook", "cooking", "recipe", "restaurant", "hungry", "dinner", "lunch"},
    "fitness": {"gym", "workout", "exercise", "run", "running", "lift", "gains", "cardio", "protein", "sets"},
    "movies": {"movie", "film", "watch", "watched", "series", "show", "episode", "season", "actor", "director"},
    "politics": {"vote", "election", "government", "policy", "political", "democrat", "republican", "congress"},
    "crypto": {"crypto", "bitcoin", "btc", "eth", "token", "blockchain", "nft", "wallet", "defi", "trading"},
    "memes": {"meme", "memes", "funny", "lol", "lmao", "based", "cringe", "cope", "ratio", "seethe"},
    "relationships": {"date", "dating", "relationship", "boyfriend", "girlfriend", "crush", "love", "breakup"},
}

# Emoji regex pattern
EMOJI_PATTERN = re.compile(
    "[\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"  # supplemental
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols ext-A
    "\U00002702-\U000027B0"
    "]+",
    flags=re.UNICODE,
)


@dataclass
class MessageFeatures:
    """Extracted features from a single message."""

    word_count: int = 0
    char_count: int = 0
    sentence_count: int = 0
    avg_word_length: float = 0.0
    capitalization_ratio: float = 0.0
    punctuation_count: int = 0
    is_question: bool = False
    is_exclamation: bool = False
    has_ellipsis: bool = False
    emoji_list: list = field(default_factory=list)
    words: list = field(default_factory=list)
    filler_words_used: list = field(default_factory=list)
    abbreviations_used: list = field(default_factory=list)
    topics_detected: list = field(default_factory=list)
    hour_of_day: int = 0
    day_of_week: int = 0  # 0=Monday, 6=Sunday
    is_reply: bool = False
    is_forwarded: bool = False


class MessageAnalyzer:
    """Extracts linguistic and behavioral features from messages."""

    def __init__(self):
        self._word_pattern = re.compile(r"\b[a-zA-Z']+\b")
        self._sentence_pattern = re.compile(r"[.!?]+")
        self._repeated_char_pattern = re.compile(r"(.)\1{2,}")
        self._url_pattern = re.compile(r"https?://\S+")

    def analyze(self, text: str, timestamp: Optional[datetime] = None, is_reply: bool = False) -> MessageFeatures:
        """Analyze a single message and extract features."""
        if not text or not text.strip():
            return MessageFeatures()

        # Clean URLs for word analysis (but keep them for length metrics)
        clean_text = self._url_pattern.sub("", text)
        now = timestamp or datetime.now()

        # Basic metrics
        char_count = len(text)
        words = self._word_pattern.findall(clean_text.lower())
        word_count = len(words)
        sentences = self._sentence_pattern.split(text)
        sentence_count = max(1, len([s for s in sentences if s.strip()]))

        # Capitalization analysis
        alpha_chars = [c for c in text if c.isalpha()]
        cap_ratio = sum(1 for c in alpha_chars if c.isupper()) / max(1, len(alpha_chars))

        # Punctuation density
        punct_count = sum(1 for c in text if c in string.punctuation)

        # Question/exclamation detection
        is_question = "?" in text
        is_exclamation = "!" in text
        has_ellipsis = "..." in text or "…" in text

        # Emoji extraction
        emojis = EMOJI_PATTERN.findall(text)
        emoji_list = list(emojis)

        # Average word length
        avg_word_len = sum(len(w) for w in words) / max(1, len(words))

        # Filler words detection
        word_set = set(words)
        fillers = [w for w in words if w in FILLER_WORDS]

        # Abbreviation detection
        abbreviations = [w for w in words if w in ABBREVIATIONS]

        # Topic detection
        topics = []
        for topic, keywords in TOPIC_KEYWORDS.items():
            if word_set & keywords:
                match_count = len(word_set & keywords)
                if match_count >= 1:
                    topics.append(topic)

        return MessageFeatures(
            word_count=word_count,
            char_count=char_count,
            sentence_count=sentence_count,
            avg_word_length=avg_word_len,
            capitalization_ratio=cap_ratio,
            punctuation_count=punct_count,
            is_question=is_question,
            is_exclamation=is_exclamation,
            has_ellipsis=has_ellipsis,
            emoji_list=emoji_list,
            words=words,
            filler_words_used=fillers,
            abbreviations_used=abbreviations,
            topics_detected=topics,
            hour_of_day=now.hour,
            day_of_week=now.weekday(),
            is_reply=is_reply,
            is_forwarded=False,
        )

    def extract_phrases(self, text: str, n: int = 2) -> list[str]:
        """Extract n-gram phrases from text."""
        clean_text = self._url_pattern.sub("", text.lower())
        words = self._word_pattern.findall(clean_text)
        if len(words) < n:
            return []

        phrases = []
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            phrases.append(phrase)
        return phrases

    def detect_repeated_chars(self, text: str) -> list[str]:
        """Detect character repetition patterns like 'nooo', 'yesss'."""
        return self._repeated_char_pattern.findall(text.lower())

    def get_vocabulary_signature(self, messages_features: list[MessageFeatures], top_n: int = 100) -> dict[str, float]:
        """Build vocabulary frequency distribution from multiple analyzed messages."""
        word_counter = Counter()
        total_words = 0

        for features in messages_features:
            word_counter.update(features.words)
            total_words += features.word_count

        if total_words == 0:
            return {}

        # Normalize to relative frequencies
        signature = {}
        for word, count in word_counter.most_common(top_n):
            signature[word] = count / total_words

        return signature
