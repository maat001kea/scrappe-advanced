from __future__ import annotations

import random


def compute_backoff_seconds(
    attempt: int,
    initial: float,
    maximum: float,
    jitter: float = 0.25,
) -> float:
    """Exponential backoff with jitter.

    attempt is 1-based.
    """

    exp = initial * (2 ** (attempt - 1))
    exp = min(exp, maximum)

    # Jitter in range [exp*(1-jitter), exp*(1+jitter)].
    delta = exp * jitter
    return max(0.0, random.uniform(exp - delta, exp + delta))
