from pathlib import Path

from scraper.storage.dedupe import DedupeState


def test_dedupe_state_roundtrip(tmp_path: Path) -> None:
    state_file = tmp_path / "dedupe.json"
    state = DedupeState.load(str(state_file))

    assert state.is_new_url("https://example.com") is True
    assert state.is_new_url("https://example.com") is False

    state.save()

    state2 = DedupeState.load(str(state_file))
    assert state2.is_new_url("https://example.com") is False
    assert state2.is_new_url("https://example.com/2") is True
