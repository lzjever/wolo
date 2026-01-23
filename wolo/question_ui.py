"""
Question UI Handler.

Handles AI questions by displaying them to the user and collecting answers.
Subscribes to question events and provides interactive prompts.

The question flow:
1. AI calls 'question' tool -> ask_questions() publishes 'question-ask' event (async)
2. QuestionHandler._on_question_ask() displays questions and collects answers (async)
3. Answers are submitted back via submit_answers()
4. ask_questions() returns with the answers
"""

import logging
import sys
from typing import Optional

from wolo.events import bus
from wolo.question import cancel_question, submit_answers

logger = logging.getLogger(__name__)


# ANSI Colors (matching ui.py)
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


# Global state
_question_handler: Optional["QuestionHandler"] = None


class QuestionHandler:
    """
    Handles AI questions interactively.

    When the AI uses the 'question' tool, this handler:
    1. Displays the questions to the user (immediately in event callback)
    2. Collects answers via input prompts
    3. Submits answers back to the waiting tool
    """

    def __init__(self):
        """Initialize question handler."""
        self._active = False

    def start(self):
        """Start listening for question events."""
        if self._active:
            return

        self._active = True
        bus.subscribe("question-ask", self._on_question_ask)
        bus.subscribe("question-timeout", self._on_question_timeout)
        logger.debug("Question handler started")

    def stop(self):
        """Stop listening for question events."""
        self._active = False
        logger.debug("Question handler stopped")

    async def _on_question_ask(self, data: dict):
        """
        Handle question-ask event (async).

        This is called asynchronously from ask_questions() via the async event bus.
        Uses the same UI input method as interject/interrupt for consistency.
        """
        if not self._active:
            return

        question_id = data["question_id"]
        questions = data["questions"]

        logger.debug(f"Question received: {question_id}")

        # Check if we're in a TTY (can do interactive input)
        if not sys.stdin.isatty():
            logger.warning("Not a TTY, cannot collect answers interactively")
            cancel_question(question_id)
            return

        # Get UI instance (registered by agent_loop)
        from wolo.ui import get_current_ui

        ui = get_current_ui()

        if not ui:
            logger.warning("No UI available for question input")
            cancel_question(question_id)
            return

        # Get ControlManager through UI to set WAIT_INPUT state
        # This prevents KeyboardListener from competing with prompt_toolkit for stdin
        control = ui.manager if hasattr(ui, "manager") else None
        old_state = None

        if control:
            from wolo.control import ControlState

            old_state = control.state
            control._set_state(ControlState.WAIT_INPUT)
            logger.debug("Set control state to WAIT_INPUT for question input")

        # Display question header
        print(f"\n{Colors.CYAN}{'─' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}│ 🤖 AI 需要你的回答{Colors.RESET}")
        print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")

        answers = []
        cancelled = False

        try:
            for i, q in enumerate(questions, 1):
                # Display question
                header = q.get("header", "")
                if header:
                    print(f"\n{Colors.YELLOW}{header}{Colors.RESET}")

                print(f"\n{Colors.WHITE}Q{i}: {q['question']}{Colors.RESET}")

                # Display options if available
                options = q.get("options", [])
                if options:
                    for j, opt in enumerate(options, 1):
                        label = opt.get("label", "")
                        desc = opt.get("description", "")
                        desc_text = f" - {Colors.DIM}{desc}{Colors.RESET}" if desc else ""
                        print(f"  {Colors.GREEN}{j}.{Colors.RESET} {label}{desc_text}")

                    if q.get("allow_custom", True):
                        print(f"  {Colors.DIM}(或输入自定义答案){Colors.RESET}")

                # Get user input using UI's async input method (same as interject/interrupt)
                # This ensures consistent behavior and proper wide character support
                try:
                    print(f"{Colors.DIM}(输入答案，Esc 取消，Ctrl+C 中断){Colors.RESET}")
                    answer = await ui.prompt_for_input()

                    if answer is None:
                        # User cancelled (Esc)
                        print(f"\n{Colors.YELLOW}[已取消]{Colors.RESET}")
                        cancelled = True
                        break

                    # If user entered a number and there are options, convert to label
                    if options and answer.isdigit():
                        idx = int(answer) - 1
                        if 0 <= idx < len(options):
                            answer = options[idx].get("label", answer)

                    answers.append([answer])

                except KeyboardInterrupt:
                    print(f"\n{Colors.YELLOW}[已中断]{Colors.RESET}")
                    cancelled = True
                    break
                except Exception as e:
                    logger.error(f"Error getting user input: {e}")
                    print(f"\n{Colors.RED}[输入错误: {e}]{Colors.RESET}")
                    cancelled = True
                    break
        finally:
            # Restore original control state
            if control and old_state:
                from wolo.control import ControlState

                control._set_state(old_state)
                logger.debug(f"Restored control state to {old_state}")

        # Submit or cancel
        if cancelled:
            cancel_question(question_id)
            print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}\n")
        else:
            submit_answers(question_id, answers)
            print(f"\n{Colors.GREEN}[答案已提交]{Colors.RESET}")
            print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}\n")

    def _on_question_timeout(self, data: dict):
        """Handle question-timeout event."""
        question_id = data.get("question_id")
        print(f"\n{Colors.RED}[问题超时: {question_id}]{Colors.RESET}")


def setup_question_handler() -> QuestionHandler:
    """
    Set up the global question handler.

    Returns:
        QuestionHandler instance
    """
    global _question_handler

    if _question_handler is None:
        _question_handler = QuestionHandler()

    _question_handler.start()
    return _question_handler


def cleanup_question_handler():
    """Clean up the question handler."""
    global _question_handler

    if _question_handler:
        _question_handler.stop()
