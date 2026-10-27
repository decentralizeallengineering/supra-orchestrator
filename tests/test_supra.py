import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from supra.cli import main


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPRA_HOME", str(tmp_path))
    monkeypatch.setenv("SUPRA_NOW", "2026-03-01 09:00")
    return tmp_path


def test_order_new_keeps_words_verbatim(ws, capsys):
    words = 'Ship it | but "only" after Ann Example signs off'
    assert main(["order", "new", words, "--owner", "worker-a"]) == 0
    assert capsys.readouterr().out.strip() == "O1"
    assert main(["order", "new", "second order"]) == 0
    text = (ws / "ORDERS.md").read_text()
    assert "O2" in text and "unassigned" in text
    from supra.cli import read_orders
    _, rows = read_orders(ws / "ORDERS.md")
    first = next(c for c in rows.values() if c[0] == "O1")
    assert first[2] == '"' + words + '"'
    assert first[3] == "worker-a" and first[4] == "open"
    assert main(["order", "new", "   "]) == 2


def test_done_and_blocked_need_evidence(ws, capsys):
    main(["order", "new", "do the thing"])
    assert main(["order", "state", "O1", "done"]) == 2
    assert main(["order", "state", "O1", "blocked"]) == 2
    assert main(["order", "state", "O9", "open"]) == 2
    assert main(["order", "state", "O1", "done", "--evidence", "pytest: 5 passed, abc123"]) == 0
    assert "done: pytest: 5 passed, abc123" in (ws / "ORDERS.md").read_text()


def test_state_add_needs_result_and_trims_into_archive(ws, monkeypatch):
    assert main(["state", "add", "did something"]) == 2
    assert main(["state", "add", "did something RESULT: DONE -"]) == 2
    monkeypatch.setenv("SUPRA_STATE_MAX", "150")
    for i in range(160):
        assert main(["state", "add", f"step {i} RESULT: DONE - ok {i}"]) == 0
    state = (ws / "STATE.md").read_text().splitlines()
    archive = (ws / "STATE-ARCHIVE.md").read_text().splitlines()
    assert len(state) == 150
    assert state[0] == "# State"
    assert "step 159" in state[-1]
    assert len(archive) == 160 - (150 - 2)
    assert "step 0 " in archive[0]


def test_facts_add_is_append_only_and_dated(ws, monkeypatch):
    main(["facts", "add", "first fact"])
    first = (ws / "FACTS.md").read_text()
    monkeypatch.setenv("SUPRA_NOW", "2026-03-02 10:30")
    main(["facts", "add", "second fact"])
    second = (ws / "FACTS.md").read_text()
    assert second.startswith(first)
    assert "- 2026-03-01 09:00 first fact" in second
    assert second.endswith("- 2026-03-02 10:30 second fact\n")
    assert main(["facts", "add", "  "]) == 2


def test_audit_lists_stale_open_and_done_without_evidence(ws, capsys, monkeypatch):
    main(["order", "new", "old open order"])
    main(["order", "new", "fresh order"])
    main(["order", "new", "hand edited done"])
    main(["order", "new", "properly done"])
    main(["order", "state", "O4", "done", "--evidence", "ran it, saw it"])
    path = ws / "ORDERS.md"
    path.write_text(path.read_text().replace(
        "hand edited done\" | unassigned | open", "hand edited done\" | unassigned | done"))
    monkeypatch.setenv("SUPRA_NOW", "2026-03-01 12:00")
    capsys.readouterr()
    assert main(["audit", "--hours", "24"]) == 1
    out = capsys.readouterr().out
    assert "O3: DONE without evidence" in out
    assert "O1" not in out and "O4" not in out
    monkeypatch.setenv("SUPRA_NOW", "2026-03-03 12:00")
    assert main(["audit", "--hours", "24"]) == 1
    out = capsys.readouterr().out
    assert "O1: open for 51.0 h" in out and "O2: open for 51.0 h" in out
    assert "O4" not in out
