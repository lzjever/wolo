"""Tests for the memory module (model, storage, tools)."""

import json
from pathlib import Path

import pytest

from wolo.memory.model import Memory, _slugify
from wolo.memory.storage import MemoryStorage

# ==================== Slugify Tests ====================


class TestSlugify:
    """Tests for the _slugify helper."""

    def test_ascii_text(self):
        assert _slugify("Debug async code") == "Debug-async-code"

    def test_unsafe_chars(self):
        assert _slugify("a/b:c?d") == "a-b-c-d"

    def test_collapses_dashes(self):
        assert _slugify("hello   world") == "hello-world"

    def test_strips_leading_trailing_dashes(self):
        assert _slugify("  hello  ") == "hello"

    def test_truncation(self):
        result = _slugify("a" * 50, max_len=10)
        assert len(result) <= 10

    def test_unicode_preserved(self):
        result = _slugify("处理XML报表流程")
        assert "处理XML报表流程" == result

    def test_empty_string_returns_uuid(self):
        result = _slugify("???")
        # All chars replaced with dashes, stripped → fallback to uuid hex
        assert len(result) == 8


# ==================== Memory Model Tests ====================


class TestMemoryModel:
    """Tests for Memory data class."""

    def test_create_memory(self):
        """Test creating a memory with auto-generated ID and timestamps."""
        mem = Memory.create(
            title="Test Memory",
            summary="A test memory entry",
            content="Detailed content here",
            tags=["test", "unit"],
        )
        # New ID format: {slug}_{YYMMDD_HHMMSS}
        assert "Test-Memory" in mem.id
        assert mem.title == "Test Memory"
        assert mem.summary == "A test memory entry"
        assert mem.content == "Detailed content here"
        assert mem.tags == ["test", "unit"]
        assert mem.created_at == mem.updated_at
        assert mem.source_session is None
        assert mem.source_context is None

    def test_create_memory_with_source(self):
        """Test creating a memory with source session and context."""
        mem = Memory.create(
            title="With Source",
            summary="Has source info",
            content="Content",
            source_session="Albert_250207_123456",
            source_context={"workdir": "/tmp"},
        )
        assert mem.source_session == "Albert_250207_123456"
        assert mem.source_context == {"workdir": "/tmp"}

    def test_create_memory_no_tags(self):
        """Test creating a memory without tags defaults to empty list."""
        mem = Memory.create(title="No Tags", summary="No tags", content="Content")
        assert mem.tags == []

    def test_to_dict(self):
        """Test serialization to dict."""
        mem = Memory.create(
            title="Dict Test",
            summary="Testing to_dict",
            content="Content",
            tags=["serialize"],
        )
        d = mem.to_dict()
        assert d["id"] == mem.id
        assert d["title"] == "Dict Test"
        assert d["summary"] == "Testing to_dict"
        assert d["content"] == "Content"
        assert d["tags"] == ["serialize"]
        assert d["created_at"] == mem.created_at
        assert d["updated_at"] == mem.updated_at

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "id": "some-title_250207_120000",
            "title": "From Dict",
            "summary": "Testing from_dict",
            "tags": ["deserialize"],
            "content": "Content here",
            "created_at": "2025-02-07T12:00:00",
            "updated_at": "2025-02-07T12:00:00",
            "source_session": "Test_250207_120000",
            "source_context": {"workdir": "/test"},
        }
        mem = Memory.from_dict(data)
        assert mem.id == "some-title_250207_120000"
        assert mem.title == "From Dict"
        assert mem.tags == ["deserialize"]
        assert mem.source_session == "Test_250207_120000"
        assert mem.source_context == {"workdir": "/test"}

    def test_roundtrip(self):
        """Test that to_dict/from_dict is lossless."""
        original = Memory.create(
            title="Roundtrip",
            summary="Testing roundtrip",
            content="Full content",
            tags=["a", "b"],
            source_session="S1",
            source_context={"key": "value"},
        )
        restored = Memory.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.summary == original.summary
        assert restored.content == original.content
        assert restored.tags == original.tags
        assert restored.created_at == original.created_at
        assert restored.source_session == original.source_session
        assert restored.source_context == original.source_context

    def test_id_format(self):
        """Test that generated IDs follow {slug}_{YYMMDD}_{HHMMSS} format."""
        mem = Memory.create(title="My Title", summary="S", content="C")
        # Should contain slugified title and timestamp
        assert "My-Title_" in mem.id
        parts = mem.id.split("_")
        # {slug}_{YYMMDD}_{HHMMSS}
        assert len(parts) >= 3
        # Last two parts are date and time
        assert len(parts[-2]) == 6  # YYMMDD
        assert len(parts[-1]) == 6  # HHMMSS

    def test_content_truncation(self):
        """Test that content is truncated when exceeding max_content_size."""
        long_content = "x" * 20000
        mem = Memory.create(
            title="Truncated",
            summary="S",
            content=long_content,
            max_content_size=12000,
        )
        assert len(mem.content) < 20000
        assert mem.content.endswith("[... truncated]")

    def test_content_no_truncation_within_limit(self):
        """Test that content within limit is not truncated."""
        content = "x" * 100
        mem = Memory.create(
            title="Short",
            summary="S",
            content=content,
            max_content_size=12000,
        )
        assert mem.content == content

    def test_custom_max_content_size(self):
        """Test truncation with custom max_content_size."""
        content = "x" * 500
        mem = Memory.create(
            title="Custom",
            summary="S",
            content=content,
            max_content_size=100,
        )
        # 100 chars + truncation marker
        assert len(mem.content) < 500
        assert mem.content.endswith("[... truncated]")


# ==================== Memory Storage Tests ====================


class TestMemoryStorage:
    """Tests for MemoryStorage."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> MemoryStorage:
        """Create a MemoryStorage with a temp directory."""
        return MemoryStorage(base_dir=tmp_path / "memories")

    def test_save_and_load(self, storage: MemoryStorage):
        """Test saving and loading a memory."""
        mem = Memory.create(
            title="Save Test",
            summary="Testing save",
            content="Content",
            tags=["test"],
        )
        memory_id = storage.save(mem)
        assert memory_id == mem.id

        loaded = storage.load(memory_id)
        assert loaded is not None
        assert loaded.id == mem.id
        assert loaded.title == "Save Test"
        assert loaded.content == "Content"

    def test_load_nonexistent(self, storage: MemoryStorage):
        """Test loading a non-existent memory returns None."""
        result = storage.load("nonexistent_000000_000000")
        assert result is None

    def test_delete(self, storage: MemoryStorage):
        """Test deleting a memory."""
        mem = Memory.create(title="Delete Me", summary="S", content="C")
        storage.save(mem)
        assert storage.delete(mem.id) is True
        assert storage.load(mem.id) is None

    def test_delete_nonexistent(self, storage: MemoryStorage):
        """Test deleting a non-existent memory returns False."""
        assert storage.delete("nonexistent_000000_000000") is False

    def test_list_all(self, storage: MemoryStorage):
        """Test listing all memories."""
        # Empty list initially
        assert storage.list_all() == []

        # Add some memories
        mem1 = Memory.create(title="First", summary="S1", content="C1")
        mem2 = Memory.create(title="Second", summary="S2", content="C2")
        storage.save(mem1)
        storage.save(mem2)

        memories = storage.list_all()
        assert len(memories) == 2
        titles = {m.title for m in memories}
        assert titles == {"First", "Second"}

    def test_list_all_sorted_by_created_at(self, storage: MemoryStorage):
        """Test that list_all returns memories sorted by created_at descending."""
        mem1 = Memory.create(title="Older", summary="S1", content="C1")
        mem2 = Memory.create(title="Newer", summary="S2", content="C2")
        storage.save(mem1)
        storage.save(mem2)

        memories = storage.list_all()
        # Newer should be first (descending order)
        assert memories[0].created_at >= memories[1].created_at

    def test_search_by_title(self, storage: MemoryStorage):
        """Test searching memories by title."""
        mem1 = Memory.create(title="Python Architecture", summary="S", content="C")
        mem2 = Memory.create(title="JavaScript Patterns", summary="S", content="C")
        storage.save(mem1)
        storage.save(mem2)

        results = storage.search("python")
        assert len(results) == 1
        assert results[0].title == "Python Architecture"

    def test_search_by_summary(self, storage: MemoryStorage):
        """Test searching memories by summary."""
        mem = Memory.create(title="T", summary="How to debug async code", content="C")
        storage.save(mem)

        results = storage.search("debug")
        assert len(results) == 1

    def test_search_by_tag(self, storage: MemoryStorage):
        """Test searching memories by tag."""
        mem = Memory.create(title="T", summary="S", content="C", tags=["rust", "systems"])
        storage.save(mem)

        results = storage.search("rust")
        assert len(results) == 1

    def test_search_with_tag_filter(self, storage: MemoryStorage):
        """Test searching with tag filter."""
        mem1 = Memory.create(title="Python Thing", summary="S", content="C", tags=["python"])
        mem2 = Memory.create(title="Python Other", summary="S", content="C", tags=["javascript"])
        storage.save(mem1)
        storage.save(mem2)

        results = storage.search("python", tag_filter="python")
        assert len(results) == 1
        assert results[0].tags == ["python"]

    def test_search_no_results(self, storage: MemoryStorage):
        """Test search with no matching results."""
        mem = Memory.create(title="Something", summary="S", content="C")
        storage.save(mem)

        results = storage.search("nonexistent")
        assert len(results) == 0

    def test_search_case_insensitive(self, storage: MemoryStorage):
        """Test that search is case-insensitive."""
        mem = Memory.create(title="Python Architecture", summary="S", content="C")
        storage.save(mem)

        results = storage.search("PYTHON")
        assert len(results) == 1

    def test_storage_creates_directory(self, tmp_path: Path):
        """Test that storage creates the base directory if it doesn't exist."""
        storage_dir = tmp_path / "new" / "nested" / "memories"
        MemoryStorage(base_dir=storage_dir)
        assert storage_dir.exists()

    def test_index_updated_on_save(self, storage: MemoryStorage):
        """Test that the index is updated when a memory is saved."""
        mem = Memory.create(title="Indexed", summary="S", content="C", tags=["test"])
        storage.save(mem)

        index = storage._load_index()
        assert index is not None
        assert mem.id in index
        assert index[mem.id]["title"] == "Indexed"

    def test_index_updated_on_delete(self, storage: MemoryStorage):
        """Test that the index is updated when a memory is deleted."""
        mem = Memory.create(title="To Delete", summary="S", content="C")
        storage.save(mem)
        storage.delete(mem.id)

        index = storage._load_index()
        assert index is not None
        assert mem.id not in index

    def test_file_persistence(self, storage: MemoryStorage):
        """Test that memories are persisted to JSON files."""
        mem = Memory.create(title="Persistent", summary="S", content="C")
        storage.save(mem)

        # Check file exists
        file_path = storage.base_dir / f"{mem.id}.json"
        assert file_path.exists()

        # Check file contents
        with open(file_path) as f:
            data = json.load(f)
        assert data["title"] == "Persistent"


# ==================== Memory Tool Tests ====================


class TestMemoryTools:
    """Tests for memory tool functions."""

    @pytest.fixture(autouse=True)
    def setup_storage(self, tmp_path: Path, monkeypatch):
        """Set up a temporary storage for each test."""
        import wolo.memory.storage as storage_mod

        test_storage = MemoryStorage(base_dir=tmp_path / "memories")
        monkeypatch.setattr(storage_mod, "_storage", test_storage)
        self.storage = test_storage

    @pytest.mark.asyncio
    async def test_memory_save_execute(self):
        """Test memory_save_execute without LLM (direct save)."""
        from wolo.tools_pkg.memory import memory_save_execute

        result = await memory_save_execute(
            summary="Test knowledge about Python async",
            tags=["python", "async"],
        )
        assert "Memory saved" in result["output"]
        assert "python" in result["metadata"]["tags"]

        # Verify stored
        memories = self.storage.list_all()
        assert len(memories) == 1
        assert memories[0].title == "Test knowledge about Python async"[:50]

    @pytest.mark.asyncio
    async def test_memory_save_with_truncation(self):
        """Test memory_save_execute truncates large content."""
        from wolo.tools_pkg.memory import memory_save_execute

        result = await memory_save_execute(
            summary="x" * 20000,
            max_content_size=100,
        )
        assert "Memory saved" in result["output"]

        memories = self.storage.list_all()
        assert len(memories) == 1
        assert len(memories[0].content) < 20000

    @pytest.mark.asyncio
    async def test_memory_list_execute_empty(self):
        """Test memory_list_execute with no memories."""
        from wolo.tools_pkg.memory import memory_list_execute

        result = await memory_list_execute()
        assert "No memories found" in result["output"]
        assert result["metadata"]["count"] == 0

    @pytest.mark.asyncio
    async def test_memory_list_execute_with_entries(self):
        """Test memory_list_execute with memories."""
        from wolo.tools_pkg.memory import memory_list_execute, memory_save_execute

        await memory_save_execute(summary="First memory", tags=["tag1"])
        await memory_save_execute(summary="Second memory", tags=["tag2"])

        result = await memory_list_execute()
        assert result["metadata"]["count"] == 2

    @pytest.mark.asyncio
    async def test_memory_list_execute_with_tag_filter(self):
        """Test memory_list_execute with tag filter."""
        from wolo.tools_pkg.memory import memory_list_execute, memory_save_execute

        await memory_save_execute(summary="Python stuff", tags=["python"])
        await memory_save_execute(summary="JS stuff", tags=["javascript"])

        result = await memory_list_execute(tag_filter="python")
        assert result["metadata"]["count"] == 1

    @pytest.mark.asyncio
    async def test_memory_recall_execute(self):
        """Test memory_recall_execute search."""
        from wolo.tools_pkg.memory import memory_recall_execute, memory_save_execute

        await memory_save_execute(
            summary="How to debug Python async code",
            tags=["python", "debug"],
        )

        result = await memory_recall_execute("debug")
        assert result["metadata"]["count"] == 1
        assert "debug" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_memory_recall_by_exact_id(self):
        """Test memory_recall_execute with exact ID match."""
        from wolo.tools_pkg.memory import memory_recall_execute, memory_save_execute

        save_result = await memory_save_execute(summary="Exact ID test")
        memory_id = save_result["metadata"]["memory_id"]

        result = await memory_recall_execute(memory_id)
        assert result["metadata"]["count"] == 1

    @pytest.mark.asyncio
    async def test_memory_recall_execute_no_results(self):
        """Test memory_recall_execute with no matches."""
        from wolo.tools_pkg.memory import memory_recall_execute

        result = await memory_recall_execute("nonexistent")
        assert "No memories found" in result["output"]
        assert result["metadata"]["count"] == 0

    @pytest.mark.asyncio
    async def test_memory_delete_execute(self):
        """Test memory_delete_execute."""
        from wolo.tools_pkg.memory import memory_delete_execute, memory_save_execute

        save_result = await memory_save_execute(summary="To delete")
        memory_id = save_result["metadata"]["memory_id"]

        result = await memory_delete_execute(memory_id)
        assert "deleted" in result["output"].lower()
        assert result["metadata"]["error"] is None

        # Verify deleted
        assert self.storage.load(memory_id) is None

    @pytest.mark.asyncio
    async def test_memory_delete_execute_not_found(self):
        """Test memory_delete_execute with non-existent ID."""
        from wolo.tools_pkg.memory import memory_delete_execute

        result = await memory_delete_execute("nonexistent_000000_000000")
        assert "not found" in result["output"].lower()
        assert result["metadata"]["error"] == "not_found"


# ==================== Load Memories Tests ====================


class TestLoadMemories:
    """Tests for load_memories_for_session."""

    @pytest.fixture(autouse=True)
    def setup_storage(self, tmp_path: Path, monkeypatch):
        """Set up a temporary storage for each test."""
        import wolo.memory.storage as storage_mod

        test_storage = MemoryStorage(base_dir=tmp_path / "memories")
        monkeypatch.setattr(storage_mod, "_storage", test_storage)
        self.storage = test_storage

    def test_load_by_exact_id(self):
        """Test loading a memory by exact ID."""
        from wolo.tools_pkg.memory import load_memories_for_session

        mem = Memory.create(title="Test Load", summary="S", content="Load content", tags=["test"])
        self.storage.save(mem)

        result = load_memories_for_session([mem.id])
        assert result is not None
        assert "Load content" in result
        assert "Test Load" in result

    def test_load_by_search_query(self):
        """Test loading memories by search query."""
        from wolo.tools_pkg.memory import load_memories_for_session

        mem = Memory.create(
            title="Python Async",
            summary="How to use async",
            content="Async details here",
        )
        self.storage.save(mem)

        result = load_memories_for_session(["python"])
        assert result is not None
        assert "Async details here" in result

    def test_load_multiple(self):
        """Test loading multiple memories."""
        from wolo.tools_pkg.memory import load_memories_for_session

        mem1 = Memory.create(title="Alpha", summary="S1", content="Content A", tags=["a"])
        mem2 = Memory.create(title="Beta", summary="S2", content="Content B", tags=["b"])
        self.storage.save(mem1)
        self.storage.save(mem2)

        result = load_memories_for_session([mem1.id, mem2.id])
        assert result is not None
        assert "Content A" in result
        assert "Content B" in result

    def test_load_deduplicates(self):
        """Test that duplicate memories are deduplicated."""
        from wolo.tools_pkg.memory import load_memories_for_session

        mem = Memory.create(title="Dedup", summary="S", content="Unique content")
        self.storage.save(mem)

        # Load same memory twice via ID and search
        result = load_memories_for_session([mem.id, "dedup"])
        assert result is not None
        # Should only appear once
        assert result.count("Unique content") == 1

    def test_load_not_found(self):
        """Test loading when no memories match."""
        from wolo.tools_pkg.memory import load_memories_for_session

        result = load_memories_for_session(["nonexistent"])
        assert result is None

    def test_load_format(self):
        """Test the format of loaded memories context."""
        from wolo.tools_pkg.memory import load_memories_for_session

        mem = Memory.create(title="Format Test", summary="S", content="Body", tags=["tag1"])
        self.storage.save(mem)

        result = load_memories_for_session([mem.id])
        assert "[Loaded memories]" in result
        assert "[End of loaded memories]" in result
        assert "Format Test" in result
        assert "tag1" in result


# ==================== Slash Command Tests ====================


class TestSlashCommands:
    """Tests for slash command handling."""

    @pytest.fixture(autouse=True)
    def setup_storage(self, tmp_path: Path, monkeypatch):
        """Set up a temporary storage for each test."""
        import wolo.memory.storage as storage_mod

        test_storage = MemoryStorage(base_dir=tmp_path / "memories")
        monkeypatch.setattr(storage_mod, "_storage", test_storage)
        self.storage = test_storage

    @pytest.mark.asyncio
    async def test_remember_with_args(self):
        """Test /remember with arguments injects as user message."""
        from wolo.cli.slash import handle_slash_command

        result = await handle_slash_command("test_session", "/remember how we fixed the auth bug")
        assert result.handled is True
        assert result.inject_as_user_message is not None
        assert "how we fixed the auth bug" in result.inject_as_user_message

    @pytest.mark.asyncio
    async def test_remember_without_args(self):
        """Test /remember without arguments shows usage."""
        from wolo.cli.slash import handle_slash_command

        result = await handle_slash_command("test_session", "/remember")
        assert result.handled is True
        assert "Usage" in result.output
        assert result.inject_as_user_message is None

    @pytest.mark.asyncio
    async def test_recall(self):
        """Test /recall command."""
        from wolo.cli.slash import handle_slash_command
        from wolo.tools_pkg.memory import memory_save_execute

        await memory_save_execute(summary="Test recall content", tags=["test"])

        result = await handle_slash_command("test_session", "/recall test")
        assert result.handled is True
        assert "Test recall content" in result.output

    @pytest.mark.asyncio
    async def test_recall_no_args(self):
        """Test /recall without arguments shows usage."""
        from wolo.cli.slash import handle_slash_command

        result = await handle_slash_command("test_session", "/recall")
        assert result.handled is True
        assert "Usage" in result.output

    @pytest.mark.asyncio
    async def test_memories(self):
        """Test /memories command."""
        from wolo.cli.slash import handle_slash_command
        from wolo.tools_pkg.memory import memory_save_execute

        await memory_save_execute(summary="Listed memory", tags=["list"])

        result = await handle_slash_command("test_session", "/memories")
        assert result.handled is True
        assert "Listed memory" in result.output

    @pytest.mark.asyncio
    async def test_forget(self):
        """Test /forget command."""
        from wolo.cli.slash import handle_slash_command
        from wolo.tools_pkg.memory import memory_save_execute

        save_result = await memory_save_execute(summary="Forget me")
        memory_id = save_result["metadata"]["memory_id"]

        result = await handle_slash_command("test_session", f"/forget {memory_id}")
        assert result.handled is True
        assert "deleted" in result.output.lower()

    @pytest.mark.asyncio
    async def test_forget_no_args(self):
        """Test /forget without arguments shows usage."""
        from wolo.cli.slash import handle_slash_command

        result = await handle_slash_command("test_session", "/forget")
        assert result.handled is True
        assert "Usage" in result.output

    @pytest.mark.asyncio
    async def test_unknown_slash_command(self):
        """Test unknown slash command returns not handled."""
        from wolo.cli.slash import handle_slash_command

        result = await handle_slash_command("test_session", "/unknown")
        assert result.handled is False

    @pytest.mark.asyncio
    async def test_memory_command_not_handled(self):
        """Test that /memory is not a valid command (use /remember instead)."""
        from wolo.cli.slash import handle_slash_command

        result = await handle_slash_command("test_session", "/memory something")
        assert result.handled is False
