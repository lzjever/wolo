"""
Comprehensive tests for session persistence.

Tests the layered storage architecture with immediate persistence.
"""

import json
import tempfile
import unittest
from pathlib import Path

from wolo.session import (
    Message,
    SessionStorage,
    TextPart,
    ToolPart,
    _deserialize_message,
    _deserialize_part,
    _serialize_message,
    _serialize_part,
    add_assistant_message,
    add_user_message,
    create_session,
    get_session,
    load_session,
    load_session_todos,
    save_session_todos,
    set_storage,
    update_message,
)


class TestPartSerialization(unittest.TestCase):
    """Test Part serialization and deserialization."""

    def test_text_part_roundtrip(self):
        """TextPart should serialize and deserialize correctly."""
        part = TextPart(id="test-id", text="Hello, world!")

        data = _serialize_part(part)
        restored = _deserialize_part(data)

        self.assertIsInstance(restored, TextPart)
        self.assertEqual(restored.id, "test-id")
        self.assertEqual(restored.text, "Hello, world!")
        self.assertEqual(restored.type, "text")

    def test_tool_part_roundtrip_with_output_and_status(self):
        """ToolPart should preserve output and status after roundtrip."""
        part = ToolPart(
            id="tool-id",
            tool="shell",
            input={"command": "ls -la"},
            output="file1.txt\nfile2.txt",
            status="completed",
        )
        part.start_time = 1000.0
        part.end_time = 2000.0

        data = _serialize_part(part)

        # Verify serialization includes all fields
        self.assertEqual(data["output"], "file1.txt\nfile2.txt")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["start_time"], 1000.0)
        self.assertEqual(data["end_time"], 2000.0)

        # Verify deserialization restores all fields
        restored = _deserialize_part(data)

        self.assertIsInstance(restored, ToolPart)
        self.assertEqual(restored.id, "tool-id")
        self.assertEqual(restored.tool, "shell")
        self.assertEqual(restored.input, {"command": "ls -la"})
        self.assertEqual(restored.output, "file1.txt\nfile2.txt")  # ✅ Fixed bug
        self.assertEqual(restored.status, "completed")  # ✅ Fixed bug
        self.assertEqual(restored.start_time, 1000.0)
        self.assertEqual(restored.end_time, 2000.0)

    def test_tool_part_default_values(self):
        """ToolPart should have correct defaults when fields are missing."""
        data = {
            "type": "tool",
            "id": "tool-id",
            "tool": "read",
            "input": {"file_path": "/tmp/test.txt"},
            # Missing: output, status, start_time, end_time
        }

        restored = _deserialize_part(data)

        self.assertEqual(restored.output, "")
        self.assertEqual(restored.status, "pending")
        self.assertEqual(restored.start_time, 0.0)
        self.assertEqual(restored.end_time, 0.0)


class TestMessageSerialization(unittest.TestCase):
    """Test Message serialization and deserialization."""

    def test_message_with_reasoning_content(self):
        """Message should preserve reasoning_content after roundtrip."""
        msg = Message(id="msg-id", role="assistant")
        msg.parts.append(TextPart(text="The answer is 42."))
        msg.reasoning_content = "Let me think about this step by step..."
        msg.finished = True
        msg.finish_reason = "stop"

        data = _serialize_message(msg)

        # Verify serialization includes reasoning_content
        self.assertEqual(data["reasoning_content"], "Let me think about this step by step...")

        # Verify deserialization restores reasoning_content
        restored = _deserialize_message(data)

        self.assertEqual(restored.id, "msg-id")
        self.assertEqual(restored.role, "assistant")
        self.assertEqual(restored.reasoning_content, "Let me think about this step by step...")
        self.assertTrue(restored.finished)
        self.assertEqual(restored.finish_reason, "stop")

    def test_message_with_tool_parts(self):
        """Message with tool parts should serialize correctly."""
        msg = Message(id="msg-id", role="assistant")
        msg.parts.append(TextPart(text="I'll run a command."))

        tool = ToolPart(tool="shell", input={"command": "echo hello"})
        tool.output = "hello"
        tool.status = "completed"
        msg.parts.append(tool)

        data = _serialize_message(msg)
        restored = _deserialize_message(data)

        self.assertEqual(len(restored.parts), 2)

        tool_part = restored.parts[1]
        self.assertIsInstance(tool_part, ToolPart)
        self.assertEqual(tool_part.output, "hello")
        self.assertEqual(tool_part.status, "completed")


class TestSessionStorage(unittest.TestCase):
    """Test SessionStorage class."""

    def setUp(self):
        """Create a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SessionStorage(Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_session(self):
        """Creating a session should create directory structure."""
        session_id = self.storage.create_session()

        session_dir = Path(self.temp_dir) / session_id
        self.assertTrue(session_dir.exists())
        self.assertTrue((session_dir / "session.json").exists())
        self.assertTrue((session_dir / "messages").exists())

    def test_session_metadata(self):
        """Session metadata should be readable and updatable."""
        session_id = self.storage.create_session()

        metadata = self.storage.get_session_metadata(session_id)
        self.assertEqual(metadata["id"], session_id)
        self.assertIsNotNone(metadata["created_at"])

        # Update metadata
        self.storage.update_session_metadata(session_id, title="Test Session")

        metadata = self.storage.get_session_metadata(session_id)
        self.assertEqual(metadata["title"], "Test Session")

    def test_save_and_load_message(self):
        """Messages should be saved and loaded correctly."""
        session_id = self.storage.create_session()

        msg = Message(role="user")
        msg.parts.append(TextPart(text="Hello!"))

        self.storage.save_message(session_id, msg)

        # Verify file exists
        msg_file = Path(self.temp_dir) / session_id / "messages" / f"{msg.id}.json"
        self.assertTrue(msg_file.exists())

        # Load and verify
        loaded = self.storage.get_message(session_id, msg.id)
        self.assertEqual(loaded.id, msg.id)
        self.assertEqual(loaded.role, "user")
        self.assertEqual(len(loaded.parts), 1)
        self.assertEqual(loaded.parts[0].text, "Hello!")

    def test_get_all_messages_sorted(self):
        """get_all_messages should return messages sorted by timestamp."""
        session_id = self.storage.create_session()

        # Create messages with different timestamps
        msg1 = Message(role="user")
        msg1.timestamp = 1000
        msg1.parts.append(TextPart(text="First"))

        msg2 = Message(role="assistant")
        msg2.timestamp = 2000
        msg2.parts.append(TextPart(text="Second"))

        msg3 = Message(role="user")
        msg3.timestamp = 3000
        msg3.parts.append(TextPart(text="Third"))

        # Save in random order
        self.storage.save_message(session_id, msg2)
        self.storage.save_message(session_id, msg3)
        self.storage.save_message(session_id, msg1)

        # Load and verify order
        messages = self.storage.get_all_messages(session_id)
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0].parts[0].text, "First")
        self.assertEqual(messages[1].parts[0].text, "Second")
        self.assertEqual(messages[2].parts[0].text, "Third")

    def test_todos_persistence(self):
        """Todos should be saved and loaded correctly."""
        session_id = self.storage.create_session()

        todos = [
            {"id": "1", "content": "Task 1", "status": "completed"},
            {"id": "2", "content": "Task 2", "status": "in_progress"},
            {"id": "3", "content": "Task 3", "status": "pending"},
        ]

        self.storage.save_todos(session_id, todos)

        # Verify file exists
        todos_file = Path(self.temp_dir) / session_id / "todos.json"
        self.assertTrue(todos_file.exists())

        # Load and verify
        loaded = self.storage.get_todos(session_id)
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0]["status"], "completed")
        self.assertEqual(loaded[1]["status"], "in_progress")

    def test_delete_session(self):
        """Deleting a session should remove all files."""
        session_id = self.storage.create_session()

        # Add some data
        msg = Message(role="user")
        msg.parts.append(TextPart(text="Test"))
        self.storage.save_message(session_id, msg)
        self.storage.save_todos(session_id, [{"id": "1", "content": "Test"}])

        # Delete
        result = self.storage.delete_session(session_id)
        self.assertTrue(result)

        # Verify deleted
        session_dir = Path(self.temp_dir) / session_id
        self.assertFalse(session_dir.exists())

    def test_list_sessions(self):
        """list_sessions should return all sessions with metadata."""
        # Create multiple sessions
        id1 = self.storage.create_session()
        self.storage.update_session_metadata(id1, title="Session 1")

        id2 = self.storage.create_session()
        self.storage.update_session_metadata(id2, title="Session 2")

        # Add a message to session 1
        msg = Message(role="user")
        msg.parts.append(TextPart(text="Test"))
        self.storage.save_message(id1, msg)

        # List sessions
        sessions = self.storage.list_sessions()
        self.assertEqual(len(sessions), 2)

        # Find session 1 and verify message count
        session1 = next(s for s in sessions if s["id"] == id1)
        self.assertEqual(session1["message_count"], 1)


class TestPublicAPI(unittest.TestCase):
    """Test public API functions."""

    def setUp(self):
        """Create a temporary storage."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SessionStorage(Path(self.temp_dir))
        set_storage(self.storage)

    def tearDown(self):
        """Clean up."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        set_storage(None)

    def test_create_and_get_session(self):
        """create_session and get_session should work correctly."""
        session_id = create_session()

        session = get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.id, session_id)

    def test_add_user_message_persists(self):
        """add_user_message should persist immediately."""
        session_id = create_session()

        msg = add_user_message(session_id, "Hello, world!")

        # Verify persisted
        msg_file = Path(self.temp_dir) / session_id / "messages" / f"{msg.id}.json"
        self.assertTrue(msg_file.exists())

        # Verify content
        with open(msg_file) as f:
            data = json.load(f)
        self.assertEqual(data["role"], "user")
        self.assertEqual(data["parts"][0]["text"], "Hello, world!")

    def test_add_assistant_message_persists(self):
        """add_assistant_message should persist immediately."""
        session_id = create_session()

        msg = add_assistant_message(session_id)

        # Verify persisted
        msg_file = Path(self.temp_dir) / session_id / "messages" / f"{msg.id}.json"
        self.assertTrue(msg_file.exists())

    def test_update_message_persists(self):
        """update_message should persist changes."""
        session_id = create_session()

        msg = add_assistant_message(session_id)
        msg.parts.append(TextPart(text="Updated content"))
        msg.finished = True
        msg.finish_reason = "stop"

        update_message(session_id, msg)

        # Reload from disk
        loaded = self.storage.get_message(session_id, msg.id)
        self.assertEqual(len(loaded.parts), 1)
        self.assertEqual(loaded.parts[0].text, "Updated content")
        self.assertTrue(loaded.finished)

    def test_save_and_load_session(self):
        """save_session and load_session should work correctly."""
        session_id = create_session()

        add_user_message(session_id, "Question")
        msg = add_assistant_message(session_id)
        msg.parts.append(TextPart(text="Answer"))

        tool = ToolPart(tool="shell", input={"command": "ls"})
        tool.output = "file.txt"
        tool.status = "completed"
        msg.parts.append(tool)

        msg.reasoning_content = "Thinking..."
        msg.finished = True
        update_message(session_id, msg)

        # Clear in-memory cache
        from wolo.session import _sessions

        _sessions.clear()

        # Load from disk
        loaded_session = load_session(session_id)

        self.assertEqual(len(loaded_session.messages), 2)

        assistant_msg = loaded_session.messages[1]
        self.assertEqual(assistant_msg.reasoning_content, "Thinking...")

        tool_part = assistant_msg.parts[1]
        self.assertEqual(tool_part.output, "file.txt")
        self.assertEqual(tool_part.status, "completed")

    def test_todos_api(self):
        """save_session_todos and load_session_todos should work."""
        session_id = create_session()

        todos = [{"id": "1", "content": "Do something", "status": "pending"}]

        save_session_todos(session_id, todos)
        loaded = load_session_todos(session_id)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["content"], "Do something")


class TestLegacyMigration(unittest.TestCase):
    """Test migration from legacy single-file format."""

    def setUp(self):
        """Create a temporary storage."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SessionStorage(Path(self.temp_dir))
        set_storage(self.storage)

    def tearDown(self):
        """Clean up."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        set_storage(None)

    def test_migrate_legacy_session(self):
        """Loading a legacy session should migrate it to new format."""
        # Create a legacy format session file
        session_id = "legacy-session-123"
        legacy_data = {
            "id": session_id,
            "messages": [
                {
                    "id": "msg-1",
                    "role": "user",
                    "parts": [{"type": "text", "id": "p1", "text": "Hello"}],
                    "timestamp": 1000,
                    "finished": True,
                    "finish_reason": "",
                },
                {
                    "id": "msg-2",
                    "role": "assistant",
                    "parts": [
                        {"type": "text", "id": "p2", "text": "Hi there!"},
                        {
                            "type": "tool",
                            "id": "p3",
                            "tool": "shell",
                            "input": {"command": "ls"},
                            "output": "file.txt",
                            "status": "completed",
                        },
                    ],
                    "timestamp": 2000,
                    "finished": True,
                    "finish_reason": "stop",
                    "reasoning_content": "Let me help...",
                },
            ],
            "created_at": 1000,
            "updated_at": 2000,
            "title": "Legacy Session",
        }

        legacy_file = Path(self.temp_dir) / f"{session_id}.json"
        with open(legacy_file, "w") as f:
            json.dump(legacy_data, f)

        # Load should migrate
        session = load_session(session_id)

        # Verify migration
        self.assertEqual(session.id, session_id)
        self.assertEqual(session.title, "Legacy Session")
        self.assertEqual(len(session.messages), 2)

        # Verify tool part preserved
        tool_part = session.messages[1].parts[1]
        self.assertEqual(tool_part.output, "file.txt")
        self.assertEqual(tool_part.status, "completed")

        # Verify reasoning preserved
        self.assertEqual(session.messages[1].reasoning_content, "Let me help...")

        # Verify legacy file removed
        self.assertFalse(legacy_file.exists())

        # Verify new format exists
        new_dir = Path(self.temp_dir) / session_id
        self.assertTrue(new_dir.exists())
        self.assertTrue((new_dir / "session.json").exists())
        self.assertTrue((new_dir / "messages").exists())


class TestAtomicWrites(unittest.TestCase):
    """Test atomic write operations."""

    def setUp(self):
        """Create a temporary storage."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SessionStorage(Path(self.temp_dir))

    def tearDown(self):
        """Clean up."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_temp_files_left(self):
        """Atomic writes should not leave .tmp files."""
        session_id = self.storage.create_session()

        # Save multiple messages
        for i in range(10):
            msg = Message(role="user")
            msg.parts.append(TextPart(text=f"Message {i}"))
            self.storage.save_message(session_id, msg)

        # Check for .tmp files
        session_dir = Path(self.temp_dir) / session_id
        tmp_files = list(session_dir.rglob("*.tmp"))
        self.assertEqual(len(tmp_files), 0, f"Found temp files: {tmp_files}")


if __name__ == "__main__":
    unittest.main()
