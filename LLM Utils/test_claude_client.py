#!/usr/bin/env python3
"""
Integration tests for claude_client.call_claude.
Requires ANTHROPIC_API_KEY in ../.env or environment.
"""

import pytest
import claude_client
from claude_client import call_claude, set_mode, get_mode, MODELS


# --- mode toggling ---

def test_set_mode_smart():
    set_mode("smart")
    assert get_mode() == "smart"


def test_set_mode_fast():
    set_mode("fast")
    assert get_mode() == "fast"
    set_mode("smart")  # restore


def test_set_mode_invalid():
    with pytest.raises(ValueError):
        set_mode("turbo")


# --- smart mode (Sonnet) ---

def test_basic_call_smart():
    set_mode("smart")
    messages = [{"role": "user", "content": "Say the word PONG and nothing else."}]
    response = call_claude(messages)

    assert response.stop_reason == "end_turn"
    assert "PONG" in response.content[0].text
    assert response.model == MODELS["smart"]


def test_system_prompt():
    messages = [{"role": "user", "content": "What are you?"}]
    response = call_claude(messages, system="You are a calculator. Reply only with numbers.")

    assert response.content[0].text is not None


def test_multi_turn():
    messages = [
        {"role": "user", "content": "My name is Alex."},
        {"role": "assistant", "content": "Nice to meet you, Alex!"},
        {"role": "user", "content": "What is my name?"},
    ]
    response = call_claude(messages)

    assert "Alex" in response.content[0].text


def test_tool_use():
    tools = [
        {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"],
            },
        }
    ]
    messages = [{"role": "user", "content": "What's the weather in Paris?"}]
    response = call_claude(messages, tools=tools)

    assert response.stop_reason == "tool_use"
    tool_block = next(b for b in response.content if b.type == "tool_use")
    assert tool_block.name == "get_weather"
    assert tool_block.input.get("city", "").lower() == "paris"


# --- fast mode (Haiku) ---

def test_basic_call_fast():
    messages = [{"role": "user", "content": "Say the word PONG and nothing else."}]
    response = call_claude(messages, mode="fast")

    assert response.stop_reason == "end_turn"
    assert "PONG" in response.content[0].text
    assert response.model == MODELS["fast"]


def test_per_call_mode_override():
    """mode= on a single call should not change the global mode."""
    set_mode("smart")
    call_claude([{"role": "user", "content": "Hi"}], mode="fast")
    assert get_mode() == "smart"


# --- shared ---

def test_response_has_usage():
    messages = [{"role": "user", "content": "Hi"}]
    response = call_claude(messages)

    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
