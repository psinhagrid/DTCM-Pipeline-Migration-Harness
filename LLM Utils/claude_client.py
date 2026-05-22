import os
from anthropic import Anthropic
from anthropic.types import Message
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODELS = {
    "smart": os.getenv("SMART_MODEL", "claude-sonnet-4-6"),
    "fast": os.getenv("FAST_MODEL", "claude-haiku-4-5-20251001"),
}

_mode = os.getenv("MODE", "smart").lower()


def set_mode(mode: str) -> None:
    """Toggle between 'smart' (Sonnet) and 'fast' (Haiku) modes."""
    global _mode
    if mode not in MODELS:
        raise ValueError(f"Invalid mode '{mode}'. Choose 'smart' or 'fast'.")
    _mode = mode
    print(f"Mode set to '{mode}' → {MODELS[mode]}")


def get_mode() -> str:
    """Return the current mode."""
    return _mode


def call_claude(
    messages: list[dict],
    system: str = "",
    tools: list[dict] = None,
    mode: str = None,
) -> Message:
    """Send messages to Claude and return the response message.

    Args:
        messages: Conversation messages.
        system: Optional system prompt.
        tools: Optional tool definitions.
        mode: Override mode for this call ('smart' or 'fast'). Uses current mode if omitted.
    """
    active_mode = mode if mode is not None else _mode
    if active_mode not in MODELS:
        raise ValueError(f"Invalid mode '{active_mode}'. Choose 'smart' or 'fast'.")

    kwargs = {
        "model": MODELS[active_mode],
        "max_tokens": 8096,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools

    return client.messages.create(**kwargs)
