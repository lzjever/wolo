"""
用户提问系统

允许 LLM 向用户提问并等待回答，提升交互能力。

Usage:
    from wolo.question import ask_questions, QuestionInfo

    answers = await ask_questions(
        session_id="xxx",
        questions=[
            QuestionInfo(
                question="Which database?",
                options=[
                    QuestionOption(label="PostgreSQL", description="Recommended"),
                    QuestionOption(label="MySQL"),
                    QuestionOption(label="SQLite"),
                ]
            )
        ]
    )
"""

import asyncio
from dataclasses import dataclass, field

from wolo.events import bus

# ==================== 数据类型 ====================


@dataclass
class QuestionOption:
    """问题选项"""

    label: str
    """选项标签"""

    description: str = ""
    """选项描述"""


@dataclass
class QuestionInfo:
    """问题信息"""

    question: str
    """问题内容"""

    options: list[QuestionOption] = field(default_factory=list)
    """可选项（空列表表示自由输入）"""

    header: str = ""
    """问题标题"""

    allow_custom: bool = True
    """是否允许自定义输入"""


Answer = list[str]
"""答案类型（可能有多个选择）"""


class QuestionCancelledError(Exception):
    """用户取消提问"""

    pass


class QuestionTimeoutError(Exception):
    """提问超时"""

    pass


# ==================== 内部状态 ====================

# 存储待回答的问题
_pending_questions: dict[str, asyncio.Future] = {}


# ==================== 公开接口 ====================


async def ask_questions(
    session_id: str,
    questions: list[QuestionInfo],
    timeout: float = 300.0,  # 5 minutes
) -> list[Answer]:
    """
    向用户提问并等待回答。

    Args:
        session_id: 会话 ID
        questions: 问题列表
        timeout: 超时时间（秒）

    Returns:
        答案列表，与问题一一对应

    Raises:
        QuestionTimeoutError: 超时未回答
        QuestionCancelledError: 用户取消
    """
    if not questions:
        return []

    # 创建 Future 等待答案
    loop = asyncio.get_event_loop()
    future: asyncio.Future[list[Answer]] = loop.create_future()
    question_id = f"{session_id}_{id(future)}"
    _pending_questions[question_id] = future

    try:
        # 发布问题事件（异步）
        await bus.publish(
            "question-ask",
            {
                "question_id": question_id,
                "session_id": session_id,
                "questions": [
                    {
                        "question": q.question,
                        "options": [
                            {"label": o.label, "description": o.description} for o in q.options
                        ],
                        "header": q.header,
                        "allow_custom": q.allow_custom,
                    }
                    for q in questions
                ],
            },
        )

        # 等待答案
        answers = await asyncio.wait_for(future, timeout=timeout)
        return answers

    except asyncio.TimeoutError:
        await bus.publish("question-timeout", {"question_id": question_id})
        raise QuestionTimeoutError(f"Question timed out after {timeout}s")
    finally:
        _pending_questions.pop(question_id, None)


def submit_answers(question_id: str, answers: list[Answer]) -> bool:
    """
    提交问题答案（由 UI 调用）。

    Args:
        question_id: 问题 ID
        answers: 答案列表

    Returns:
        是否成功提交
    """
    future = _pending_questions.get(question_id)
    if future and not future.done():
        future.set_result(answers)
        return True
    return False


def cancel_question(question_id: str) -> bool:
    """
    取消问题（由 UI 调用）。

    Args:
        question_id: 问题 ID

    Returns:
        是否成功取消
    """
    future = _pending_questions.get(question_id)
    if future and not future.done():
        future.set_exception(QuestionCancelledError("User cancelled"))
        return True
    return False


def get_pending_question(question_id: str) -> asyncio.Future | None:
    """
    获取待回答的问题 Future。

    用于检查问题是否仍在等待回答。
    """
    return _pending_questions.get(question_id)


def has_pending_questions(session_id: str) -> bool:
    """
    检查会话是否有待回答的问题。
    """
    return any(qid.startswith(f"{session_id}_") for qid in _pending_questions)
