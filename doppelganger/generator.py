"""
Response Generator for Doppelganger Bot.

Generates text that mimics a specific user's writing style by constructing
detailed prompts from their personality profile and sending them to an LLM.
Supports OpenAI, Anthropic, and any OpenAI-compatible API.
"""

import random
import logging
from typing import Optional
import httpx

from .config import LLMConfig, BotConfig
from .personality import PersonalityEngine
from .storage import ProfileStorage

logger = logging.getLogger(__name__)


IMPERSONATION_SYSTEM_PROMPT = """You are an AI that perfectly mimics a specific person's writing style in a group chat. \
You will be given a detailed personality profile and must generate a message that sounds EXACTLY like them.

RULES:
- Match their capitalization habits precisely
- Use their vocabulary, slang, and abbreviations naturally
- Match their typical message length
- Include their favorite emojis at the same frequency they would
- Use their filler words and phrases
- Match their punctuation style
- Stay in character completely - you ARE this person typing in a chat
- Never break character or acknowledge you're an AI
- Keep it natural and conversational
- One message only, no quotation marks around it"""

ROAST_SYSTEM_PROMPT = """You are a witty roast comedian in a group chat. You've been given a detailed personality profile of someone, \
and you need to roast them IN THEIR OWN WRITING STYLE. The roast should:

RULES:
- Be written exactly how THEY would write (their capitalization, slang, emojis, etc.)
- Make fun of their most distinctive traits and habits
- Reference their topic interests and vocabulary quirks
- Be funny but not genuinely mean or hurtful
- Feel like self-deprecating humor they'd actually write
- One message only, keep it concise and punchy
- No quotation marks around the message"""


class ResponseGenerator:
    """Generates responses mimicking a specific user's style using LLM APIs."""

    def __init__(self, llm_config: LLMConfig, personality_engine: PersonalityEngine):
        self.config = llm_config
        self.engine = personality_engine
        self._client = httpx.AsyncClient(timeout=30.0)

    async def generate_impersonation(
        self, user_id: int, chat_id: int, topic: Optional[str] = None, context: Optional[str] = None
    ) -> Optional[str]:
        """Generate a message that mimics the target user's style."""
        profile_data = self.engine.get_profile_for_generation(user_id, chat_id)
        if profile_data is None:
            return None

        user_prompt = self._build_impersonation_prompt(profile_data, topic, context)
        response = await self._call_llm(IMPERSONATION_SYSTEM_PROMPT, user_prompt)
        return self._clean_response(response)

    async def generate_roast(self, user_id: int, chat_id: int) -> Optional[str]:
        """Generate a roast of the target user written in their own style."""
        profile_data = self.engine.get_profile_for_generation(user_id, chat_id)
        if profile_data is None:
            return None

        user_prompt = self._build_roast_prompt(profile_data)
        response = await self._call_llm(ROAST_SYSTEM_PROMPT, user_prompt)
        return self._clean_response(response)

    def _build_impersonation_prompt(self, profile: dict, topic: Optional[str], context: Optional[str]) -> str:
        """Build the user prompt for impersonation."""
        lines = [
            f"## Target Person: {profile['display_name']} (@{profile['username']})",
            f"",
            f"## Writing Style Analysis (based on {profile['messages_analyzed']} messages):",
            f"- Style: {profile['style_description']}",
            f"- Average message length: ~{profile['avg_message_length']:.0f} characters",
            f"- Capitalization ratio: {profile['capitalization_ratio']:.1%}",
            f"- Question frequency: {profile['question_ratio']:.1%}",
            f"",
            f"## Vocabulary & Language:",
            f"- Frequently used words: {', '.join(profile['top_words'][:20])}",
            f"- Slang/informal: {', '.join(profile['slang_terms'][:15])}",
            f"- Abbreviations: {', '.join(profile['abbreviations'][:10])}",
            f"- Filler words: {', '.join(profile['filler_words'][:8])}",
            f"- Distinctive phrases: {', '.join(profile['unique_phrases'][:10])}",
            f"",
            f"## Emojis: {' '.join(profile['favorite_emojis'][:8])}",
            f"## Topics they care about: {', '.join(profile['topic_interests'])}",
        ]

        if topic:
            lines.append(f"\n## Generate a message about: {topic}")
        else:
            # Pick a random topic they like
            if profile["topic_interests"]:
                random_topic = random.choice(profile["topic_interests"])
                lines.append(f"\n## Generate a casual message about: {random_topic}")
            else:
                lines.append("\n## Generate a casual message about anything they'd naturally talk about")

        if context:
            lines.append(f"\n## Recent chat context (respond to this naturally):\n{context}")

        lines.append("\nNow write ONE message as this person would. Match their style exactly.")
        return "\n".join(lines)

    def _build_roast_prompt(self, profile: dict) -> str:
        """Build the user prompt for roasting."""
        lines = [
            f"## Person to Roast: {profile['display_name']} (@{profile['username']})",
            f"",
            f"## Their Writing Style (roast must be written in THIS style):",
            f"- {profile['style_description']}",
            f"- Average message length: ~{profile['avg_message_length']:.0f} characters",
            f"",
            f"## Their Vocabulary (use THESE words/style in the roast):",
            f"- Common words: {', '.join(profile['top_words'][:20])}",
            f"- Slang: {', '.join(profile['slang_terms'][:15])}",
            f"- Abbreviations: {', '.join(profile['abbreviations'][:10])}",
            f"- Phrases: {', '.join(profile['unique_phrases'][:10])}",
            f"- Emojis: {' '.join(profile['favorite_emojis'][:8])}",
            f"",
            f"## Roastable Traits:",
            f"- Topics they won't shut up about: {', '.join(profile['topic_interests'])}",
            f"- They use these filler words constantly: {', '.join(profile['filler_words'][:8])}",
            f"- Capitalization habit: {'never capitalizes' if profile['capitalization_ratio'] < 0.05 else 'normal caps' if profile['capitalization_ratio'] < 0.3 else 'CAPS ABUSER'}",
            f"- Messages analyzed: {profile['messages_analyzed']} (they talk A LOT)" if profile["messages_analyzed"] > 500 else f"- Messages analyzed: {profile['messages_analyzed']}",
        ]

        lines.append("\nWrite a funny roast of this person, written IN THEIR OWN WRITING STYLE. One message.")
        return "\n".join(lines)

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call the configured LLM API."""
        try:
            if self.config.provider == "anthropic":
                return await self._call_anthropic(system_prompt, user_prompt)
            else:
                # OpenAI and all compatible APIs
                return await self._call_openai_compatible(system_prompt, user_prompt)
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return None

    async def _call_openai_compatible(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call OpenAI or any compatible API."""
        base_url = self.config.api_base or "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _call_anthropic(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call Anthropic's Claude API."""
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": self.config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
        }

        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    def _clean_response(self, response: Optional[str]) -> Optional[str]:
        """Clean up the LLM response."""
        if not response:
            return None

        # Remove surrounding quotes if the LLM added them
        text = response.strip()
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            text = text[1:-1]

        # Remove any "As [name]:" prefixes the LLM might add
        if ":" in text[:50]:
            potential_prefix = text.split(":", 1)[0].lower()
            skip_prefixes = ["as", "me", "response", "message", "reply"]
            if any(p in potential_prefix for p in skip_prefixes):
                text = text.split(":", 1)[1].strip()

        return text

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
