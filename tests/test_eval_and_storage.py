import sqlite3

import pytest

from api.interview import Scores
from bot.main_bot import split_message
from database.db_manager import init_db, save_report
from eval.scoring_eval import summarise


def test_summarise_separates_noise_from_tier_gap():
    scores = {
        "high_1": [90, 92], "high_2": [88, 90],
        "mid_1": [50, 54], "mid_2": [52, 50],
        "low_1": [10, 12], "low_2": [None, 10],
    }
    s = summarise(scores)
    assert s["unparsed"] == 1
    assert s["tiers_in_order"]
    assert s["separation_high_minus_low"] == pytest.approx(90 - 32 / 3)
    # Pooled SD is dominated by the gap between tiers, not by noise
    assert s["pooled_sd_reference_only"] > 10 * s["within_tier_sd"]


def test_report_is_saved_with_parsed_scores(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    save_report("u1", "full text", Scores(30, 20, 25, 75), db_path=db)
    save_report("u2", "unparsable", Scores(None, None, None, None), db_path=db)
    rows = sqlite3.connect(db).execute("SELECT user_id, overall FROM reports ORDER BY id").fetchall()
    assert rows == [("u1", 75), ("u2", None)]


def test_split_message_respects_discord_limit():
    text = "\n".join("line %d " % i + "x" * 90 for i in range(60))
    parts = split_message(text, limit=2000)
    assert all(len(p) <= 2000 for p in parts)
    assert "".join(parts).replace("\n", "") == text.replace("\n", "")
