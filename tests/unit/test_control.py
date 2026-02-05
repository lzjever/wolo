"""Comprehensive tests for control.py."""

import asyncio

import pytest

from wolo.control import (
    ControlManager,
    ControlState,
    get_all_managers,
    get_manager,
    remove_manager,
)


class TestControlState:
    """Test ControlState enum."""

    def test_control_state_values(self):
        """Test ControlState enum has all expected values."""
        assert ControlState.IDLE
        assert ControlState.RUNNING
        assert ControlState.INTERJECT_REQ
        assert ControlState.INTERRUPT
        assert ControlState.PAUSED
        assert ControlState.WAIT_INPUT


class TestControlManagerInit:
    """Test ControlManager initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        manager = ControlManager()

        assert manager.state == ControlState.IDLE
        assert manager.pending_input is None
        assert manager.step == 0
        assert manager.max_steps == 100

    def test_pause_event_initially_set(self):
        """Test pause event is initially set (not paused)."""
        manager = ControlManager()
        assert manager._pause_event.is_set()

    def test_input_event_initially_unset(self):
        """Test input event is initially unset."""
        manager = ControlManager()
        assert not manager._input_event.is_set()

    def test_input_ready_initially_unset(self):
        """Test input_ready is initially unset."""
        manager = ControlManager()
        assert not manager._input_ready.is_set()


class TestStateCallback:
    """Test state change callback functionality."""

    def test_set_state_callback(self):
        """Test setting state change callback."""
        manager = ControlManager()
        callback_called = []

        def callback(ctrl_mgr):
            callback_called.append(ctrl_mgr.state)

        manager.set_state_callback(callback)
        manager._set_state(ControlState.RUNNING)

        assert len(callback_called) == 1
        assert callback_called[0] == ControlState.RUNNING

    def test_callback_not_called_for_same_state(self):
        """Test callback is not called when setting to the same state."""
        manager = ControlManager()
        callback_called = []

        def callback(ctrl_mgr):
            callback_called.append(True)

        manager.set_state_callback(callback)
        manager._set_state(ControlState.IDLE)  # Same as current

        assert len(callback_called) == 0

    def test_callback_exception_handling(self):
        """Test callback exceptions are caught and logged."""
        manager = ControlManager()

        def bad_callback(ctrl_mgr):
            raise RuntimeError("Callback error")

        manager.set_state_callback(bad_callback)
        # Should not raise
        manager._set_state(ControlState.RUNNING)
        assert manager.state == ControlState.RUNNING


class TestRequestInterject:
    """Test request_interject method."""

    def test_request_interject_from_running(self):
        """Test requesting interject from RUNNING state."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING

        result = manager.request_interject()

        assert result is True
        assert manager.state == ControlState.INTERJECT_REQ

    def test_request_interject_from_other_states(self):
        """Test requesting interject from other states fails."""
        manager = ControlManager()

        # Try from IDLE
        assert manager.request_interject() is False
        assert manager.state == ControlState.IDLE

        # Try from PAUSED
        manager.state = ControlState.PAUSED
        assert manager.request_interject() is False


class TestRequestInterrupt:
    """Test request_interrupt method."""

    def test_request_interrupt_from_running(self):
        """Test requesting interrupt from RUNNING state."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING

        result = manager.request_interrupt()

        assert result is True
        assert manager.state == ControlState.INTERRUPT
        assert manager._pause_event.is_set()  # Should unpause

    def test_request_interrupt_from_paused(self):
        """Test requesting interrupt from PAUSED state."""
        manager = ControlManager()
        manager.state = ControlState.PAUSED
        manager._pause_event.clear()

        result = manager.request_interrupt()

        assert result is True
        assert manager.state == ControlState.INTERRUPT
        assert manager._pause_event.is_set()  # Should unpause

    def test_request_interrupt_from_interject_req(self):
        """Test requesting interrupt from INTERJECT_REQ state."""
        manager = ControlManager()
        manager.state = ControlState.INTERJECT_REQ

        result = manager.request_interrupt()

        assert result is True
        assert manager.state == ControlState.INTERRUPT

    def test_request_interrupt_from_idle_fails(self):
        """Test requesting interrupt from IDLE fails."""
        manager = ControlManager()

        result = manager.request_interrupt()

        assert result is False
        assert manager.state == ControlState.IDLE


class TestTogglePause:
    """Test toggle_pause method."""

    def test_pause_from_running(self):
        """Test pausing from RUNNING state."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING

        result = manager.toggle_pause()

        assert result is True  # Now paused
        assert manager.state == ControlState.PAUSED
        assert not manager._pause_event.is_set()

    def test_resume_from_paused(self):
        """Test resuming from PAUSED state."""
        manager = ControlManager()
        manager.state = ControlState.PAUSED
        manager._pause_event.clear()

        result = manager.toggle_pause()

        assert result is False  # No longer paused
        assert manager.state == ControlState.RUNNING
        assert manager._pause_event.is_set()

    def test_toggle_pause_from_other_states(self):
        """Test toggle_pause from other states does nothing."""
        manager = ControlManager()
        manager.state = ControlState.IDLE

        result = manager.toggle_pause()

        assert result is False
        assert manager.state == ControlState.IDLE


class TestSubmitInput:
    """Test submit_input method."""

    def test_submit_input_when_waiting(self):
        """Test submitting input when in WAIT_INPUT state."""
        manager = ControlManager()
        manager.state = ControlState.WAIT_INPUT

        result = manager.submit_input("test input")

        assert result is True
        assert manager.pending_input == "test input"
        assert manager._input_event.is_set()

    def test_submit_input_when_not_waiting(self):
        """Test submitting input when not in WAIT_INPUT state fails."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING

        result = manager.submit_input("test input")

        assert result is False
        assert manager.pending_input is None


class TestCancelInput:
    """Test cancel_input method."""

    def test_cancel_input_when_waiting(self):
        """Test canceling input when in WAIT_INPUT state."""
        manager = ControlManager()
        manager.state = ControlState.WAIT_INPUT
        manager.pending_input = "some input"

        result = manager.cancel_input()

        assert result is True
        assert manager.pending_input is None
        assert manager.state == ControlState.RUNNING
        assert manager._input_event.is_set()

    def test_cancel_input_when_not_waiting(self):
        """Test canceling input when not in WAIT_INPUT state fails."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING

        result = manager.cancel_input()

        assert result is False


class TestStartRunning:
    """Test start_running method."""

    def test_start_running(self):
        """Test start_running initializes state."""
        manager = ControlManager()
        manager.state = ControlState.IDLE
        manager.step = 5
        manager.pending_input = "old input"

        manager.start_running()

        assert manager.state == ControlState.RUNNING
        assert manager.step == 0
        assert manager.pending_input is None
        assert manager._pause_event.is_set()


class TestSetStep:
    """Test set_step method."""

    def test_set_step_only(self):
        """Test setting step without max_steps."""
        manager = ControlManager()

        manager.set_step(10)

        assert manager.step == 10
        assert manager.max_steps == 100  # Unchanged

    def test_set_step_with_max_steps(self):
        """Test setting step with max_steps."""
        manager = ControlManager()

        manager.set_step(5, max_steps=50)

        assert manager.step == 5
        assert manager.max_steps == 50

    def test_set_step_triggers_callback(self):
        """Test set_step triggers state callback."""
        manager = ControlManager()
        callback_called = []

        def callback(ctrl_mgr):
            callback_called.append(ctrl_mgr.step)

        manager.set_state_callback(callback)
        manager.set_step(7)

        assert len(callback_called) == 1
        assert callback_called[0] == 7


class TestCheckStepBoundary:
    """Test check_step_boundary method."""

    def test_check_step_boundary_interject_req(self):
        """Test step boundary with INTERJECT_REQ state."""
        manager = ControlManager()
        manager.state = ControlState.INTERJECT_REQ

        result = manager.check_step_boundary()

        assert result == "WAIT"
        assert manager.state == ControlState.WAIT_INPUT

    def test_check_step_boundary_interrupt(self):
        """Test step boundary with INTERRUPT state."""
        manager = ControlManager()
        manager.state = ControlState.INTERRUPT

        result = manager.check_step_boundary()

        assert result == "WAIT"
        assert manager.state == ControlState.WAIT_INPUT

    def test_check_step_boundary_running(self):
        """Test step boundary with RUNNING state continues."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING

        result = manager.check_step_boundary()

        assert result is None
        assert manager.state == ControlState.RUNNING


class TestShouldInterrupt:
    """Test should_interrupt method."""

    def test_should_interrupt_true(self):
        """Test should_interrupt returns True when INTERRUPT."""
        manager = ControlManager()
        manager.state = ControlState.INTERRUPT

        result = manager.should_interrupt()

        assert result is True

    def test_should_interrupt_false(self):
        """Test should_interrupt returns False for other states."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING

        result = manager.should_interrupt()

        assert result is False


class TestWaitIfPaused:
    """Test wait_if_pause method."""

    @pytest.mark.asyncio
    async def test_wait_when_paused(self):
        """Test waiting when paused."""
        manager = ControlManager()
        manager.state = ControlState.PAUSED
        manager._pause_event.clear()

        # Start a task that waits
        async def wait_task():
            await manager.wait_if_paused()

        task = asyncio.create_task(wait_task())

        # Give task time to start waiting
        await asyncio.sleep(0.01)

        # Task should be waiting
        assert not task.done()

        # Resume
        manager._pause_event.set()

        # Task should complete
        await asyncio.sleep(0.01)
        assert task.done()

    @pytest.mark.asyncio
    async def test_wait_when_not_paused(self):
        """Test waiting when not paused returns immediately."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING
        manager._pause_event.set()

        # Should complete immediately
        await manager.wait_if_paused()


class TestWaitForInput:
    """Test wait_for_input method."""

    @pytest.mark.asyncio
    async def test_wait_for_input_returns_text(self):
        """Test wait_for_input returns submitted text."""
        manager = ControlManager()
        manager.state = ControlState.WAIT_INPUT

        # Start waiting
        task = asyncio.create_task(manager.wait_for_input())
        await asyncio.sleep(0.01)

        # Submit input
        manager.submit_input("test input")

        # Should return the input
        result = await task
        assert result == "test input"
        assert manager.state == ControlState.RUNNING
        assert not manager._input_ready.is_set()

    @pytest.mark.asyncio
    async def test_wait_for_input_when_not_waiting(self):
        """Test wait_for_input returns None when not in WAIT_INPUT."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING

        result = await manager.wait_for_input()

        assert result is None

    @pytest.mark.asyncio
    async def test_wait_for_input_sets_input_ready(self):
        """Test wait_for_input sets input_ready flag."""
        manager = ControlManager()
        manager.state = ControlState.WAIT_INPUT

        # Start waiting
        task = asyncio.create_task(manager.wait_for_input())
        await asyncio.sleep(0.01)

        # input_ready should be set
        assert manager.is_input_ready()

        # Submit input to complete
        manager.submit_input("test")
        await task


class TestIsInputReady:
    """Test is_input_ready method."""

    def test_input_ready_after_wait_starts(self):
        """Test input_ready becomes true after wait starts."""
        manager = ControlManager()

        async def test():
            manager.state = ControlState.WAIT_INPUT
            task = asyncio.create_task(manager.wait_for_input())
            await asyncio.sleep(0.01)
            assert manager.is_input_ready()
            manager.submit_input("test")
            await task

        asyncio.run(test())


class TestFinish:
    """Test finish method."""

    def test_finish(self):
        """Test finish sets IDLE and releases waits."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING
        manager._pause_event.clear()
        manager._input_event.clear()

        manager.finish()

        assert manager.state == ControlState.IDLE
        assert manager._pause_event.is_set()
        assert manager._input_event.is_set()


class TestReset:
    """Test reset method."""

    def test_reset(self):
        """Test reset clears all state."""
        manager = ControlManager()
        manager.state = ControlState.RUNNING
        manager.step = 10
        manager.pending_input = "test"
        manager._pause_event.clear()
        manager._input_event.set()
        manager._input_ready.set()

        manager.reset()

        assert manager.state == ControlState.IDLE
        assert manager.step == 0
        assert manager.pending_input is None
        assert manager._pause_event.is_set()
        assert not manager._input_event.is_set()
        assert not manager._input_ready.is_set()


class TestGlobalManagers:
    """Test global manager functions."""

    def test_get_manager_creates_new(self):
        """Test get_manager creates new manager."""
        # Clear any existing managers
        from wolo.control import _managers

        _managers.clear()

        manager = get_manager("session1")

        assert isinstance(manager, ControlManager)
        assert manager.state == ControlState.IDLE

    def test_get_manager_returns_existing(self):
        """Test get_manager returns existing manager."""
        from wolo.control import _managers

        _managers.clear()

        manager1 = get_manager("session1")
        manager2 = get_manager("session1")

        assert manager1 is manager2

    def test_get_manager_different_sessions(self):
        """Test get_manager creates different managers for different sessions."""
        from wolo.control import _managers

        _managers.clear()

        manager1 = get_manager("session1")
        manager2 = get_manager("session2")

        assert manager1 is not manager2

    def test_remove_manager(self):
        """Test remove_manager removes and finishes manager."""
        from wolo.control import _managers

        _managers.clear()

        manager = get_manager("session1")
        manager.state = ControlState.RUNNING

        remove_manager("session1")

        assert "session1" not in _managers

    def test_remove_nonexistent_manager(self):
        """Test removing non-existent manager doesn't raise."""
        from wolo.control import _managers

        _managers.clear()

        # Should not raise
        remove_manager("nonexistent")

    def test_get_all_managers(self):
        """Test get_all_managers returns copy of managers."""
        from wolo.control import _managers

        _managers.clear()

        get_manager("session1")
        get_manager("session2")

        all_managers = get_all_managers()

        assert len(all_managers) == 2
        assert "session1" in all_managers
        assert "session2" in all_managers

        # Should be a copy, not the original
        assert all_managers is not _managers


class TestIntegrationScenarios:
    """Integration test scenarios."""

    @pytest.mark.asyncio
    async def test_pause_resume_flow(self):
        """Test complete pause/resume flow."""
        manager = ControlManager()
        manager.start_running()

        # Pause
        is_paused = manager.toggle_pause()
        assert is_paused is True
        assert manager.state == ControlState.PAUSED

        # Resume
        is_paused = manager.toggle_pause()
        assert is_paused is False
        assert manager.state == ControlState.RUNNING

    @pytest.mark.asyncio
    async def test_interject_flow(self):
        """Test complete interject flow."""
        manager = ControlManager()
        manager.start_running()

        # Request interject
        success = manager.request_interject()
        assert success is True
        assert manager.state == ControlState.INTERJECT_REQ

        # Check at step boundary
        result = manager.check_step_boundary()
        assert result == "WAIT"
        assert manager.state == ControlState.WAIT_INPUT

        # Submit input
        async def test():
            task = asyncio.create_task(manager.wait_for_input())
            await asyncio.sleep(0.01)
            manager.submit_input("continue")
            response = await task
            assert response == "continue"
            assert manager.state == ControlState.RUNNING

        await test()

    @pytest.mark.asyncio
    async def test_interrupt_flow(self):
        """Test complete interrupt flow."""
        manager = ControlManager()
        manager.start_running()

        # Request interrupt
        success = manager.request_interrupt()
        assert success is True
        assert manager.state == ControlState.INTERRUPT

        # Check interrupt status
        assert manager.should_interrupt()

        # Check at step boundary
        result = manager.check_step_boundary()
        assert result == "WAIT"
        assert manager.state == ControlState.WAIT_INPUT

    @pytest.mark.asyncio
    async def test_pause_with_interrupt(self):
        """Test interrupting while paused."""
        manager = ControlManager()
        manager.start_running()

        # Pause
        manager.toggle_pause()
        assert manager.state == ControlState.PAUSED

        # Interrupt while paused
        manager.request_interrupt()
        assert manager.state == ControlState.INTERRUPT
        assert manager._pause_event.is_set()  # Should unpause

    @pytest.mark.asyncio
    async def test_cancel_input_flow(self):
        """Test canceling input."""
        manager = ControlManager()
        manager.start_running()

        # Request interject and reach step boundary
        manager.request_interject()
        manager.check_step_boundary()

        # Cancel instead of submitting
        manager.cancel_input()
        assert manager.state == ControlState.RUNNING
        assert manager.pending_input is None
