"""Compaction history management.

Stores and retrieves compaction records for auditing, debugging,
and potential message recovery.
"""

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wolo.compaction.types import CompactionRecord, PolicyType

if TYPE_CHECKING:
    from wolo.session import Message, SessionStorage

logger = logging.getLogger(__name__)


class CompactionHistory:
    """Manages compaction history records.
    
    Storage Layout:
        ~/.wolo/sessions/{session_id}/compaction/
        ├── records.json          # Index of all records
        └── {record_id}.json      # Individual record details
    
    The records.json file contains a lightweight index for fast
    listing, while full record details are stored separately.
    """
    
    def __init__(self, storage: "SessionStorage") -> None:
        """Initialize compaction history.
        
        Args:
            storage: Session storage instance for file operations
        """
        self._storage = storage
    
    def add_record(
        self,
        session_id: str,
        record: CompactionRecord,
    ) -> None:
        """Add a compaction record.
        
        Args:
            session_id: Session identifier
            record: Compaction record to store
            
        Side Effects:
            - Creates compaction directory if needed
            - Writes record file
            - Updates records index
        """
        # Ensure compaction directory exists
        compaction_dir = self._compaction_dir(session_id)
        compaction_dir.mkdir(parents=True, exist_ok=True)
        
        # Write the full record
        record_file = self._record_file(session_id, record.id)
        record_data = self._serialize_record(record)
        self._write_json(record_file, record_data)
        
        # Update the index
        self._update_index(session_id, record)
        
        logger.debug(f"Added compaction record {record.id[:8]}... to session {session_id[:8]}...")
    
    def get_records(
        self,
        session_id: str,
    ) -> list[CompactionRecord]:
        """Get all compaction records for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of compaction records, sorted by creation time (newest first)
        """
        records = []
        
        index_file = self._records_file(session_id)
        if not index_file.exists():
            return records
        
        index_data = self._read_json(index_file)
        if not index_data:
            return records
        
        # Load each record
        for entry in index_data.get("records", []):
            record_id = entry.get("id")
            if record_id:
                record = self.get_record(session_id, record_id)
                if record:
                    records.append(record)
        
        # Sort by creation time (newest first)
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records
    
    def get_record(
        self,
        session_id: str,
        record_id: str,
    ) -> CompactionRecord | None:
        """Get a single compaction record.
        
        Args:
            session_id: Session identifier
            record_id: Record identifier
            
        Returns:
            CompactionRecord if found, None otherwise
        """
        record_file = self._record_file(session_id, record_id)
        if not record_file.exists():
            return None
        
        data = self._read_json(record_file)
        if not data:
            return None
        
        return self._deserialize_record(data)
    
    def get_original_messages(
        self,
        session_id: str,
        record_id: str,
    ) -> list["Message"]:
        """Get original messages from a compaction record.
        
        Args:
            session_id: Session identifier
            record_id: Compaction record identifier
            
        Returns:
            List of original messages (loaded from storage)
        """
        record = self.get_record(session_id, record_id)
        if not record:
            return []
        
        messages = []
        for msg_id in record.compacted_message_ids:
            msg = self._storage.get_message(session_id, msg_id)
            if msg:
                messages.append(msg)
        
        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp)
        return messages
    
    def _compaction_dir(self, session_id: str) -> Path:
        """Get compaction directory path for a session."""
        return self._storage._session_dir(session_id) / "compaction"
    
    def _records_file(self, session_id: str) -> Path:
        """Get records index file path."""
        return self._compaction_dir(session_id) / "records.json"
    
    def _record_file(self, session_id: str, record_id: str) -> Path:
        """Get individual record file path."""
        return self._compaction_dir(session_id) / f"{record_id}.json"
    
    def _update_index(self, session_id: str, record: CompactionRecord) -> None:
        """Update the records index file."""
        index_file = self._records_file(session_id)
        
        # Load existing index
        if index_file.exists():
            index_data = self._read_json(index_file) or {"records": []}
        else:
            index_data = {"records": []}
        
        # Add new entry
        index_data["records"].append({
            "id": record.id,
            "created_at": record.created_at,
            "policy": record.policy.value,
        })
        
        # Write updated index
        self._write_json(index_file, index_data)
    
    def _write_json(self, path: Path, data: dict) -> None:
        """Write JSON data to file."""
        import fcntl
        import os
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        temp_path = path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            temp_path.rename(path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e
    
    def _read_json(self, path: Path) -> dict | None:
        """Read JSON data from file."""
        import fcntl
        
        if not path.exists():
            return None
        
        try:
            with open(path, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read {path}: {e}")
            return None
    
    def _serialize_record(self, record: CompactionRecord) -> dict[str, Any]:
        """Serialize a CompactionRecord to dictionary."""
        return {
            "id": record.id,
            "session_id": record.session_id,
            "policy": record.policy.value,
            "created_at": record.created_at,
            "original_token_count": record.original_token_count,
            "result_token_count": record.result_token_count,
            "original_message_count": record.original_message_count,
            "result_message_count": record.result_message_count,
            "compacted_message_ids": list(record.compacted_message_ids),
            "preserved_message_ids": list(record.preserved_message_ids),
            "summary_message_id": record.summary_message_id,
            "summary_text": record.summary_text,
            "config_snapshot": record.config_snapshot,
        }
    
    def _deserialize_record(self, data: dict[str, Any]) -> CompactionRecord:
        """Deserialize a dictionary to CompactionRecord."""
        return CompactionRecord(
            id=data["id"],
            session_id=data["session_id"],
            policy=PolicyType(data["policy"]),
            created_at=data["created_at"],
            original_token_count=data["original_token_count"],
            result_token_count=data["result_token_count"],
            original_message_count=data["original_message_count"],
            result_message_count=data["result_message_count"],
            compacted_message_ids=tuple(data.get("compacted_message_ids", [])),
            preserved_message_ids=tuple(data.get("preserved_message_ids", [])),
            summary_message_id=data.get("summary_message_id"),
            summary_text=data.get("summary_text", ""),
            config_snapshot=data.get("config_snapshot", {}),
        )
