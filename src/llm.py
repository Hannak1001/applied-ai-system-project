"""Shared Gemini (free tier) helper used by the agent and the explainer.

Every function returns None on any failure (no key, SDK missing, network or
quota error, bad JSON) so callers can fall back to rule-based behavior.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

DEFAULT_MODEL = "gemini-3.5-flash-lite"  # highest free-tier quota; override with GEMINI_MODEL
COOLDOWN_SECONDS = 60

# Set when Gemini reports it is out of quota; calls are skipped until then so
# the app drops straight to its offline fallbacks instead of waiting on errors.
_blocked_until = 0.0
last_error: Optional[str] = None  # short reason for the most recent failure, for the UI


def load_env(path: str = ".env") -> None:
    """Tiny .env reader so we don't need python-dotenv. Existing env vars win."""
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def generate_json(prompt: str) -> Optional[Any]:
    """Send a prompt to Gemini in JSON mode and return the parsed reply."""
    global _blocked_until, last_error
    load_env()
    if time.time() < _blocked_until:
        last_error = "quota cooldown"
        return None
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai  # imported lazily: optional dependency
        from google.genai import types
    except ImportError:
        return None
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta"),  # JSON mode needs v1beta
        )
        response = client.models.generate_content(
            model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        last_error = None
        return json.loads(response.text)
    except Exception as error:
        if "429" in str(error) or "RESOURCE_EXHAUSTED" in str(error):
            _blocked_until = time.time() + COOLDOWN_SECONDS
            last_error = "quota exceeded"
        else:
            last_error = type(error).__name__
        return None
