import json

import pytest

from backend.voice_commands.commands import detect_summary_request, handle_summary_request


class DummyMemory:
    def __init__(self):
        self.called = False

    def force_session_summary(self, uuid, source):
        self.called = True
        return True


class DummySender:
    def __init__(self):
        self.sent = []

    def __call__(self, event):
        self.sent.append(event)


def test_detect_summary_request_positive():
    assert detect_summary_request("Can you summarize our discussion?")


def test_detect_summary_request_negative():
    assert not detect_summary_request("Hello, how are you?")


def test_handle_summary_request_triggers_and_confirms():
    mem = DummyMemory()
    sender = DummySender()
    handled = handle_summary_request(
        "Please summarize our chat.",
        mem,
        user_uuid="u123",
        send_json=sender,
        modalities=["text"],
        confirmation_text="Done!",
        error_text="Oops!",
    )
    assert handled is True
    assert mem.called is True
    # Should have sent a system message and a resume event
    types = {evt.get("type") for evt in sender.sent}
    assert "conversation.item.create" in types
    assert "response.create" in types


def test_handle_summary_request_no_trigger():
    mem = DummyMemory()
    sender = DummySender()
    handled = handle_summary_request(
        "Just chatting.",
        mem,
        user_uuid="u123",
        send_json=sender,
    )
    assert handled is False
    assert mem.called is False
    assert sender.sent == []