from scraper.network.backoff import compute_backoff_seconds


def test_compute_backoff_bounds() -> None:
    v = compute_backoff_seconds(attempt=1, initial=1.0, maximum=10.0, jitter=0.25)
    assert 0.75 <= v <= 1.25

    v2 = compute_backoff_seconds(attempt=10, initial=1.0, maximum=10.0, jitter=0.25)
    assert 7.5 <= v2 <= 12.5
