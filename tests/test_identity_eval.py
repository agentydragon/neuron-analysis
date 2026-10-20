from pathlib import Path

from evals.identity.stubs import build
from cell_tracking.identity import IdentityMarks, evaluate

ROOT = Path(__file__).resolve().parent.parent


def test_oracle_stub_scores_perfectly_and_empty_stub_fails():
    marks = IdentityMarks.model_validate_json((ROOT / "data/eval/identity_marks.json").read_text())
    oracle = evaluate(build(marks, mode="oracle"), marks)
    assert oracle["valid"] and oracle["failures"] == []
    assert oracle["marks_covered"] == {"passed": 36, "total": 36}
    empty = evaluate(build(marks, mode="empty"), marks)
    assert empty["valid"] and empty["marks_covered"]["passed"] == 0
