"""Interview flow: a small state machine around an LLM.

The LLM never decides when the interview moves on or ends. Code does: each
stage has its own instruction, and after the last answer the session switches
to the scoring prompt and is closed.
"""
import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Awaitable, Callable, Optional

LLMCall = Callable[[list[dict]], Awaitable[str]]

INTERVIEWER_PROMPT = """You are a senior technical interviewer at a large tech company.
Rules:
1. Ask exactly one question per message. Do not teach or explain the answer.
2. If the candidate cannot answer, say so briefly and move on.
3. Be professional, concise and direct."""


class Stage(IntEnum):
    AWAITING_TOPIC = 0   # first message: the candidate names a topic
    FUNDAMENTALS = 1     # answer to question 1 expected
    DEEP_DIVE = 2        # answer to question 2 expected
    SCENARIO = 3         # answer to question 3 expected
    FINISHED = 4


# Instruction for the question asked after the candidate's message in each stage
STAGE_INSTRUCTIONS = {
    Stage.AWAITING_TOPIC: "Task: question 1 of 3, fundamentals. Ask one classic core-concept "
                          "question about the topic the candidate chose.",
    Stage.FUNDAMENTALS: "Task: question 2 of 3, deep dive. Pick one detail from the previous "
                        "answer and ask how it works underneath. If the previous answer was "
                        "wrong or empty, ask a slightly harder conceptual question instead.",
    Stage.DEEP_DIVE: "Task: question 3 of 3, applied scenario. Describe a realistic production "
                     "incident or engineering requirement and ask the candidate how they would "
                     "design or fix it using this technology.",
}

# Structured rubric. The same text is used by eval/scoring_eval.py, so the
# evaluation measures the prompt that actually runs in production.
RUBRIC_PROMPT = """The interview is over. You are now on the hiring panel.
Score the candidate on the whole conversation using three dimensions:
- Knowledge depth (0-40)
- Logical rigour (0-30)
- Clarity of expression (0-30)

Reply in exactly this format:
### Interview assessment
Knowledge depth: <score>/40
Logical rigour: <score>/30
Clarity: <score>/30
Overall: <sum>/100

Strengths: <one sentence>
Weaknesses: <one sentence>
Advice: <specific next steps>"""

# Variant that makes the judge verify the candidate's claims before scoring.
# Tested against RUBRIC_PROMPT in eval/scoring_eval.py.
FACT_CHECK_RUBRIC_PROMPT = """The interview is over. You are now on the hiring panel.
First, list every technical claim the candidate made (complexities, definitions,
how something works) and mark each one CORRECT or WRONG using your own knowledge.
Confident or fluent wording is not evidence; only correctness counts.

Then score three dimensions:
- Knowledge depth (0-40): at most 15 if any core claim is WRONG
- Logical rigour (0-30)
- Clarity of expression (0-30): clear but wrong explanations still lose points under knowledge

Reply in exactly this format:
### Fact check
- <claim>: CORRECT or WRONG
### Interview assessment
Knowledge depth: <score>/40
Logical rigour: <score>/30
Clarity: <score>/30
Overall: <sum>/100

Strengths: <one sentence>
Weaknesses: <one sentence>
Advice: <specific next steps>"""

FINISH_NOTE = "[The interview is over. Do not answer any question. Write the assessment now.]"
RESTART_WORDS = {"restart", "/restart"}
MAX_HISTORY = 10


@dataclass
class Scores:
    knowledge: Optional[int]
    logic: Optional[int]
    clarity: Optional[int]
    overall: Optional[int]


def parse_scores(report: str) -> Scores:
    """Pull the numbers out of a rubric report; missing ones become None."""
    def grab(label: str) -> Optional[int]:
        m = re.search(rf"{label}\s*:\s*\**\s*(\d+)\s*\**\s*/", report, flags=re.IGNORECASE)
        return int(m.group(1)) if m else None
    return Scores(grab("Knowledge depth"), grab("Logical rigour"), grab("Clarity"), grab("Overall"))


@dataclass
class InterviewSession:
    stage: Stage = Stage.AWAITING_TOPIC
    history: list[dict] = field(default_factory=list)


@dataclass
class Reply:
    text: str
    finished: bool = False
    report: Optional[str] = None
    scores: Optional[Scores] = None


class Interviewer:
    def __init__(self, llm: LLMCall):
        self.llm = llm
        self.sessions: dict[str, InterviewSession] = {}

    async def handle(self, user_id: str, message: str) -> Reply:
        session = self.sessions.setdefault(user_id, InterviewSession())

        if session.stage == Stage.FINISHED:
            if message.strip().lower() in RESTART_WORDS:
                self.sessions[user_id] = InterviewSession()
                return Reply("New interview started. Which technical topic would you like to be tested on?")
            return Reply("This interview has finished. Send 'restart' to start a new one.")

        is_final = session.stage == Stage.SCENARIO
        if is_final:
            system_prompt = RUBRIC_PROMPT
            user_content = f"{message}\n\n{FINISH_NOTE}"
        else:
            system_prompt = f"{INTERVIEWER_PROMPT}\n\n{STAGE_INSTRUCTIONS[session.stage]}"
            user_content = message

        history = session.history + [{"role": "user", "content": user_content}]
        payload = [{"role": "system", "content": system_prompt}] + history[-MAX_HISTORY:]

        # If the call raises, the session is left unchanged and the user can resend.
        reply = await self.llm(payload)

        session.history = history + [{"role": "assistant", "content": reply}]
        session.stage = Stage(session.stage + 1)

        if is_final:
            return Reply(reply, finished=True, report=reply, scores=parse_scores(reply))
        return Reply(reply)
