"""
Shared LLM call helpers used by AdvisorAgent, MatchAgent and CampaignCoordinator.

Why this module exists
-----------------------
All three agents were independently calling `client.chat.completions.create(...)`
and then hand-parsing the JSON response with near-identical (and slightly
inconsistent) code. That duplication made the codebase harder to reason about
and meant a fix in one place silently didn't apply to the others.

This module is the single place that:
1. Calls the model with automatic retries + exponential backoff on transient
   failures (rate limits, timeouts, connection errors, 5xx) — this is what
   actually backs the "handles retries" claim in the architecture docs.
2. Robustly parses model output that is supposed to be JSON but may be wrapped
   in markdown fences, use smart quotes, Python literals (True/False/None), or
   have a trailing comma.
3. Falls back to a caller-supplied default dict if parsing ultimately fails,
   so a single bad model response degrades gracefully instead of throwing.
"""

import asyncio
import json
import logging
import re
from typing import Any, Optional

import openai
from openai import AsyncOpenAI

logger = logging.getLogger("creator_collab.llm")

# Transient errors worth retrying. Anything else (bad request, auth, content
# filter) is treated as permanent and surfaces immediately via the fallback.
RETRYABLE_EXCEPTIONS = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)


def safe_json_parse(text: Any) -> dict:
    """Best-effort parse of model output into a dict.

    Handles the common ways small/fast models deviate from "valid JSON only":
    markdown code fences, smart quotes, Python-style booleans/None, and
    trailing commas. Returns {"error": ..., "raw_text": ...} on failure so
    callers can fall back without raising.
    """
    if text is None:
        return {"error": "Empty response from model", "raw_text": None}
    if not isinstance(text, (str, bytes, bytearray)):
        return {"error": f"Unexpected response type: {type(text).__name__}", "raw_text": str(text)}
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="ignore")
    if not text.strip():
        return {"error": "Empty response from model", "raw_text": text}

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    repaired = cleaned
    repaired = repaired.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    repaired = re.sub(r"\bTrue\b", "true", repaired)
    repaired = re.sub(r"\bFalse\b", "false", repaired)
    repaired = re.sub(r"\bNone\b", "null", repaired)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)

    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        return {"error": "Failed to parse JSON from model output", "parse_error": str(e), "raw_text": text}


def safe_score(value: Any) -> float:
    """Coerce a model-provided score to float, defaulting to 0.0 on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def call_json_model(
    client: AsyncOpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    fallback: dict,
    max_tokens: int = 1200,
    max_retries: int = 2,
    base_delay: float = 1.0,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> dict:
    """Call the chat completion API and return a parsed JSON dict.

    Retries transient failures (rate limits, timeouts, connection errors,
    5xx) with exponential backoff. Permanent failures (bad request, auth,
    malformed output that still fails to parse after retries) fall back to
    a copy of `fallback` with diagnostic fields attached, so the caller can
    keep going instead of crashing the whole pipeline.

    `semaphore`, if provided, bounds how many of these calls run concurrently
    — agents use this to parallelize independent sub-analyses without
    overwhelming the API with bursts of simultaneous requests.
    """

    async def _do_call() -> Any:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )
        try:
            return response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            return ""

    last_error: Optional[Exception] = None
    result_text = ""

    for attempt in range(max_retries + 1):
        try:
            if semaphore is not None:
                async with semaphore:
                    result_text = await _do_call()
            else:
                result_text = await _do_call()
            last_error = None
            break
        except RETRYABLE_EXCEPTIONS as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Transient LLM error (%s), retrying in %.1fs [attempt %d/%d]",
                    type(e).__name__, delay, attempt + 1, max_retries,
                )
                await asyncio.sleep(delay)
            continue
        except Exception as e:
            # Non-retryable (bad request, auth, content filter, etc.)
            last_error = e
            break

    if last_error is not None:
        result = dict(fallback)
        result["error"] = f"Model call failed after retries: {last_error}"
        return result

    parsed = safe_json_parse(result_text)
    if not isinstance(parsed, dict):
        result = dict(fallback)
        result["error"] = "Parsed output was not a JSON object"
        result["raw_text"] = result_text
        return result
    if parsed.get("error"):
        result = dict(fallback)
        result["parse_error"] = parsed.get("error")
        result["raw_text"] = parsed.get("raw_text")
        return result
    return parsed
