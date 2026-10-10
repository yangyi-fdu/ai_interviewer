import asyncio

import pytest

from api.interview import RUBRIC_PROMPT, STAGE_INSTRUCTIONS, Interviewer, Stage, parse_scores

REPORT = """### Interview assessment
Knowledge depth: 31/40
Logical rigour: 22/30
Clarity: **25**/30
Overall: 78/100

Strengths: clear structure."""


class FakeLLM:
    def __init__(self, fail_on_call=None):
        self.calls = []
        self.fail_on_call = fail_on_call

    async def __call__(self, messages):
        self.calls.append(messages)
        if len(self.calls) == self.fail_on_call:
            raise RuntimeError("API down")
        return REPORT if messages[0]["content"] == RUBRIC_PROMPT else f"question {len(self.calls)}"


def run(coro):
    return asyncio.run(coro)


def test_full_interview_walks_through_every_stage_then_scores():
    llm = FakeLLM()
    bot = Interviewer(llm)
    replies = [run(bot.handle("u", m)) for m in ["Python", "answer 1", "answer 2", "answer 3"]]

    system_prompts = [call[0]["content"] for call in llm.calls]
    assert STAGE_INSTRUCTIONS[Stage.AWAITING_TOPIC] in system_prompts[0]
    assert STAGE_INSTRUCTIONS[Stage.FUNDAMENTALS] in system_prompts[1]
    assert STAGE_INSTRUCTIONS[Stage.DEEP_DIVE] in system_prompts[2]
    assert system_prompts[3] == RUBRIC_PROMPT

    assert [r.finished for r in replies] == [False, False, False, True]
    assert replies[-1].scores.overall == 78
    assert bot.sessions["u"].stage == Stage.FINISHED


def test_finished_session_ignores_messages_until_restart():
    llm = FakeLLM()
    bot = Interviewer(llm)
    for m in ["Python", "a", "b", "c"]:
        run(bot.handle("u", m))
    calls_before = len(llm.calls)

    assert "finished" in run(bot.handle("u", "one more question?")).text
    assert len(llm.calls) == calls_before
    run(bot.handle("u", "restart"))
    assert bot.sessions["u"].stage == Stage.AWAITING_TOPIC


def test_failed_llm_call_leaves_the_session_unchanged():
    bot = Interviewer(FakeLLM(fail_on_call=2))
    run(bot.handle("u", "Python"))
    with pytest.raises(RuntimeError):
        run(bot.handle("u", "answer 1"))
    session = bot.sessions["u"]
    assert session.stage == Stage.FUNDAMENTALS
    assert len(session.history) == 2

    run(bot.handle("u", "answer 1"))  # resending works
    assert session.stage == Stage.DEEP_DIVE


def test_users_have_separate_sessions():
    bot = Interviewer(FakeLLM())
    run(bot.handle("alice", "Python"))
    run(bot.handle("alice", "answer"))
    run(bot.handle("bob", "C++"))
    assert bot.sessions["alice"].stage == Stage.DEEP_DIVE
    assert bot.sessions["bob"].stage == Stage.FUNDAMENTALS


def test_parse_scores_handles_markdown_and_missing_values():
    s = parse_scores(REPORT)
    assert (s.knowledge, s.logic, s.clarity, s.overall) == (31, 22, 25, 78)
    assert parse_scores("no numbers here").overall is None
