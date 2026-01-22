"""Configuration schema validation and documentation.

This module provides utilities to validate configuration and generate
documentation from configuration classes.
"""

from typing import Any, get_type_hints, get_origin, get_args
from dataclasses import fields, is_dataclass
import inspect


def get_config_schema(config_class: type) -> dict[str, Any]:
    """Generate a schema dictionary from a configuration dataclass.
    
    Args:
        config_class: A dataclass configuration class
        
    Returns:
        Dictionary describing the configuration schema
    """
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    
    if not is_dataclass(config_class):
        return schema
    
    type_hints = get_type_hints(config_class)
    
    for field in fields(config_class):
        field_info = {
            "description": field.metadata.get("description", ""),
            "default": field.default if field.default != inspect.Parameter.empty else None,
        }
        
        # Get type information
        field_type = type_hints.get(field.name, field.type)
        
        # Handle Optional types
        origin = get_origin(field_type)
        if origin is not None:
            args = get_args(field_type)
            if len(args) == 2 and type(None) in args:
                # Optional type
                field_info["nullable"] = True
                field_info["type"] = _python_type_to_json_type(args[0] if args[0] != type(None) else args[1])
            elif origin is list:
                field_info["type"] = "array"
                if args:
                    field_info["items"] = {"type": _python_type_to_json_type(args[0])}
            elif origin is dict:
                field_info["type"] = "object"
                if args:
                    field_info["additionalProperties"] = True
            elif origin is tuple:
                field_info["type"] = "array"
        else:
            field_info["type"] = _python_type_to_json_type(field_type)
        
        # Check if required
        if field.default == inspect.Parameter.empty:
            schema["required"].append(field.name)
        
        schema["properties"][field.name] = field_info
        
        # Handle nested dataclasses
        if is_dataclass(field_type):
            field_info["properties"] = get_config_schema(field_type).get("properties", {})
    
    return schema


def _python_type_to_json_type(python_type: type) -> str:
    """Convert Python type to JSON schema type string."""
    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        tuple: "array",
    }
    
    return type_mapping.get(python_type, "string")


def generate_config_docs(config_class: type, indent: int = 0) -> str:
    """Generate markdown documentation from a configuration class.
    
    Args:
        config_class: A dataclass configuration class
        indent: Indentation level for nested configs
        
    Returns:
        Markdown documentation string
    """
    lines = []
    prefix = "  " * indent
    
    if not is_dataclass(config_class):
        return ""
    
    type_hints = get_type_hints(config_class)
    
    for field in fields(config_class):
        field_type = type_hints.get(field.name, field.type)
        type_str = _format_type(field_type)
        
        default_str = ""
        if field.default != inspect.Parameter.empty:
            if callable(field.default):
                default_str = " (default: factory function)"
            else:
                default_str = f" (default: {field.default!r})"
        
        # Get docstring from class if available
        doc = ""
        if hasattr(config_class, "__doc__") and config_class.__doc__:
            # Try to extract field description from docstring
            pass
        
        line = f"{prefix}- `{field.name}` ({type_str}){default_str}"
        if doc:
            line += f": {doc}"
        lines.append(line)
        
        # Handle nested dataclasses
        origin = get_origin(field_type)
        if origin is None and is_dataclass(field_type):
            lines.append(f"{prefix}  Nested configuration:")
            nested_docs = generate_config_docs(field_type, indent + 1)
            if nested_docs:
                lines.append(nested_docs)
    
    return "\n".join(lines)


def _format_type(python_type: type) -> str:
    """Format Python type as a readable string."""
    origin = get_origin(python_type)
    
    if origin is None:
        return python_type.__name__
    
    args = get_args(python_type)
    
    if origin is list:
        if args:
            return f"list[{_format_type(args[0])}]"
        return "list"
    elif origin is dict:
        if args:
            return f"dict[{_format_type(args[0])}, {_format_type(args[1])}]"
        return "dict"
    elif origin is tuple:
        if args:
            formatted_args = ", ".join(_format_type(arg) for arg in args)
            return f"tuple[{formatted_args}]"
        return "tuple"
    elif hasattr(origin, "__name__"):
        return origin.__name__
    
    return str(python_type)


def validate_config_value(value: Any, field_type: type, field_name: str) -> tuple[bool, str | None]:
    """Validate a configuration value against its expected type.
    
    Args:
        value: Value to validate
        field_type: Expected type
        field_name: Name of the field (for error messages)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    origin = get_origin(field_type)
    
    if origin is None:
        # Simple type check
        if not isinstance(value, field_type):
            return False, f"{field_name} must be of type {field_type.__name__}, got {type(value).__name__}"
    elif origin is list:
        if not isinstance(value, list):
            return False, f"{field_name} must be a list, got {type(value).__name__}"
        args = get_args(field_type)
        if args:
            item_type = args[0]
            for i, item in enumerate(value):
                is_valid, error = validate_config_value(item, item_type, f"{field_name}[{i}]")
                if not is_valid:
                    return False, error
    elif origin is dict:
        if not isinstance(value, dict):
            return False, f"{field_name} must be a dict, got {type(value).__name__}"
    
    return True, None
