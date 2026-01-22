"""
Unit tests for session management improvements:
- Session ID generation
- PID management
- Session conflict detection
- Watch server
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from wolo.session import (
    SessionStorage,
    create_session,
    check_and_set_session_pid,
    clear_session_pid,
    get_session_status,
    list_sessions,
    set_storage,
    get_storage,
    _generate_session_id,
)


class TestSessionIDGeneration(unittest.TestCase):
    """Test session ID generation with agent name and timestamp."""
    
    def test_generate_session_id_format(self):
        """Session ID should be in format: {AgentName}_{YYMMDD}_{HHMMSS}"""
        agent_name = "Albert Einstein"
        session_id = _generate_session_id(agent_name)
        
        # Should remove spaces
        self.assertNotIn(" ", session_id)
        # Should start with sanitized name
        self.assertTrue(session_id.startswith("AlbertEinstein_"))
        # Should have timestamp part
        parts = session_id.split("_")
        self.assertEqual(len(parts), 3)  # name, date, time
        # Date should be 6 digits (YYMMDD)
        self.assertEqual(len(parts[1]), 6)
        # Time should be 6 digits (HHMMSS)
        self.assertEqual(len(parts[2]), 6)
    
    def test_generate_session_id_removes_spaces(self):
        """Session ID should remove all spaces from agent name."""
        agent_name = "Isaac Newton"
        session_id = _generate_session_id(agent_name)
        
        self.assertNotIn(" ", session_id)
        self.assertTrue(session_id.startswith("IsaacNewton_"))
    
    def test_generate_session_id_timestamp_format(self):
        """Timestamp should use 2-digit year."""
        agent_name = "TestAgent"
        session_id = _generate_session_id(agent_name)
        
        # Extract timestamp parts
        parts = session_id.split("_")
        date_part = parts[1]  # YYMMDD
        time_part = parts[2]  # HHMMSS
        
        # Year should be 2 digits (e.g., 26 for 2026)
        year = int(date_part[:2])
        self.assertGreaterEqual(year, 0)
        self.assertLess(year, 100)
        
        # Date should be valid format
        self.assertEqual(len(date_part), 6)
        self.assertEqual(len(time_part), 6)


class TestSessionCreation(unittest.TestCase):
    """Test session creation with new features."""
    
    def setUp(self):
        """Create a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SessionStorage(Path(self.temp_dir))
        set_storage(self.storage)
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        set_storage(None)
    
    def test_create_session_auto_generate_id(self):
        """Creating session without ID should auto-generate from agent name."""
        agent_name = "TestAgent"
        session_id = create_session(agent_name=agent_name)
        
        # Should be in correct format
        self.assertTrue(session_id.startswith("TestAgent_"))
        # Should exist
        self.assertTrue(self.storage.session_exists(session_id))
        # Should have PID fields in metadata
        metadata = self.storage.get_session_metadata(session_id)
        self.assertIn("pid", metadata)
        self.assertIn("pid_updated_at", metadata)
        self.assertIsNone(metadata["pid"])
    
    def test_create_session_manual_id(self):
        """Creating session with manual ID should use that ID."""
        session_id = create_session(session_id="mytask")
        
        self.assertEqual(session_id, "mytask")
        self.assertTrue(self.storage.session_exists("mytask"))
    
    def test_create_session_conflict_detection(self):
        """Creating session with existing ID should raise ValueError."""
        # Create first session
        create_session(session_id="mytask")
        
        # Try to create again with same ID
        with self.assertRaises(ValueError) as cm:
            create_session(session_id="mytask")
        
        self.assertIn("already exists", str(cm.exception).lower())
    
    def test_create_session_auto_generate_without_agent_name(self):
        """Creating session without agent_name should use random agent name."""
        session_id = create_session()
        
        # Should still be valid format (random agent name + timestamp)
        self.assertIsNotNone(session_id)
        self.assertTrue(len(session_id) > 0)
        # Should have underscore separator
        self.assertIn("_", session_id)


class TestPIDManagement(unittest.TestCase):
    """Test PID management for preventing concurrent execution."""
    
    def setUp(self):
        """Create a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SessionStorage(Path(self.temp_dir))
        set_storage(self.storage)
        self.current_pid = os.getpid()
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        set_storage(None)
    
    def test_check_and_set_pid_new_session(self):
        """Setting PID on new session should succeed."""
        session_id = create_session(session_id="test")
        
        result = check_and_set_session_pid(session_id)
        
        self.assertTrue(result)
        metadata = self.storage.get_session_metadata(session_id)
        self.assertEqual(metadata["pid"], self.current_pid)
        self.assertIsNotNone(metadata["pid_updated_at"])
    
    def test_check_and_set_pid_no_existing_pid(self):
        """Setting PID when no existing PID should succeed."""
        session_id = create_session(session_id="test")
        
        result = check_and_set_session_pid(session_id)
        
        self.assertTrue(result)
        metadata = self.storage.get_session_metadata(session_id)
        self.assertEqual(metadata["pid"], self.current_pid)
    
    @patch('psutil.Process')
    def test_check_and_set_pid_running_process(self, mock_process_class):
        """Setting PID when process is running should fail."""
        session_id = create_session(session_id="test")
        
        # Set an existing PID
        self.storage.update_session_metadata(session_id, pid=9999, pid_updated_at=time.time())
        
        # Mock psutil to return running process
        mock_process = MagicMock()
        mock_process.cmdline.return_value = ["python", "-m", "wolo", "test"]
        mock_process.is_running.return_value = True
        mock_process_class.return_value = mock_process
        
        result = check_and_set_session_pid(session_id)
        
        self.assertFalse(result)
        # PID should not be changed
        metadata = self.storage.get_session_metadata(session_id)
        self.assertEqual(metadata["pid"], 9999)
    
    @patch('psutil.Process')
    def test_check_and_set_pid_stale_pid(self, mock_process_class):
        """Setting PID when stored PID is stale should clear and set new."""
        import psutil
        
        session_id = create_session(session_id="test")
        
        # Set a stale PID
        self.storage.update_session_metadata(session_id, pid=9999, pid_updated_at=time.time())
        
        # Mock psutil to raise NoSuchProcess (process doesn't exist)
        mock_process_class.side_effect = psutil.NoSuchProcess(9999)
        
        result = check_and_set_session_pid(session_id)
        
        self.assertTrue(result)
        # PID should be updated to current
        metadata = self.storage.get_session_metadata(session_id)
        self.assertEqual(metadata["pid"], self.current_pid)
    
    def test_clear_pid(self):
        """Clearing PID should set it to None."""
        session_id = create_session(session_id="test")
        check_and_set_session_pid(session_id)
        
        clear_session_pid(session_id)
        
        metadata = self.storage.get_session_metadata(session_id)
        self.assertIsNone(metadata["pid"])
        self.assertIsNone(metadata["pid_updated_at"])
    
    @patch('psutil.Process')
    def test_get_session_status_running(self, mock_process_class):
        """get_session_status should detect running process."""
        session_id = create_session(session_id="test")
        self.storage.update_session_metadata(session_id, pid=9999, pid_updated_at=time.time())
        
        # Mock running process
        mock_process = MagicMock()
        mock_process.cmdline.return_value = ["python", "-m", "wolo", "test"]
        mock_process.is_running.return_value = True
        mock_process_class.return_value = mock_process
        
        status = get_session_status(session_id)
        
        self.assertTrue(status["exists"])
        self.assertEqual(status["pid"], 9999)
        self.assertTrue(status["is_running"])
    
    @patch('psutil.Process')
    def test_get_session_status_not_running(self, mock_process_class):
        """get_session_status should detect non-running process."""
        import psutil
        
        session_id = create_session(session_id="test")
        self.storage.update_session_metadata(session_id, pid=9999, pid_updated_at=time.time())
        
        # Mock non-running process
        mock_process_class.side_effect = psutil.NoSuchProcess(9999)
        
        status = get_session_status(session_id)
        
        self.assertTrue(status["exists"])
        self.assertEqual(status["pid"], 9999)
        self.assertFalse(status["is_running"])
    
    def test_get_session_status_no_pid(self):
        """get_session_status should handle session without PID."""
        session_id = create_session(session_id="test")
        
        status = get_session_status(session_id)
        
        self.assertTrue(status["exists"])
        self.assertIsNone(status["pid"])
        self.assertFalse(status["is_running"])


class TestListSessionsWithStatus(unittest.TestCase):
    """Test list_sessions with running status."""
    
    def setUp(self):
        """Create a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SessionStorage(Path(self.temp_dir))
        set_storage(self.storage)
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        set_storage(None)
    
    def test_list_sessions_includes_status(self):
        """list_sessions should include is_running status."""
        session_id1 = create_session(session_id="session1")
        session_id2 = create_session(session_id="session2")
        
        # Set PID for session1
        self.storage.update_session_metadata(session_id1, pid=os.getpid(), pid_updated_at=time.time())
        
        sessions = list_sessions()
        
        # Find our sessions
        session1 = next(s for s in sessions if s["id"] == session_id1)
        session2 = next(s for s in sessions if s["id"] == session_id2)
        
        # Both should have is_running field
        self.assertIn("is_running", session1)
        self.assertIn("is_running", session2)
        self.assertIn("message_count", session1)
        self.assertIn("message_count", session2)


class TestWatchServer(unittest.IsolatedAsyncioTestCase):
    """Test watch server functionality."""
    
    async def test_watch_server_start_stop(self):
        """Watch server should start and stop correctly."""
        from wolo.watch_server import WatchServer
        
        server = WatchServer("test-session")
        
        # Start server
        await server.start()
        
        # Verify socket file exists
        socket_path = Path.home() / ".wolo" / "sessions" / "test-session" / "watch.sock"
        self.assertTrue(socket_path.exists())
        
        # Stop server
        await server.stop()
        
        # Socket should be cleaned up
        self.assertFalse(socket_path.exists())
    
    async def test_watch_server_broadcast_event(self):
        """Watch server should broadcast events to observers."""
        from wolo.watch_server import WatchServer
        from unittest.mock import AsyncMock
        
        server = WatchServer("test-session")
        await server.start()
        
        # Create a mock observer
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        
        # Add observer
        server.observers.add(mock_writer)
        
        # Broadcast event
        await server.broadcast_event({"type": "test", "data": "test_data"})
        
        # Verify event was sent
        mock_writer.write.assert_called_once()
        written_data = mock_writer.write.call_args[0][0]
        self.assertIn(b"test", written_data)
        self.assertIn(b"test_data", written_data)
        
        await server.stop()
    
    async def test_watch_server_handle_client_disconnect(self):
        """Watch server should handle client disconnection gracefully."""
        from wolo.watch_server import WatchServer
        from unittest.mock import AsyncMock
        
        server = WatchServer("test-session")
        await server.start()
        
        # Create mock reader/writer
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        # Simulate immediate disconnect
        async def read_side_effect(*args, **kwargs):
            return b""  # Empty data means disconnect
        
        mock_reader.read = MagicMock(side_effect=read_side_effect)
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        
        # Handle client
        await server._handle_client(mock_reader, mock_writer)
        
        # Verify cleanup
        self.assertNotIn(mock_writer, server.observers)
        
        await server.stop()


class TestSessionInfoDisplay(unittest.TestCase):
    """Test session information display."""
    
    def setUp(self):
        """Create a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SessionStorage(Path(self.temp_dir))
        set_storage(self.storage)
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        set_storage(None)
    
    def test_get_session_status_complete_info(self):
        """get_session_status should return complete information."""
        session_id = create_session(session_id="test")
        
        # Add agent name
        self.storage.update_session_metadata(session_id, agent_display_name="TestAgent")
        
        # Add a message
        from wolo.session import add_user_message
        add_user_message(session_id, "Test message")
        
        status = get_session_status(session_id)
        
        self.assertTrue(status["exists"])
        self.assertEqual(status["agent_name"], "TestAgent")
        self.assertEqual(status["message_count"], 1)
        self.assertIsNotNone(status["created_at"])


if __name__ == "__main__":
    unittest.main()
