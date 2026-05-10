"""
AI engine — LLM client and response generation.

Provides a provider-agnostic interface to any OpenAI-compatible API.
Handles prompt construction, API calls, retries, and response parsing.
"""

import json
import logging
import random
from typing import Any, Optional

import httpx

from doppelganger.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
)
from doppelganger.ai.prompts import (
    build_response_prompt,
    build_profile_extraction_prompt,
    build_impersonation_prompt,
    build_silence_breaker_prompt,
)

logger = logging.getLogger("doppelganger.ai.engine")

# HTTP client timeout for LLM requests (some models need longer)
_LLM_TIMEOUT = 120.0


async def _call_llm(
    messages: list[dict[str, str]],
    max_tokens: int = LLM_MAX_TOKENS,
    temperature: float = LLM_TEMPERATURE,
) -> Optional[str]:
    """Send a chat completion request to the LLM provider.

    Args:
        messages: List of message dicts with 'role' and 'content'.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0 = deterministic, 2.0 = creative).

    Returns:
        The assistant's response text, or None on failure.
    """
    try:
        logger.debug(
            f"LLM call: model={LLM_MODEL}, max_tokens={max_tokens}, temp={temperature}"
        )

        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
            response = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )

        if response.status_code != 200:
            logger.error(
                f"LLM HTTP {response.status_code}: {response.text[:500]}"
            )
            return None

        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not content:
            usage = data.get("usage", {})
            logger.warning(
                f"LLM returned empty content despite {usage.get('completion_tokens', '?')} tokens"
            )
            return None

        # Log usage stats
        usage = data.get("usage", {})
        finish = data["choices"][0].get("finish_reason", "unknown")
        logger.debug(
            f"LLM response: {len(content)} chars, "
            f"finish={finish}, tokens={usage.get('total_tokens', '?')}"
        )

        return content

    except httpx.TimeoutException:
        logger.error("LLM request timed out")
        return None
    except Exception:
        logger.exception("LLM request failed")
        return None


def _format_messages_context(messages: list[dict[str, Any]]) -> str:
    """Format recent messages into a readable string for prompts.

    Args:
        messages: List of message dicts from the tracker.

    Returns:
        Formatted multi-line string of recent messages.
    """
    lines = []
    for msg in messages[-30:]:
        name = msg.get("name", "Unknown")
        text = msg.get("text", "")
        lines.append(f"{name}: {text}")
    return "\n".join(lines)


async def generate_response(
    profiles_summary: str,
    recent_messages: list[dict[str, Any]],
    trigger_type: str = "random",
    target_user: Optional[str] = None,
) -> Optional[str]:
    """Generate a bot response based on conversation context.

    Args:
        profiles_summary: Formatted summary of all user profiles.
        recent_messages: Recent messages from the conversation tracker.
        trigger_type: What triggered the response (random, mentioned, reply, roast).
        target_user: The user name who triggered the bot, if applicable.

    Returns:
        Generated response text, or None on failure.
    """
    messages_context = _format_messages_context(recent_messages)

    system_prompt, user_prompt = build_response_prompt(
        profiles_summary=profiles_summary,
        messages_context=messages_context,
        trigger_type=trigger_type,
        target_user=target_user,
    )

    return await _call_llm(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
    )


async def generate_impersonation(
    profile: dict[str, Any],
    recent_messages: list[dict[str, Any]],
) -> Optional[str]:
    """Generate a message impersonating a specific user.

    Args:
        profile: The target user's personality profile.
        recent_messages: Recent messages for conversational context.

    Returns:
        Generated impersonation text, or None on failure.
    """
    messages_context = _format_messages_context(recent_messages)

    system_prompt, user_prompt = build_impersonation_prompt(
        profile=profile,
        messages_context=messages_context,
    )

    return await _call_llm(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
    )


async def extract_profile_updates(
    current_profile: dict[str, Any],
    new_message: str,
    context_messages: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Extract personality profile updates from recent messages.

    Uses LLM to analyze messages and identify new personality traits,
    interests, speech patterns, and roast material.

    Args:
        current_profile: The user's current profile data.
        new_message: The latest message from the user.
        context_messages: Recent chat messages for context.

    Returns:
        Dict of profile field updates, or None on failure.
    """
    context = "\n".join(
        f"{msg['name']}: {msg['text']}"
        for msg in context_messages[-20:]
    )

    system_prompt, user_prompt = build_profile_extraction_prompt(
        profile=current_profile,
        new_message=new_message,
        context=context,
    )

    try:
        result = await _call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=800,
            temperature=0.3,
        )

        if not result:
            return None

        # Strip markdown code fences if present
        cleaned = result.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (possibly with language tag)
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        return json.loads(cleaned)

    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to parse profile update JSON: {exc}")
        return None
    except Exception:
        logger.exception("Profile extraction failed")
        return None


async def generate_silence_breaker(
    profiles_summary: str,
) -> Optional[str]:
    """Generate a message to break chat silence.

    Picks a random conversation-starting topic and generates
    a provocative or engaging message based on known profiles.

    Args:
        profiles_summary: Formatted summary of all user profiles.

    Returns:
        Generated message text, or None on failure.
    """
    topics = [
        "Roast a specific person based on their profile",
        "Ask the group a provocative or controversial question",
        "Bring up a funny fact about someone",
        "Compare two group members in something amusing",
        "Ask for opinions on something debatable",
        "Complain about something relatable and funny",
        "Share a 'breaking news' story about someone in the group",
        "Start a debate about something trivial but passionate",
    ]

    chosen_topic = random.choice(topics)

    system_prompt, user_prompt = build_silence_breaker_prompt(
        profiles_summary=profiles_summary,
        topic_hint=chosen_topic,
    )

    return await _call_llm(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=1.0,
    )
