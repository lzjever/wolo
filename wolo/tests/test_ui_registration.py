"""UI registration mechanism tests."""
import pytest

from wolo.ui import SimpleUI, get_current_ui, register_ui, unregister_ui
from wolo.control import ControlManager


class TestUIRegistration:
    """UI registration mechanism tests."""

    def test_register_and_get(self):
        """Test registering and getting UI instance."""
        # Initially should be None
        assert get_current_ui() is None

        # Create a UI instance
        manager = ControlManager()
        ui = SimpleUI(manager, terminal=None)  # terminal is optional

        # Register it
        register_ui(ui)

        # Should be able to get it
        assert get_current_ui() is ui

        # Unregister
        unregister_ui()

        # Should be None again
        assert get_current_ui() is None

    def test_unregister_when_none(self):
        """Test unregistering when no UI is registered."""
        # Should not raise an error
        unregister_ui()
        assert get_current_ui() is None

    def test_replace_ui(self):
        """Test replacing one UI with another."""
        manager1 = ControlManager()
        ui1 = SimpleUI(manager1, terminal=None)

        manager2 = ControlManager()
        ui2 = SimpleUI(manager2, terminal=None)

        # Register first UI
        register_ui(ui1)
        assert get_current_ui() is ui1

        # Replace with second UI
        register_ui(ui2)
        assert get_current_ui() is ui2
        assert get_current_ui() is not ui1

        # Cleanup
        unregister_ui()
