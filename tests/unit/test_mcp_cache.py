"""Tests for MCP tool cache functionality."""

import json
import time

from wolo.mcp.cache import (
    CACHE_VERSION,
    DEFAULT_CACHE_TTL,
    CachedServerTools,
    MCPCache,
    clear_cache,
    filter_cache_by_servers,
    get_cache_path,
    get_cached_tool_schemas,
    get_cached_tools_by_server,
    is_cache_valid,
    load_cache,
    mark_server_error,
    rebuild_cache_from_servers,
    remove_server_from_cache,
    save_cache,
    update_server_cache,
)


class TestCachedServerTools:
    """Test CachedServerTools dataclass."""

    def test_create_empty(self):
        """Test creating empty cached server tools."""
        tools = CachedServerTools()
        assert tools.tools == []
        assert tools.status == "unknown"
        assert tools.cached_at == 0.0

    def test_is_expired(self):
        """Test expiration check."""
        tools = CachedServerTools(cached_at=time.time())
        assert not tools.is_expired()

        tools_old = CachedServerTools(cached_at=time.time() - DEFAULT_CACHE_TTL - 1)
        assert tools_old.is_expired()

    def test_is_expired_custom_ttl(self):
        """Test expiration check with custom TTL."""
        tools = CachedServerTools(cached_at=time.time() - 100)
        assert not tools.is_expired(ttl=200)
        assert tools.is_expired(ttl=50)


class TestMCPCache:
    """Test MCPCache dataclass."""

    def test_create_empty(self):
        """Test creating empty cache."""
        cache = MCPCache()
        assert cache.version == CACHE_VERSION
        assert cache.servers == {}

    def test_to_dict(self):
        """Test serialization to dict."""
        cache = MCPCache()
        cache.updated_at = 12345.0
        cache.servers["test"] = CachedServerTools(
            tools=[{"name": "tool1"}],
            status="running",
            cached_at=12345.0,
        )

        data = cache.to_dict()
        assert data["version"] == CACHE_VERSION
        assert data["updated_at"] == 12345.0
        assert "test" in data["servers"]
        assert data["servers"]["test"]["tools"] == [{"name": "tool1"}]

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "version": CACHE_VERSION,
            "updated_at": 12345.0,
            "servers": {
                "test": {
                    "tools": [{"name": "tool1"}],
                    "status": "running",
                    "cached_at": 12345.0,
                }
            },
        }

        cache = MCPCache.from_dict(data)
        assert cache.version == CACHE_VERSION
        assert cache.updated_at == 12345.0
        assert "test" in cache.servers
        assert cache.servers["test"].tools == [{"name": "tool1"}]

    def test_from_dict_empty(self):
        """Test deserialization from empty dict."""
        cache = MCPCache.from_dict({})
        assert cache.version == CACHE_VERSION
        assert cache.servers == {}


class TestCacheIO:
    """Test cache load/save operations."""

    def test_get_cache_path(self):
        """Test cache path is under ~/.wolo/."""
        path = get_cache_path()
        assert ".wolo" in str(path)
        assert path.name == "mcp_cache.json"

    def test_save_and_load_cache(self, tmp_path, monkeypatch):
        """Test saving and loading cache."""
        # Redirect cache path to temp directory
        monkeypatch.setattr(
            "wolo.mcp.cache.get_cache_path",
            lambda: tmp_path / "mcp_cache.json",
        )

        # Create and save cache
        cache = MCPCache()
        cache.servers["test_server"] = CachedServerTools(
            tools=[{"name": "test_tool", "description": "Test"}],
            status="running",
            cached_at=time.time(),
        )
        save_cache(cache)

        # Load cache
        loaded = load_cache()
        assert loaded is not None
        assert "test_server" in loaded.servers
        assert loaded.servers["test_server"].tools[0]["name"] == "test_tool"

    def test_load_cache_not_found(self, tmp_path, monkeypatch):
        """Test loading cache when file doesn't exist."""
        monkeypatch.setattr(
            "wolo.mcp.cache.get_cache_path",
            lambda: tmp_path / "nonexistent.json",
        )

        cache = load_cache()
        assert cache is None

    def test_load_cache_invalid_json(self, tmp_path, monkeypatch):
        """Test loading cache with invalid JSON."""
        cache_path = tmp_path / "mcp_cache.json"
        cache_path.write_text("not valid json")

        monkeypatch.setattr("wolo.mcp.cache.get_cache_path", lambda: cache_path)

        cache = load_cache()
        assert cache is None

    def test_load_cache_version_mismatch(self, tmp_path, monkeypatch):
        """Test loading cache with wrong version."""
        cache_path = tmp_path / "mcp_cache.json"
        cache_path.write_text(json.dumps({"version": 999, "servers": {}}))

        monkeypatch.setattr("wolo.mcp.cache.get_cache_path", lambda: cache_path)

        cache = load_cache()
        assert cache is None

    def test_clear_cache(self, tmp_path, monkeypatch):
        """Test clearing cache."""
        cache_path = tmp_path / "mcp_cache.json"
        cache_path.write_text("{}")

        monkeypatch.setattr("wolo.mcp.cache.get_cache_path", lambda: cache_path)

        clear_cache()
        assert not cache_path.exists()


class TestCacheHelpers:
    """Test cache helper functions."""

    def test_update_server_cache_new(self):
        """Test updating cache with new server."""
        cache = update_server_cache(
            None,
            "new_server",
            [{"name": "tool1"}],
            "running",
        )

        assert cache is not None
        assert "new_server" in cache.servers
        assert cache.servers["new_server"].tools == [{"name": "tool1"}]

    def test_update_server_cache_existing(self):
        """Test updating existing server in cache."""
        cache = MCPCache()
        cache.servers["test"] = CachedServerTools(tools=[{"name": "old"}])

        updated = update_server_cache(
            cache,
            "test",
            [{"name": "new"}],
            "running",
        )

        assert updated.servers["test"].tools == [{"name": "new"}]

    def test_get_cached_tool_schemas_empty(self):
        """Test getting schemas from empty cache."""
        schemas = get_cached_tool_schemas(None)
        assert schemas == []

        cache = MCPCache()
        schemas = get_cached_tool_schemas(cache)
        assert schemas == []

    def test_get_cached_tool_schemas(self):
        """Test getting schemas from cache."""
        cache = MCPCache()
        cache.servers["test"] = CachedServerTools(
            tools=[{"name": "tool1", "description": "Test", "input_schema": {}}],
            status="running",
            cached_at=time.time(),
        )

        schemas = get_cached_tool_schemas(cache)
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "mcp_test__tool1"

    def test_get_cached_tool_schemas_llm_format(self):
        """Test getting schemas already in LLM format."""
        cache = MCPCache()
        cache.servers["test"] = CachedServerTools(
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "mcp_test__tool1",
                        "description": "Test",
                        "parameters": {},
                    },
                }
            ],
            status="running",
            cached_at=time.time(),
        )

        schemas = get_cached_tool_schemas(cache)
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "mcp_test__tool1"

    def test_get_cached_tools_by_server(self):
        """Test getting tools grouped by server."""
        cache = MCPCache()
        cache.servers["s1"] = CachedServerTools(
            tools=[{"name": "t1"}],
            status="running",
            cached_at=time.time(),
        )
        cache.servers["s2"] = CachedServerTools(
            tools=[{"name": "t2"}],
            status="error",  # Not running, should be excluded
            cached_at=time.time(),
        )

        tools = get_cached_tools_by_server(cache)
        assert "s1" in tools
        assert "s2" not in tools
        assert tools["s1"] == [{"name": "t1"}]

    def test_is_cache_valid(self):
        """Test cache validity check."""
        # None is invalid
        assert not is_cache_valid(None)

        # Empty cache is invalid
        cache = MCPCache()
        assert not is_cache_valid(cache)

        # Cache with fresh data is valid
        cache.servers["test"] = CachedServerTools(
            tools=[{"name": "tool1"}],
            status="running",
            cached_at=time.time(),
        )
        assert is_cache_valid(cache)

        # Cache with expired data is invalid
        cache.servers["test"].cached_at = time.time() - DEFAULT_CACHE_TTL - 1
        assert not is_cache_valid(cache)

    def test_is_cache_valid_version_mismatch(self):
        """Test cache validity with version mismatch."""
        cache = MCPCache(version=999)
        cache.servers["test"] = CachedServerTools(
            tools=[{"name": "tool1"}],
            status="running",
            cached_at=time.time(),
        )
        assert not is_cache_valid(cache)


class TestCacheFiltering:
    """Test cache filtering and cleanup functions."""

    def test_filter_cache_by_servers(self):
        """Test filtering cache to only include specified servers."""
        cache = MCPCache()
        cache.servers["keep"] = CachedServerTools(tools=[{"name": "t1"}])
        cache.servers["remove"] = CachedServerTools(tools=[{"name": "t2"}])

        filtered = filter_cache_by_servers(cache, {"keep", "other"})

        assert "keep" in filtered.servers
        assert "remove" not in filtered.servers

    def test_filter_cache_by_servers_none(self):
        """Test filtering None cache."""
        result = filter_cache_by_servers(None, {"keep"})
        assert result is None

    def test_filter_cache_by_servers_empty_set(self):
        """Test filtering with empty server set removes all."""
        cache = MCPCache()
        cache.servers["s1"] = CachedServerTools(tools=[{"name": "t1"}])

        filtered = filter_cache_by_servers(cache, set())

        assert len(filtered.servers) == 0

    def test_remove_server_from_cache(self):
        """Test removing a server from cache."""
        cache = MCPCache()
        cache.servers["s1"] = CachedServerTools(tools=[{"name": "t1"}])
        cache.servers["s2"] = CachedServerTools(tools=[{"name": "t2"}])

        result = remove_server_from_cache(cache, "s1")

        assert "s1" not in result.servers
        assert "s2" in result.servers

    def test_remove_server_from_cache_not_found(self):
        """Test removing non-existent server."""
        cache = MCPCache()
        cache.servers["s1"] = CachedServerTools(tools=[{"name": "t1"}])

        result = remove_server_from_cache(cache, "nonexistent")

        assert "s1" in result.servers

    def test_remove_server_from_cache_none(self):
        """Test removing from None cache."""
        result = remove_server_from_cache(None, "s1")
        assert result is None

    def test_mark_server_error_existing(self):
        """Test marking existing server as error."""
        cache = MCPCache()
        cache.servers["s1"] = CachedServerTools(
            tools=[{"name": "t1"}],
            status="running",
        )

        result = mark_server_error(cache, "s1", "Connection failed")

        assert result.servers["s1"].status == "error"

    def test_mark_server_error_new(self):
        """Test marking non-existent server as error."""
        result = mark_server_error(None, "s1", "Failed")

        assert "s1" in result.servers
        assert result.servers["s1"].status == "error"
        assert result.servers["s1"].tools == []

    def test_rebuild_cache_from_servers(self):
        """Test rebuilding cache from server states."""
        server_states = {
            "running_server": {
                "status": "running",
                "tools": [{"name": "t1", "description": "Test", "input_schema": {}}],
            },
            "error_server": {
                "status": "error",
                "tools": [],
            },
        }

        new_cache = rebuild_cache_from_servers(None, server_states)

        assert "running_server" in new_cache.servers
        assert "error_server" not in new_cache.servers  # Error servers excluded
        assert len(new_cache.servers["running_server"].tools) == 1

    def test_rebuild_cache_from_servers_empty(self):
        """Test rebuilding cache with no running servers."""
        server_states = {
            "error_server": {
                "status": "error",
                "tools": [],
            },
        }

        new_cache = rebuild_cache_from_servers(None, server_states)

        assert len(new_cache.servers) == 0

    def test_rebuild_cache_replaces_old(self):
        """Test that rebuild replaces old cache content."""
        old_cache = MCPCache()
        old_cache.servers["old_server"] = CachedServerTools(tools=[{"name": "old"}])

        server_states = {
            "new_server": {
                "status": "running",
                "tools": [{"name": "new", "description": "New", "input_schema": {}}],
            },
        }

        new_cache = rebuild_cache_from_servers(old_cache, server_states)

        # Old server should not be in new cache
        assert "old_server" not in new_cache.servers
        assert "new_server" in new_cache.servers
