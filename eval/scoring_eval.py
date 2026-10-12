"""Compare two scoring prompts for the LLM judge.

Each of the 9 graded answers in cases.json (3 strong, 3 partly wrong, 3 weak)
is scored `--repeats` times by each prompt. A good judge should
  * give the same answer the same score on every repeat (repeatability),
  * give similar answers of the same quality similar scores (within-tier SD),
  * keep strong and weak answers far apart (separation).

The SD of all scores pooled together is reported for reference only: it mixes
the gap between tiers (which we want to be large) with noise (which we want to
be small), so on its own it cannot say whether a prompt got better or worse.

Usage (from the repository root, with LLM_API_KEY set):
    python -m eval.scoring_eval --repeats 5
"""
import argparse
import asyncio
import json
import os
import statistics
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from api.interview import FACT_CHECK_RUBRIC_PROMPT, RUBRIC_PROMPT, parse_scores

HERE = Path(__file__).resolve().parent
TIERS = ("high", "mid", "low")

BASELINE_PROMPT = """You are a technical interviewer. Give the candidate's answer one overall score from 0 to 100.
Reply with exactly one line: Overall: <score>/100"""

PROMPTS = {"baseline": BASELINE_PROMPT, "rubric": RUBRIC_PROMPT, "rubric_fact_check": FACT_CHECK_RUBRIC_PROMPT}


def summarise(scores: dict[str, list]) -> dict:
    """scores maps answer id ('high_1', ...) to the scores of its repeats (None = unparsable)."""
    valid = {k: [s for s in v if s is not None] for k, v in scores.items()}
    failed = sum(len(v) - len(valid[k]) for k, v in scores.items())

    tier_scores = {t: [s for k, v in valid.items() if k.startswith(t) for s in v] for t in TIERS}
    tier_mean = {t: statistics.mean(v) for t, v in tier_scores.items()}
    tier_sd = {t: statistics.stdev(v) for t, v in tier_scores.items()}
    repeat_sd = statistics.mean(statistics.stdev(v) for v in valid.values() if len(v) > 1)
    within_sd = statistics.mean(sd ** 2 for sd in tier_sd.values()) ** 0.5
    separation = tier_mean["high"] - tier_mean["low"]

    return {
        "unparsed": failed,
        "tier_mean": tier_mean,
        "tier_sd": tier_sd,
        "repeat_sd": repeat_sd,
        "within_tier_sd": within_sd,
        "separation_high_minus_low": separation,
        "separation_over_within_sd": separation / within_sd,
        "tiers_in_order": tier_mean["high"] > tier_mean["mid"] > tier_mean["low"],
        "pooled_sd_reference_only": statistics.stdev(s for v in tier_scores.values() for s in v),
    }


async def score_once(client, model, sem, prompt, question, answer, temperature):
    async with sem:
        try:
            r = await client.chat.completions.create(
                model=model, temperature=temperature,
                messages=[{"role": "system", "content": prompt},
                          {"role": "user", "content": f"Question: {question}\nCandidate's answer: {answer}"}],
            )
        except Exception as exc:
            print(f"request failed: {exc}")
            return None
        return parse_scores(r.choices[0].message.content).overall


async def run(repeats: int, temperature: float, concurrency: int) -> dict:
    load_dotenv()
    client = AsyncOpenAI(api_key=os.getenv("LLM_API_KEY"),
                         base_url=os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"))
    model = os.getenv("LLM_MODEL", "glm-4-flash")
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    sem = asyncio.Semaphore(concurrency)

    raw = {}
    for name, prompt in PROMPTS.items():
        jobs = {aid: [score_once(client, model, sem, prompt, cases["question"], text, temperature)
                      for _ in range(repeats)]
                for aid, text in cases["answers"].items()}
        raw[name] = {aid: await asyncio.gather(*js) for aid, js in jobs.items()}
        print(f"{name}: done")

    return {"model": model, "temperature": temperature, "repeats": repeats, "raw": raw,
            "summary": {name: summarise(s) for name, s in raw.items()}}


def print_table(summary: dict) -> None:
    rows = [("Mean score, strong / partly wrong / weak", lambda s: " / ".join(f"{s['tier_mean'][t]:.1f}" for t in TIERS)),
            ("Repeatability: SD across repeats of one answer", lambda s: f"{s['repeat_sd']:.1f}"),
            ("Within-tier SD", lambda s: f"{s['within_tier_sd']:.1f}"),
            ("Separation (strong minus weak)", lambda s: f"{s['separation_high_minus_low']:.1f}"),
            ("Separation / within-tier SD", lambda s: f"{s['separation_over_within_sd']:.2f}"),
            ("Tiers in the right order", lambda s: str(s["tiers_in_order"])),
            ("Unparsable replies", lambda s: str(s["unparsed"])),
            ("Pooled SD (reference only)", lambda s: f"{s['pooled_sd_reference_only']:.1f}")]
    names = list(summary)
    print("| Metric | " + " | ".join(names) + " |")
    print("|---|" + "---:|" * len(names))
    for label, fmt in rows:
        print(f"| {label} | " + " | ".join(fmt(summary[n]) for n in names) + " |")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    result = asyncio.run(run(args.repeats, args.temperature, args.concurrency))
    out = HERE / "results" / f"run_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print_table(result["summary"])
    print(f"\nRaw scores saved to {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
