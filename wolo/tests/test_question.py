"""Question tool tests."""

import asyncio

import pytest

from wolo.question import (
    QuestionCancelledError,
    QuestionInfo,
    QuestionOption,
    QuestionTimeoutError,
    ask_questions,
    cancel_question,
    has_pending_questions,
    submit_answers,
)


class TestQuestionInfo:
    """QuestionInfo dataclass tests."""

    def test_basic_question(self):
        """Basic question creation."""
        q = QuestionInfo(question="What is your name?")
        assert q.question == "What is your name?"
        assert q.options == []
        assert q.header == ""
        assert q.allow_custom is True

    def test_question_with_options(self):
        """Question with options."""
        q = QuestionInfo(
            question="Choose a database",
            options=[
                QuestionOption(label="PostgreSQL", description="Recommended"),
                QuestionOption(label="MySQL"),
            ],
            header="Database Selection",
        )
        assert len(q.options) == 2
        assert q.options[0].label == "PostgreSQL"
        assert q.options[0].description == "Recommended"
        assert q.header == "Database Selection"


class TestAskQuestions:
    """ask_questions function tests."""

    @pytest.mark.asyncio
    async def test_empty_questions(self):
        """Empty questions list returns empty answers."""
        answers = await ask_questions("test_session", [])
        assert answers == []

    @pytest.mark.asyncio
    async def test_question_timeout(self):
        """Question times out if not answered."""
        with pytest.raises(QuestionTimeoutError):
            await ask_questions(
                "test_session",
                [QuestionInfo(question="Test?")],
                timeout=0.1,
            )

    @pytest.mark.asyncio
    async def test_submit_answers(self):
        """Answers can be submitted."""

        # Start question in background
        async def ask():
            return await ask_questions(
                "test_session",
                [QuestionInfo(question="Test?")],
                timeout=5.0,
            )

        task = asyncio.create_task(ask())

        # Wait a bit for the question to be registered
        await asyncio.sleep(0.1)

        # Find and submit answer
        # The question_id format is "{session_id}_{future_id}"
        for qid in list(get_pending_questions_ids()):
            if qid.startswith("test_session_"):
                submit_answers(qid, [["answer1"]])
                break

        answers = await task
        assert answers == [["answer1"]]

    @pytest.mark.asyncio
    async def test_cancel_question(self):
        """Question can be cancelled."""

        async def ask():
            return await ask_questions(
                "test_session_cancel",
                [QuestionInfo(question="Test?")],
                timeout=5.0,
            )

        task = asyncio.create_task(ask())
        await asyncio.sleep(0.1)

        # Cancel
        for qid in list(get_pending_questions_ids()):
            if qid.startswith("test_session_cancel_"):
                cancel_question(qid)
                break

        with pytest.raises(QuestionCancelledError):
            await task


class TestSubmitAnswers:
    """submit_answers function tests."""

    def test_submit_to_nonexistent(self):
        """Submit to non-existent question returns False."""
        result = submit_answers("nonexistent_id", [["answer"]])
        assert result is False


class TestCancelQuestion:
    """cancel_question function tests."""

    def test_cancel_nonexistent(self):
        """Cancel non-existent question returns False."""
        result = cancel_question("nonexistent_id")
        assert result is False


class TestHasPendingQuestions:
    """has_pending_questions function tests."""

    def test_no_pending(self):
        """No pending questions."""
        assert has_pending_questions("nonexistent_session") is False


# Helper to get pending question IDs
def get_pending_questions_ids():
    """Get all pending question IDs."""
    from wolo.question import _pending_questions

    return list(_pending_questions.keys())
