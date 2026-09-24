"""지문 해시는 **생성물을 바꾸는 모든 것**을 세야 한다.

2026-09-24 — v46 이 재시도 지문에 조건부 블록을 붙였는데 지문 해시가 v41 과
완전히 같았다. 처방 전 라운드와 처방 후 라운드가 구별이 안 됐고, 판정선을 재는
`floors.py` 가 「지문 1종이니 같은 구성」으로 읽고 섞을 뻔했다.
"""


def test_the_fingerprint_covers_every_file_that_changes_the_output():
    import run_local_v2 as R
    fp = R.prompt_fingerprint()
    for key in ("system", "fewshots", "catalog", "schema", "vocab",
                "validator", "retry"):
        assert key in fp, f"{key} 가 지문에 없다"


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
