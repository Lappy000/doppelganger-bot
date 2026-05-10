"""
Personality Engine for Doppelganger Bot.

Builds and maintains personality profiles by processing message features over time.
Implements incremental learning - profiles get more accurate with more data.
"""

import time
from collections import Counter
from datetime import datetime
from typing import Optional
import logging

from .analyzer import MessageAnalyzer, MessageFeatures, FILLER_WORDS, ABBREVIATIONS
from .storage import ProfileStorage, PersonalityProfile, StyleMetrics
from .config import BotConfig

logger = logging.getLogger(__name__)


class PersonalityEngine:
    """
    Builds and updates personality profiles from message streams.

    Uses exponential moving averages for metrics so profiles naturally
    adapt to changes in a user's writing style over time.
    """

    def __init__(self, storage: ProfileStorage, config: BotConfig):
        self.storage = storage
        self.config = config
        self.analyzer = MessageAnalyzer()
        self._message_buffers: dict[str, list[MessageFeatures]] = {}
        self._phrase_buffers: dict[str, list[str]] = {}
        # Smoothing factor for exponential moving average (higher = more recent bias)
        self._ema_alpha = 0.1

    def _buffer_key(self, user_id: int, chat_id: int) -> str:
        return f"{chat_id}:{user_id}"

    def process_message(
        self,
        text: str,
        user_id: int,
        chat_id: int,
        username: str = "",
        display_name: str = "",
        timestamp: Optional[datetime] = None,
        is_reply: bool = False,
    ) -> Optional[PersonalityProfile]:
        """
        Process a single message and update the user's profile.

        Returns the updated profile if a batch update was triggered, else None.
        """
        # Analyze the message
        features = self.analyzer.analyze(text, timestamp=timestamp, is_reply=is_reply)

        if features.word_count == 0:
            return None

        # Buffer the features
        key = self._buffer_key(user_id, chat_id)
        if key not in self._message_buffers:
            self._message_buffers[key] = []
            self._phrase_buffers[key] = []

        self._message_buffers[key].append(features)

        # Extract and buffer bigram phrases
        phrases = self.analyzer.extract_phrases(text, n=2)
        self._phrase_buffers[key].extend(phrases)

        # Check if we should update the profile
        if len(self._message_buffers[key]) >= self.config.profile_update_interval:
            return self._flush_buffer(user_id, chat_id, username, display_name)

        return None

    def _flush_buffer(
        self, user_id: int, chat_id: int, username: str, display_name: str
    ) -> PersonalityProfile:
        """Process buffered messages and update the profile."""
        key = self._buffer_key(user_id, chat_id)
        features_batch = self._message_buffers.pop(key, [])
        phrases_batch = self._phrase_buffers.pop(key, [])

        if not features_batch:
            return self.storage.get_or_create_profile(user_id, chat_id, username, display_name)

        profile = self.storage.get_or_create_profile(user_id, chat_id, username, display_name)

        # Update display info
        if username:
            profile.username = username
        if display_name:
            profile.display_name = display_name

        # Update message count
        batch_size = len(features_batch)
        profile.total_messages_analyzed += batch_size

        # Update style metrics with EMA
        self._update_style_metrics(profile, features_batch)

        # Update vocabulary
        self._update_vocabulary(profile, features_batch)

        # Update phrases
        self._update_phrases(profile, phrases_batch)

        # Update emoji frequencies
        self._update_emoji(profile, features_batch)

        # Update filler words and abbreviations
        self._update_informal_language(profile, features_batch)

        # Update topic affinities
        self._update_topics(profile, features_batch)

        # Update temporal patterns
        self._update_temporal(profile, features_batch)

        # Update response behavior
        self._update_behavior(profile, features_batch)

        # Save updated profile
        self.storage.save_profile(profile)
        logger.info(
            f"Updated profile for {display_name} ({user_id}) - "
            f"now {profile.total_messages_analyzed} messages analyzed"
        )
        return profile

    def _ema(self, old_val: float, new_val: float) -> float:
        """Calculate exponential moving average."""
        return old_val * (1 - self._ema_alpha) + new_val * self._ema_alpha

    def _update_style_metrics(self, profile: PersonalityProfile, batch: list[MessageFeatures]) -> None:
        """Update writing style metrics."""
        n = len(batch)
        if n == 0:
            return

        # Calculate batch averages
        avg_msg_len = sum(f.char_count for f in batch) / n
        avg_word_len = sum(f.avg_word_length for f in batch) / n
        avg_sent_len = sum(f.word_count / max(1, f.sentence_count) for f in batch) / n
        cap_ratio = sum(f.capitalization_ratio for f in batch) / n
        punct_density = sum(f.punctuation_count / max(1, f.char_count) for f in batch) / n
        question_ratio = sum(1 for f in batch if f.is_question) / n
        exclamation_ratio = sum(1 for f in batch if f.is_exclamation) / n
        ellipsis_ratio = sum(1 for f in batch if f.has_ellipsis) / n

        style = profile.style
        if profile.total_messages_analyzed <= len(batch):
            # First batch - set directly
            style.avg_message_length = avg_msg_len
            style.avg_word_length = avg_word_len
            style.avg_sentence_length = avg_sent_len
            style.capitalization_ratio = cap_ratio
            style.punctuation_density = punct_density
            style.question_ratio = question_ratio
            style.exclamation_ratio = exclamation_ratio
            style.ellipsis_usage = ellipsis_ratio
        else:
            # Subsequent batches - use EMA
            style.avg_message_length = self._ema(style.avg_message_length, avg_msg_len)
            style.avg_word_length = self._ema(style.avg_word_length, avg_word_len)
            style.avg_sentence_length = self._ema(style.avg_sentence_length, avg_sent_len)
            style.capitalization_ratio = self._ema(style.capitalization_ratio, cap_ratio)
            style.punctuation_density = self._ema(style.punctuation_density, punct_density)
            style.question_ratio = self._ema(style.question_ratio, question_ratio)
            style.exclamation_ratio = self._ema(style.exclamation_ratio, exclamation_ratio)
            style.ellipsis_usage = self._ema(style.ellipsis_usage, ellipsis_ratio)

    def _update_vocabulary(self, profile: PersonalityProfile, batch: list[MessageFeatures]) -> None:
        """Update the user's vocabulary fingerprint."""
        # Count words in this batch
        word_counter = Counter()
        for features in batch:
            word_counter.update(features.words)

        # Merge with existing top words
        existing = Counter(profile.top_words)
        for word, count in word_counter.items():
            # Normalize count to a frequency-like score
            existing[word] = existing.get(word, 0) + count

        # Keep only top N words
        top_n = self.config.max_vocab_size
        profile.top_words = dict(existing.most_common(top_n))

    def _update_phrases(self, profile: PersonalityProfile, phrases: list[str]) -> None:
        """Update distinctive phrases."""
        if not phrases:
            return

        phrase_counter = Counter(phrases)
        # Keep phrases that appear multiple times (more distinctive)
        existing_phrases = Counter({p: 1 for p in profile.unique_phrases})
        for phrase, count in phrase_counter.items():
            if count >= 2:  # Must appear at least twice to be considered a pattern
                existing_phrases[phrase] = existing_phrases.get(phrase, 0) + count

        # Keep top phrases
        top_phrases = existing_phrases.most_common(self.config.max_phrases_tracked)
        profile.unique_phrases = [p for p, _ in top_phrases]

    def _update_emoji(self, profile: PersonalityProfile, batch: list[MessageFeatures]) -> None:
        """Update emoji usage patterns."""
        emoji_counter = Counter()
        total_emojis = 0
        for features in batch:
            for emoji_group in features.emoji_list:
                for char in emoji_group:
                    emoji_counter[char] += 1
                    total_emojis += 1

        # Merge with existing
        existing = Counter(profile.emoji_frequencies)
        existing.update(emoji_counter)

        # Keep top emojis
        profile.emoji_frequencies = dict(existing.most_common(self.config.max_emoji_tracked))

        # Update emoji per message rate
        batch_rate = total_emojis / max(1, len(batch))
        if profile.total_messages_analyzed <= len(batch):
            profile.emoji_per_message = batch_rate
        else:
            profile.emoji_per_message = self._ema(profile.emoji_per_message, batch_rate)

    def _update_informal_language(self, profile: PersonalityProfile, batch: list[MessageFeatures]) -> None:
        """Update slang and abbreviation tracking."""
        filler_counter = Counter()
        abbrev_counter = Counter()

        for features in batch:
            filler_counter.update(features.filler_words_used)
            abbrev_counter.update(features.abbreviations_used)

        # Merge fillers
        existing_fillers = Counter(profile.filler_words)
        existing_fillers.update(filler_counter)
        profile.filler_words = dict(existing_fillers.most_common(30))

        # Merge slang (fillers are also slang)
        existing_slang = Counter(profile.slang_terms)
        existing_slang.update(filler_counter)
        profile.slang_terms = dict(existing_slang.most_common(50))

        # Merge abbreviations
        existing_abbrev = Counter(profile.abbreviations)
        existing_abbrev.update(abbrev_counter)
        profile.abbreviations = dict(existing_abbrev.most_common(30))

    def _update_topics(self, profile: PersonalityProfile, batch: list[MessageFeatures]) -> None:
        """Update topic affinity scores."""
        topic_counter = Counter()
        for features in batch:
            for topic in features.topics_detected:
                topic_counter[topic] += 1

        if not topic_counter:
            return

        # Normalize to 0-1 scale and merge with EMA
        n = len(batch)
        for topic, count in topic_counter.items():
            new_score = count / n
            old_score = profile.topic_affinities.get(topic, 0.0)
            if old_score == 0.0:
                profile.topic_affinities[topic] = new_score
            else:
                profile.topic_affinities[topic] = self._ema(old_score, new_score)

        # Decay topics not seen in this batch
        for topic in list(profile.topic_affinities.keys()):
            if topic not in topic_counter:
                profile.topic_affinities[topic] *= 0.95  # Slow decay
                if profile.topic_affinities[topic] < 0.01:
                    del profile.topic_affinities[topic]

    def _update_temporal(self, profile: PersonalityProfile, batch: list[MessageFeatures]) -> None:
        """Update activity timing patterns."""
        for features in batch:
            hour_key = str(features.hour_of_day)
            day_key = str(features.day_of_week)
            profile.active_hours[hour_key] = profile.active_hours.get(hour_key, 0) + 1
            profile.active_days[day_key] = profile.active_days.get(day_key, 0) + 1

    def _update_behavior(self, profile: PersonalityProfile, batch: list[MessageFeatures]) -> None:
        """Update conversational behavior metrics."""
        n = len(batch)
        reply_count = sum(1 for f in batch if f.is_reply)
        starter_ratio = 1.0 - (reply_count / max(1, n))

        if profile.total_messages_analyzed <= n:
            profile.conversation_starter_ratio = starter_ratio
        else:
            profile.conversation_starter_ratio = self._ema(
                profile.conversation_starter_ratio, starter_ratio
            )

    def force_flush(self, user_id: int, chat_id: int, username: str = "", display_name: str = "") -> Optional[PersonalityProfile]:
        """Force flush the buffer for a user (e.g., when profile is requested)."""
        key = self._buffer_key(user_id, chat_id)
        if key in self._message_buffers and self._message_buffers[key]:
            return self._flush_buffer(user_id, chat_id, username, display_name)
        return None

    def get_profile_for_generation(self, user_id: int, chat_id: int) -> Optional[dict]:
        """
        Get a profile formatted for use in LLM prompting.

        Returns a dict with key personality traits formatted as natural language
        that can be injected into a system prompt.
        """
        profile = self.storage.load_profile(user_id, chat_id)
        if profile is None or profile.total_messages_analyzed < self.config.min_messages_for_profile:
            return None

        # Build a description of their style
        style_desc = []

        # Message length preference
        if profile.style.avg_message_length < 30:
            style_desc.append("writes very short, concise messages")
        elif profile.style.avg_message_length < 80:
            style_desc.append("writes medium-length messages")
        else:
            style_desc.append("tends to write longer, detailed messages")

        # Capitalization
        if profile.style.capitalization_ratio < 0.05:
            style_desc.append("never capitalizes (all lowercase)")
        elif profile.style.capitalization_ratio > 0.3:
            style_desc.append("USES CAPS FREQUENTLY")

        # Punctuation style
        if profile.style.punctuation_density < 0.02:
            style_desc.append("rarely uses punctuation")
        elif profile.style.punctuation_density > 0.1:
            style_desc.append("uses lots of punctuation!!!")

        # Question tendency
        if profile.style.question_ratio > 0.3:
            style_desc.append("asks lots of questions")

        # Emoji usage
        if profile.emoji_per_message > 2:
            style_desc.append("uses emojis heavily")
        elif profile.emoji_per_message > 0.5:
            style_desc.append("occasionally uses emojis")
        else:
            style_desc.append("rarely uses emojis")

        # Ellipsis
        if profile.style.ellipsis_usage > 0.2:
            style_desc.append("frequently uses '...' (ellipsis)")

        return {
            "user_id": profile.user_id,
            "username": profile.username,
            "display_name": profile.display_name,
            "style_description": "; ".join(style_desc),
            "top_words": list(profile.top_words.keys())[:30],
            "favorite_emojis": list(profile.emoji_frequencies.keys())[:10],
            "slang_terms": list(profile.slang_terms.keys())[:20],
            "abbreviations": list(profile.abbreviations.keys())[:15],
            "filler_words": list(profile.filler_words.keys())[:10],
            "unique_phrases": profile.unique_phrases[:20],
            "topic_interests": list(profile.topic_affinities.keys()),
            "messages_analyzed": profile.total_messages_analyzed,
            "avg_message_length": profile.style.avg_message_length,
            "capitalization_ratio": profile.style.capitalization_ratio,
            "question_ratio": profile.style.question_ratio,
        }
