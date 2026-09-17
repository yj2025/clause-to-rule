"""팀원 체크포인트 짝지은 비교 (`ckpt_paired.py`).

통계 함수는 손으로 셀 수 있는 값으로 본다. 팀원 파일 읽기는 폴더가 있을 때만 본다.
"""

import random

import pytest

import ckpt_paired as C

TEAM_READY = all(p.exists() for p in C.MODELS.values())


def test_mcnemar_exact_matches_binomial_tails():
    assert C.mcnemar_exact(0, 6) == pytest.approx(2 / 64)
    assert C.mcnemar_exact(0, 5) == pytest.approx(2 / 32)
    assert C.mcnemar_exact(1, 4) == pytest.approx(2 * 6 / 32)
    assert C.mcnemar_exact(3, 3) == 1.0
    assert C.mcnemar_exact(0, 0) == 1.0


def test_six_one_sided_discordant_items_are_needed_at_005():
    # Dev50 에서 체크포인트 사이 한두 문항 차이는 판정할 수 없다는 근거
    assert C.min_discordant_for(0.05) == 6


def test_sign_flip_is_one_when_nothing_moves():
    assert C.sign_flip_p([0.0] * 50) == 1.0


def test_sign_flip_is_small_when_every_item_moves_up():
    p = C.sign_flip_p([0.5] * 12, n_perm=5000, rng=random.Random(1))
    assert p < 0.005


def test_sign_flip_is_large_for_balanced_moves():
    p = C.sign_flip_p([0.5, -0.5] * 10, n_perm=5000, rng=random.Random(1))
    assert p > 0.5


def test_bootstrap_interval_collapses_for_constant_diffs():
    assert C.boot_ci([0.2] * 30, n_boot=500, rng=random.Random(1)) == (
        pytest.approx(0.2), pytest.approx(0.2))


def test_compare_binary_counts_only_discordant_items():
    a = {1: {"semantic_exact": True}, 2: {"semantic_exact": False},
         3: {"semantic_exact": False}, 4: {"semantic_exact": True}}
    b = {1: {"semantic_exact": True}, 2: {"semantic_exact": True},
         3: {"semantic_exact": True}, 4: {"semantic_exact": False}}
    r = C.compare(a, b, "semantic_exact", [1, 2, 3, 4])
    assert (r["only_a"], r["only_b"]) == (1, 2)
    assert (r["only_a_items"], r["only_b_items"]) == ([4], [2, 3])
    assert r["diff"] == pytest.approx(0.25)


@pytest.mark.skipif(not TEAM_READY, reason="팀원 평가 파일이 없다")
def test_team_csv_means_reproduce_team_score_files():
    data, _ = C.load()            # 다르면 SystemExit
    assert {len(v) for v in data.values()} == {50}
