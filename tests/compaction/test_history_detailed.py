"""Comprehensive tests for CompactionHistory.

Tests history storage, retrieval, and edge cases.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wolo.compaction.history import CompactionHistory
from wolo.compaction.types import CompactionRecord, PolicyType
from wolo.session import Message, TextPart


@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_storage(temp_dir):
    """Create mock storage."""
    storage = MagicMock()

    def session_dir(session_id: str) -> Path:
        return temp_dir / "sessions" / session_id

    storage._session_dir = session_dir
    storage.get_message = MagicMock(return_value=None)

    return storage


@pytest.fixture
def history(mock_storage):
    """Create CompactionHistory instance."""
    return CompactionHistory(mock_storage)


@pytest.fixture
def sample_record():
    """Create sample compaction record."""
    import time

    return CompactionRecord(
        id="test-record-1",
        session_id="test-session",
        policy=PolicyType.SUMMARY,
        created_at=time.time(),
        original_token_count=10000,
        result_token_count=5000,
        original_message_count=20,
        result_message_count=7,
        compacted_message_ids=("msg-1", "msg-2", "msg-3"),
        preserved_message_ids=("msg-4", "msg-5", "msg-6", "msg-7"),
        summary_message_id="summary-msg-1",
        summary_text="Summary of conversation",
        config_snapshot={"recent_exchanges_to_keep": 6},
    )


class TestAddRecord:
    """Test add_record functionality."""

    def test_adds_record(self, history, mock_storage, sample_record, temp_dir):
        """Should add record successfully."""
        history.add_record("test-session", sample_record)

        # Verify record file exists
        record_file = (
            temp_dir / "sessions" / "test-session" / "compaction" / f"{sample_record.id}.json"
        )
        assert record_file.exists()

        # Verify index file exists
        index_file = temp_dir / "sessions" / "test-session" / "compaction" / "records.json"
        assert index_file.exists()

    def test_record_file_contains_data(self, history, mock_storage, sample_record, temp_dir):
        """Record file should contain correct data."""
        history.add_record("test-session", sample_record)

        record_file = (
            temp_dir / "sessions" / "test-session" / "compaction" / f"{sample_record.id}.json"
        )
        with open(record_file) as f:
            data = json.load(f)

        assert data["id"] == sample_record.id
        assert data["session_id"] == sample_record.session_id
        assert data["policy"] == sample_record.policy.value
        assert data["original_token_count"] == sample_record.original_token_count

    def test_index_file_updated(self, history, mock_storage, sample_record, temp_dir):
        """Index file should be updated."""
        history.add_record("test-session", sample_record)

        index_file = temp_dir / "sessions" / "test-session" / "compaction" / "records.json"
        with open(index_file) as f:
            index_data = json.load(f)

        assert "records" in index_data
        assert len(index_data["records"]) == 1
        assert index_data["records"][0]["id"] == sample_record.id


class TestGetRecords:
    """Test get_records functionality."""

    def test_empty_initially(self, history):
        """Initially should return empty list."""
        records = history.get_records("test-session")
        assert len(records) == 0

    def test_retrieves_added_records(self, history, mock_storage, sample_record, temp_dir):
        """Should retrieve added records."""
        history.add_record("test-session", sample_record)

        records = history.get_records("test-session")
        assert len(records) == 1
        assert records[0].id == sample_record.id

    def test_sorted_newest_first(self, history, mock_storage, temp_dir):
        """Records should be sorted newest first."""
        import time

        record1 = CompactionRecord(
            id="record-1",
            session_id="test-session",
            policy=PolicyType.SUMMARY,
            created_at=time.time() - 100,
            original_token_count=1000,
            result_token_count=500,
            original_message_count=10,
            result_message_count=5,
            compacted_message_ids=(),
            preserved_message_ids=(),
            summary_message_id=None,
            summary_text="",
            config_snapshot={},
        )

        record2 = CompactionRecord(
            id="record-2",
            session_id="test-session",
            policy=PolicyType.TOOL_PRUNING,
            created_at=time.time(),
            original_token_count=2000,
            result_token_count=1000,
            original_message_count=20,
            result_message_count=10,
            compacted_message_ids=(),
            preserved_message_ids=(),
            summary_message_id=None,
            summary_text="",
            config_snapshot={},
        )

        history.add_record("test-session", record1)
        history.add_record("test-session", record2)

        records = history.get_records("test-session")
        assert len(records) == 2
        # Newest first
        assert records[0].id == record2.id
        assert records[1].id == record1.id

    def test_multiple_sessions_independent(self, history, mock_storage, sample_record, temp_dir):
        """Multiple sessions should be independent."""
        record1 = CompactionRecord(
            id="record-1",
            session_id="session-1",
            policy=PolicyType.SUMMARY,
            created_at=1000.0,
            original_token_count=1000,
            result_token_count=500,
            original_message_count=10,
            result_message_count=5,
            compacted_message_ids=(),
            preserved_message_ids=(),
            summary_message_id=None,
            summary_text="",
            config_snapshot={},
        )

        record2 = CompactionRecord(
            id="record-2",
            session_id="session-2",
            policy=PolicyType.TOOL_PRUNING,
            created_at=1000.0,
            original_token_count=2000,
            result_token_count=1000,
            original_message_count=20,
            result_message_count=10,
            compacted_message_ids=(),
            preserved_message_ids=(),
            summary_message_id=None,
            summary_text="",
            config_snapshot={},
        )

        history.add_record("session-1", record1)
        history.add_record("session-2", record2)

        records1 = history.get_records("session-1")
        records2 = history.get_records("session-2")

        assert len(records1) == 1
        assert len(records2) == 1
        assert records1[0].id == record1.id
        assert records2[0].id == record2.id


class TestGetRecord:
    """Test get_record functionality."""

    def test_returns_none_when_not_found(self, history):
        """Should return None when record not found."""
        record = history.get_record("test-session", "non-existent")
        assert record is None

    def test_retrieves_existing_record(self, history, mock_storage, sample_record, temp_dir):
        """Should retrieve existing record."""
        history.add_record("test-session", sample_record)

        record = history.get_record("test-session", sample_record.id)
        assert record is not None
        assert record.id == sample_record.id
        assert record.session_id == sample_record.session_id

    def test_deserializes_correctly(self, history, mock_storage, sample_record, temp_dir):
        """Should deserialize record correctly."""
        history.add_record("test-session", sample_record)

        record = history.get_record("test-session", sample_record.id)
        assert record.policy == PolicyType.SUMMARY
        assert record.original_token_count == 10000
        assert record.result_token_count == 5000
        assert len(record.compacted_message_ids) == 3
        assert len(record.preserved_message_ids) == 4


class TestGetOriginalMessages:
    """Test get_original_messages functionality."""

    def test_returns_empty_when_record_not_found(self, history):
        """Should return empty list when record not found."""
        messages = history.get_original_messages("test-session", "non-existent")
        assert len(messages) == 0

    def test_retrieves_messages_from_storage(self, history, mock_storage, sample_record, temp_dir):
        """Should retrieve messages from storage."""
        # Create mock messages
        msg1 = Message(role="user", parts=[TextPart(text="Message 1")])
        msg1.id = "msg-1"
        msg2 = Message(role="assistant", parts=[TextPart(text="Message 2")])
        msg2.id = "msg-2"

        def get_message(session_id: str, msg_id: str):
            if msg_id == "msg-1":
                return msg1
            elif msg_id == "msg-2":
                return msg2
            return None

        mock_storage.get_message = get_message

        history.add_record("test-session", sample_record)

        messages = history.get_original_messages("test-session", sample_record.id)

        # Should retrieve messages from storage
        assert len(messages) == 2  # Only msg-1 and msg-2 exist in mock
        assert messages[0].id == "msg-1"
        assert messages[1].id == "msg-2"

    def test_sorts_by_timestamp(self, history, mock_storage, sample_record, temp_dir):
        """Should sort messages by timestamp."""
        import time

        msg1 = Message(role="user", parts=[TextPart(text="Message 1")])
        msg1.id = "msg-1"
        msg1.timestamp = time.time() - 100

        msg2 = Message(role="assistant", parts=[TextPart(text="Message 2")])
        msg2.id = "msg-2"
        msg2.timestamp = time.time()

        def get_message(session_id: str, msg_id: str):
            if msg_id == "msg-1":
                return msg1
            elif msg_id == "msg-2":
                return msg2
            return None

        mock_storage.get_message = get_message

        history.add_record("test-session", sample_record)

        messages = history.get_original_messages("test-session", sample_record.id)

        # Should be sorted by timestamp
        assert messages[0].timestamp < messages[1].timestamp


class TestEdgeCases:
    """Test edge cases."""

    def test_handles_corrupted_index(self, history, mock_storage, temp_dir):
        """Should handle corrupted index file."""
        # Create corrupted index
        index_file = temp_dir / "sessions" / "test-session" / "compaction" / "records.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)
        with open(index_file, "w") as f:
            f.write("invalid json{")

        # Should not crash
        records = history.get_records("test-session")
        assert len(records) == 0

    def test_handles_corrupted_record(self, history, mock_storage, temp_dir):
        """Should handle corrupted record file."""
        # Create corrupted record
        record_file = temp_dir / "sessions" / "test-session" / "compaction" / "record-1.json"
        record_file.parent.mkdir(parents=True, exist_ok=True)
        with open(record_file, "w") as f:
            f.write("invalid json{")

        # Should return None
        record = history.get_record("test-session", "record-1")
        assert record is None

    def test_handles_missing_record_file(self, history, mock_storage, temp_dir):
        """Should handle missing record file in index."""
        # Create index with reference to non-existent record
        index_file = temp_dir / "sessions" / "test-session" / "compaction" / "records.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)
        with open(index_file, "w") as f:
            json.dump(
                {"records": [{"id": "non-existent", "created_at": 1000.0, "policy": "summary"}]}, f
            )

        # Should skip missing records
        records = history.get_records("test-session")
        assert len(records) == 0
