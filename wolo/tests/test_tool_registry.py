"""
Tests for the Tool Registry.
"""

import unittest

from wolo.tool_registry import (
    ToolSpec,
    ToolCategory,
    ToolRegistry,
    get_registry,
    Colors,
    SHELL, READ, WRITE, EDIT, GREP, TODOWRITE,
)


class TestToolSpec(unittest.TestCase):
    """Test ToolSpec class."""
    
    def test_get_color_by_category(self):
        """Tool should return correct color based on category."""
        self.assertEqual(SHELL.get_color(), Colors.YELLOW)
        self.assertEqual(READ.get_color(), Colors.CYAN)
        self.assertEqual(WRITE.get_color(), Colors.MAGENTA)
        self.assertEqual(TODOWRITE.get_color(), Colors.GREEN)
    
    def test_format_brief_shell(self):
        """Shell tool should format brief correctly."""
        brief = SHELL.format_brief({"command": "ls -la"})
        self.assertEqual(brief, "$ ls -la")
        
        # Long command should be truncated
        long_cmd = "a" * 100
        brief = SHELL.format_brief({"command": long_cmd})
        self.assertTrue(len(brief) < 80)
        self.assertTrue(brief.endswith("..."))
    
    def test_format_brief_read(self):
        """Read tool should format brief correctly."""
        brief = READ.format_brief({"file_path": "/path/to/file.py"})
        self.assertEqual(brief, "📄 /path/to/file.py")
    
    def test_format_brief_write(self):
        """Write tool should include char count."""
        brief = WRITE.format_brief({
            "file_path": "/path/to/file.py",
            "content": "hello world"
        })
        self.assertIn("11 chars", brief)
    
    def test_format_brief_grep(self):
        """Grep tool should format pattern and path."""
        brief = GREP.format_brief({"pattern": "TODO", "path": "./src"})
        self.assertIn("TODO", brief)
        self.assertIn("./src", brief)
    
    def test_format_brief_todowrite(self):
        """Todowrite tool should show todo count."""
        brief = TODOWRITE.format_brief({
            "todos": [
                {"id": "1", "content": "Task 1", "status": "pending"},
                {"id": "2", "content": "Task 2", "status": "completed"},
            ]
        })
        self.assertIn("2 todos", brief)
    
    def test_format_result_success(self):
        """Successful result should return content description (no icon)."""
        result = SHELL.format_result("output line", "completed")
        # Result should contain the output, no status icon (CLI adds it)
        self.assertIn("output line", result)
        self.assertNotIn("✓", result)  # Icon added by CLI, not here
    
    def test_format_result_error(self):
        """Error result should return error message (no icon)."""
        result = SHELL.format_result("Error message", "error")
        # Result should contain error info, no status icon (CLI adds it)
        self.assertIn("Error message", result)
        self.assertNotIn("❌", result)  # Icon added by CLI, not here
    
    def test_format_result_multiline(self):
        """Multiline output should show line count."""
        output = "line1\nline2\nline3"
        result = SHELL.format_result(output, "completed")
        self.assertIn("3 lines", result)
        self.assertNotIn("✓", result)  # Icon added by CLI, not here
    
    def test_to_llm_schema(self):
        """Tool should convert to LLM schema format."""
        schema = SHELL.to_llm_schema()
        
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "shell")
        self.assertIn("command", schema["function"]["parameters"]["properties"])
        self.assertIn("command", schema["function"]["parameters"]["required"])


class TestToolRegistry(unittest.TestCase):
    """Test ToolRegistry class."""
    
    def test_get_registry_singleton(self):
        """get_registry should return the same instance."""
        r1 = get_registry()
        r2 = get_registry()
        self.assertIs(r1, r2)
    
    def test_registry_has_default_tools(self):
        """Registry should have all default tools registered."""
        registry = ToolRegistry()
        
        # Core tools
        expected_tools = [
            "shell", "read", "write", "edit", "multiedit",
            "grep", "glob",
            "task", "todowrite", "todoread",
            "question", "batch",
        ]
        
        for tool_name in expected_tools:
            spec = registry.get(tool_name)
            self.assertIsNotNone(spec, f"Tool {tool_name} not found")
            self.assertEqual(spec.name, tool_name)
        
        # These tools were removed (can be done via shell)
        removed_tools = ["ls", "file_exists", "get_env"]
        for tool_name in removed_tools:
            spec = registry.get(tool_name)
            self.assertIsNone(spec, f"Tool {tool_name} should be removed")
    
    def test_get_llm_schemas(self):
        """get_llm_schemas should return valid schemas for all tools."""
        registry = ToolRegistry()
        schemas = registry.get_llm_schemas()
        
        self.assertGreater(len(schemas), 0)
        
        for schema in schemas:
            self.assertEqual(schema["type"], "function")
            self.assertIn("name", schema["function"])
            self.assertIn("description", schema["function"])
            self.assertIn("parameters", schema["function"])
    
    def test_format_tool_start(self):
        """format_tool_start should return complete event data."""
        registry = ToolRegistry()
        
        event = registry.format_tool_start("shell", {"command": "ls"})
        
        self.assertEqual(event["tool"], "shell")
        self.assertEqual(event["brief"], "$ ls")
        self.assertEqual(event["color"], Colors.YELLOW)
        self.assertEqual(event["category"], ToolCategory.SHELL)
    
    def test_format_tool_complete(self):
        """format_tool_complete should return complete event data."""
        registry = ToolRegistry()
        
        event = registry.format_tool_complete(
            "shell", "output", "completed", 1.5
        )
        
        self.assertEqual(event["tool"], "shell")
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["duration"], 1.5)
        self.assertIn("brief", event)
        self.assertFalse(event["show_output"])  # shell doesn't show output
    
    def test_format_tool_complete_with_output(self):
        """Tools with show_output=True should include output."""
        registry = ToolRegistry()
        
        event = registry.format_tool_complete(
            "todowrite", "Todo list updated", "completed", 0.1
        )
        
        self.assertTrue(event["show_output"])
        self.assertEqual(event["output"], "Todo list updated")
    
    def test_format_unknown_tool(self):
        """Unknown tool should return sensible defaults."""
        registry = ToolRegistry()
        
        event = registry.format_tool_start("unknown_tool", {})
        
        self.assertEqual(event["tool"], "unknown_tool")
        self.assertEqual(event["brief"], "unknown_tool")
        self.assertEqual(event["color"], Colors.WHITE)


class TestShowOutputFlag(unittest.TestCase):
    """Test that show_output flag is set correctly for each tool."""
    
    def test_tools_that_show_output(self):
        """These tools should show their output."""
        registry = ToolRegistry()
        
        show_output_tools = ["todowrite", "todoread", "question", "batch"]
        
        for tool_name in show_output_tools:
            spec = registry.get(tool_name)
            self.assertTrue(
                spec.show_output,
                f"{tool_name} should have show_output=True"
            )
    
    def test_tools_that_hide_output(self):
        """These tools should NOT show their output."""
        registry = ToolRegistry()
        
        hide_output_tools = [
            "shell", "read", "write", "edit", "multiedit",
            "grep", "glob", "task"
        ]
        
        for tool_name in hide_output_tools:
            spec = registry.get(tool_name)
            self.assertIsNotNone(spec, f"Tool {tool_name} not found")
            self.assertFalse(
                spec.show_output,
                f"{tool_name} should have show_output=False"
            )


if __name__ == "__main__":
    unittest.main()
