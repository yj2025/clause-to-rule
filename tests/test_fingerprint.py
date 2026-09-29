"""지문 해시는 **생성물을 바꾸는 모든 것**을 세야 한다.

2026-09-24 — v46 이 재시도 지문에 조건부 블록을 붙였는데 지문 해시가 v41 과
완전히 같았다. 처방 전 라운드와 처방 후 라운드가 구별이 안 됐고, 판정선을 재는
`floors.py` 가 「지문 1종이니 같은 구성」으로 읽고 섞을 뻔했다.
"""


def test_the_fingerprint_covers_every_file_that_changes_the_output():
    import run_local_v2 as R
    fp = R.prompt_fingerprint()
    for key in ("system", "fewshots", "catalog", "schema", "vocab",
                "validator", "retry", "triggers", "runner"):
        assert key in fp, f"{key} 가 지문에 없다"


def _touch(name):
    """그 파일에 한 줄 더하고 지문이 바뀌는지 본다."""
    import pathlib

    import run_local_v2 as R
    p = pathlib.Path(R.__file__).parent / name
    before = R.prompt_fingerprint()
    orig = p.read_text("utf-8")
    try:
        p.write_text(orig + "\n# 지문 해시 시험용 한 줄\n", "utf-8")
        after = R.prompt_fingerprint()
    finally:
        p.write_text(orig, "utf-8")
    return before, after


def test_changing_a_block_trigger_changes_the_fingerprint():
    """**이 시험이 v58 을 잡았어야 했다.**

    조건부 블록을 어느 조문에 붙일지 정하는 방아쇠는 `catalog.py` 에 있다.
    2026-09-24 에 `prompt.py` 만 넣고 이 파일을 빠뜨렸다 — 그래서 v36↔v37 과
    v38↔v39 가 지문으로 구별되지 않았다.

    **앞 시험은 키 목록만 열거해 이 구멍을 못 봤다.** 그래서 파일을 실제로
    건드려 본다.
    """
    before, after = _touch("catalog.py")
    assert before != after, "catalog.py 를 고쳐도 지문 해시가 안 바뀐다"


def test_changing_the_retry_prompt_changes_the_fingerprint():
    """**이 시험이 v46 을 잡았어야 했다.**"""
    import pathlib

    import run_local_v2 as R
    p = pathlib.Path(R.__file__).parent / "prompt.py"
    before = R.prompt_fingerprint()["retry"]
    orig = p.read_text("utf-8")
    try:
        p.write_text(orig + "\n# 지문 해시 시험용 한 줄\n", "utf-8")
        after = R.prompt_fingerprint()["retry"]
    finally:
        p.write_text(orig, "utf-8")
    assert before != after, "prompt.py 를 고쳐도 지문 해시가 안 바뀐다"


def test_changing_the_retry_loop_changes_the_fingerprint():
    """**이 시험이 없으면 재시도 루프만 바꾼 라운드가 앞 라운드와 구별이 안 된다.**

    재시도를 할지 말지는 `run_local_v2.run_clause` 가 정한다. 2026-09-29 에 그 루프만
    바꾸는 처방을 준비하다 지문이 이 파일을 안 센다는 것을 봤다.
    """
    before, after = _touch("run_local_v2.py")
    assert before != after, "run_local_v2.py 를 고쳐도 지문 해시가 안 바뀐다"
