# tests/path_safety/test_config_schema.py
from wolo.config_schema import get_config_schema
from wolo.config import PathSafetyConfig


class TestPathSafetySchema:
    def test_schema_includes_path_safety(self):
        """Config schema should include path_safety section"""
        from wolo.config import Config

        schema = get_config_schema(Config)

        assert "path_safety" in schema["properties"]
        path_safety_schema = schema["properties"]["path_safety"]

        assert path_safety_schema["type"] == "object"
        assert "allowed_write_paths" in path_safety_schema["properties"]
        assert "max_confirmations_per_session" in path_safety_schema["properties"]
        assert "audit_denied" in path_safety_schema["properties"]

    def test_allowed_write_paths_is_array(self):
        """allowed_write_paths should be an array type"""
        from wolo.config import Config

        schema = get_config_schema(Config)
        allowed_paths = schema["properties"]["path_safety"]["properties"]["allowed_write_paths"]

        assert allowed_paths["type"] == "array"
