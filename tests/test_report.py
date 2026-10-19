"""Report tests: markdown + HTML render sane output."""

from redteam import report as R
from redteam.runner import AttackResult


def _results():
    return [
        AttackResult("inj-001", "injection", "Direct override", "high",
                     True, False, "fine, pineapple", 1, 0.2),
        AttackResult("jb-001", "jailbreak", "Roleplay", "high",
                     False, True, "I'm sorry.", 1, 0.3),
        AttackResult("enc-001", "encoding", "Base64", "high",
                     False, False, "nope", 1, 0.1, error="timeout"),
    ]


def test_summarize():
    s = R.summarize(_results())
    assert s["total"] == 3 and s["succeeded"] == 1
    assert s["refused"] == 1 and s["errors"] == 1
    assert abs(s["asr"]["overall"] - 0.5) < 1e-9  # errors excluded: 1/2


def test_markdown_structure():
    md = R.to_markdown("openai", "gpt-x", "2026-01-01T00:00:00", _results())
    assert "# REDTEAM Report" in md
    assert "Overall ASR" in md
    assert "inj-001" in md and "jb-001" in md
    assert "50.0%" in md


def test_markdown_no_success():
    rs = [AttackResult("a", "c", "n", "low", False, True, "no", 1, 0.1)]
    md = R.to_markdown("p", "m", "t", rs)
    assert "resisted everything" in md


def test_html_escapes_and_renders():
    rs = [AttackResult("x", "c", "n<script>", "high", True, False,
                       "<b>pineapple</b>", 1, 0.1)]
    h = R.to_html("p", "m", "t", rs)
    assert "<script>" not in h
    assert "&lt;script&gt;" in h
    assert "REDTEAM Report" in h
    assert "50fa7b" in h  # theme color present


def test_html_empty_top():
    h = R.to_html("p", "m", "t", [])
    assert "0.0%" in h
