"""Test suite for Wolo."""

import tempfile
from pathlib import Path

import pytest

from wolo.session import (
    TextPart,
    ToolPart,
    add_assistant_message,
    add_user_message,
    create_session,
    create_subsession,
    find_last_assistant_message,
    find_last_user_message,
    get_pending_tool_calls,
    get_session_messages,
    get_session_mode,
    has_pending_tool_calls,
    update_session_mode,
)


class TestSessionManagement:
    """Test session management functionality."""

    def test_create_session(self):
        """Test creating a new session."""
        session_id = create_session()
        assert session_id is not None
        assert len(session_id) > 0

    def test_add_user_message(self):
        """Test adding a user message."""
        session_id = create_session()
        message = add_user_message(session_id, "Hello, world!")

        assert message is not None
        assert message.role == "user"
        assert len(message.parts) == 1
        assert isinstance(message.parts[0], TextPart)
        assert message.parts[0].text == "Hello, world!"

    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        session_id = create_session()
        message = add_assistant_message(session_id)

        assert message is not None
        assert message.role == "assistant"
        assert message.parts == []

    def test_get_session_messages(self):
        """Test retrieving all messages from a session."""
        session_id = create_session()
        add_user_message(session_id, "Test message 1")
        add_user_message(session_id, "Test message 2")

        messages = get_session_messages(session_id)
        assert len(messages) == 2

    def test_find_last_user_message(self):
        """Test finding the last user message."""
        session_id = create_session()
        add_user_message(session_id, "First")
        add_user_message(session_id, "Last")

        messages = get_session_messages(session_id)
        last = find_last_user_message(messages)
        assert last is not None
        assert last.parts[0].text == "Last"

    def test_find_last_assistant_message(self):
        """Test finding the last assistant message."""
        session_id = create_session()
        add_user_message(session_id, "User message")
        msg1 = add_assistant_message(session_id)
        msg1.parts.append(TextPart(text="Response 1"))
        msg2 = add_assistant_message(session_id)
        msg2.parts.append(TextPart(text="Response 2"))

        messages = get_session_messages(session_id)
        last = find_last_assistant_message(messages)
        assert last is not None
        assert last.parts[0].text == "Response 2"

    def test_tool_parts(self):
        """Test tool parts in messages."""
        session_id = create_session()
        msg = add_assistant_message(session_id)

        tool_part = ToolPart(tool="test_tool", input={"param": "value"})
        msg.parts.append(tool_part)

        assert has_pending_tool_calls(msg)
        pending = get_pending_tool_calls(msg)
        assert len(pending) == 1
        assert pending[0].tool == "test_tool"

    def test_create_subsession(self):
        """Test creating subsessions."""
        parent_id = create_session()
        add_user_message(parent_id, "Parent task")

        child_id = create_subsession(parent_id, "explore")
        assert child_id != parent_id

        child_messages = get_session_messages(child_id)
        parent_messages = get_session_messages(parent_id)

        # Parent has message, child doesn't yet
        assert len(parent_messages) == 1
        assert len(child_messages) == 0


class TestMessageParts:
    """Test message part types."""

    def test_text_part(self):
        """Test TextPart creation."""
        part = TextPart(text="Hello")
        assert part.type == "text"
        assert part.text == "Hello"
        assert part.id is not None

    def test_tool_part(self):
        """Test ToolPart creation."""
        part = ToolPart(tool="read", input={"file_path": "test.txt"})
        assert part.type == "tool"
        assert part.tool == "read"
        assert part.input == {"file_path": "test.txt"}
        assert part.status == "pending"
        assert part.output == ""

    def test_tool_part_status_update(self):
        """Test updating tool part status."""
        part = ToolPart(tool="read", input={"file_path": "test.txt"})
        part.status = "completed"
        part.output = "File content here"

        assert part.status == "completed"
        assert part.output == "File content here"


class TestSessionPersistence:
    """Test session save/load functionality."""

    def test_save_and_load_session(self):
        """Test saving and loading a session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from wolo.session import load_session, save_session

            # Override sessions directory
            original_sessions = Path(tmpdir)

            session_id = create_session()
            add_user_message(session_id, "Test persistence")
            add_assistant_message(session_id).parts.append(TextPart(text="Response"))

            save_session(session_id, sessions_dir=original_sessions)

            # Clear in-memory session
            from wolo.session import _sessions

            if session_id in _sessions:
                del _sessions[session_id]

            # Load session
            loaded = load_session(session_id, sessions_dir=original_sessions)
            messages = loaded.get_messages()

            assert len(messages) == 2
            assert messages[0].role == "user"
            assert messages[1].role == "assistant"


class TestExecutionMode:
    """Test execution mode persistence functionality."""

    def test_default_mode_is_solo(self):
        """Test that new sessions default to solo mode."""
        session_id = create_session()
        mode = get_session_mode(session_id)
        assert mode == "solo"

    def test_update_session_mode(self):
        """Test updating session execution mode."""
        session_id = create_session()

        # Update to coop
        update_session_mode(session_id, "coop")
        mode = get_session_mode(session_id)
        assert mode == "coop"

        # Update to repl
        update_session_mode(session_id, "repl")
        mode = get_session_mode(session_id)
        assert mode == "repl"

    def test_mode_persists_after_save_load(self):
        """Test that execution mode persists after save/load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from wolo.session import _sessions, load_session, save_session

            original_sessions = Path(tmpdir)

            session_id = create_session()
            update_session_mode(session_id, "coop")

            save_session(session_id, sessions_dir=original_sessions)

            # Clear in-memory session
            if session_id in _sessions:
                del _sessions[session_id]

            # Load session and verify mode persisted
            loaded = load_session(session_id, sessions_dir=original_sessions)
            assert loaded.execution_mode == "coop"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
