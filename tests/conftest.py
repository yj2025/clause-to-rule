import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def clauses():
    return json.loads((ROOT / "data/clauses.json").read_text("utf-8"))


@pytest.fixture(scope="session")
def product():
    return json.loads((ROOT / "data/gold/_product.json").read_text("utf-8"))


@pytest.fixture(scope="session")
def profiles():
    import gold
    return gold.profiles()


WINDOW = {"window": {"month_range": {
    "from": {"anchor": "contract.start_date", "offset_months": 0, "day": "first"},
    "to": {"anchor": "contract.maturity_date", "offset_months": -2, "day": "last"}}}}


def ctx(salary=0, card=0, age=17, term="MATURITY", provide_salary=True):
    ev = {}
    provided = ["contract.start_date", "contract.maturity_date",
                "contract.reference_date", "customer.age", "account.balance"]
    if salary:
        ev["SALARY_TRANSFER"] = [{"date": f"2026-{m:02d}-25"} for m in range(1, 1 + salary)]
    if provide_salary:
        provided.append("events.SALARY_TRANSFER")
    if card:
        ev["CARD_USAGE"] = [{"date": "2026-08-15"}]
        provided.append("events.CARD_USAGE")
    return {"customer": {"age": age}, "account": {"balance": 0, "reserved_amount": 0},
            "contract": {"start_date": "2026-01-01", "maturity_date": "2026-12-01",
                         "reference_date": "2026-09-11", "termination_type": term,
                         "base_rate": 0.1, "channel": "MOBILE"},
            "events": ev, "_provided": provided}


@pytest.fixture
def make_ctx():
    return ctx
