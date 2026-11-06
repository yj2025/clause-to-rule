"""다음 pilot Dev 크기 (`experiments/devsize.py`). 검정력은 모든 경우를 직접 센 값과 맞춘다."""

import math

import pytest

import ckpt_paired as C
import devsize as D


def _brute(n, delta, p_disc):
    q = (p_disc + delta) / (2 * p_disc)
    tot = 0.0
    for d in range(n + 1):
        pd = math.comb(n, d) * p_disc ** d * (1 - p_disc) ** (n - d)
        for b in range(d + 1):
            if C.mcnemar_exact(d - b, b) < D.ALPHA:
                tot += pd * math.comb(d, b) * q ** b * (1 - q) ** (d - b)
    return tot


@pytest.mark.parametrize("n,delta,p_disc", [(30, 0.1, 0.1), (50, 0.05, 0.1), (80, 0.1, 0.4)])
def test_power_matches_brute_force(n, delta, p_disc):
    assert D.mcnemar_power(n, delta, p_disc) == pytest.approx(_brute(n, delta, p_disc), abs=1e-9)


def test_power_needs_delta_within_discordance():
    with pytest.raises(ValueError):
        D.mcnemar_power(50, 0.1, 0.05)


def test_sample_size_is_the_first_crossing():
    n = D.mcnemar_n(0.1, 0.1)
    assert D.mcnemar_power(n, 0.1, 0.1) >= D.POWER
    assert all(D.mcnemar_power(m, 0.1, 0.1) < D.POWER for m in range(1, n))


def test_more_discordance_needs_more_items():
    assert D.mcnemar_n(0.1, 0.1) < D.mcnemar_n(0.1, 0.2) < D.mcnemar_n(0.1, 0.4)


def test_normal_sample_size_formula():
    # (1.95996 + 0.84162)² · (0.2 / 0.05)² = 125.6 → 126
    assert D.normal_n(0.2, 0.05) == 126
