from triad.core.context.blackboard import Blackboard


def test_blackboard_empty():
    bb = Blackboard()
    assert bb.task == ""
    assert bb.current_plan == []
    assert bb.open_issues == []


def test_blackboard_set_task():
    bb = Blackboard()
    bb.task = "Add auth to API"
    assert bb.task == "Add auth to API"


def test_blackboard_update_plan():
    bb = Blackboard()
    bb.current_plan = ["step 1", "step 2"]
    assert len(bb.current_plan) == 2


def test_blackboard_add_artifact():
    bb = Blackboard()
    bb.add_artifact("writer_diff", "ta_abc123")
    assert bb.latest_artifacts["writer_diff"] == "ta_abc123"


def test_blackboard_add_decision():
    bb = Blackboard()
    bb.add_decision("Use JWT for auth")
    assert "Use JWT for auth" in bb.decisions_made


def test_blackboard_render_for_writer():
    bb = Blackboard()
    bb.task = "Fix the bug"
    bb.current_plan = ["find bug", "fix it"]
    bb.open_issues = ["unclear requirements"]
    text = bb.render_for_role("writer")
    assert "Fix the bug" in text
    assert "find bug" in text
    assert "unclear requirements" in text


def test_blackboard_render_for_critic():
    bb = Blackboard()
    bb.task = "Fix the bug"
    bb.open_issues = ["something"]
    text = bb.render_for_role("critic")
    assert "Fix the bug" in text
    # critic should NOT see open issues (that's writer's concern)


def test_blackboard_to_dict():
    bb = Blackboard()
    bb.task = "test"
    bb.add_decision("decided X")
    d = bb.to_dict()
    assert d["task"] == "test"
    assert "decided X" in d["decisions_made"]


def test_blackboard_from_dict():
    data = {"task": "test", "current_plan": ["a"], "open_issues": [], "latest_artifacts": {}, "decisions_made": []}
    bb = Blackboard.from_dict(data)
    assert bb.task == "test"
    assert bb.current_plan == ["a"]


def test_blackboard_constraints_roundtrip():
    bb = Blackboard()
    bb.accepted_constraints = ["JWT only", "no breaking changes"]
    d = bb.to_dict()
    assert "accepted_constraints" in d
    bb2 = Blackboard.from_dict(d)
    assert bb2.accepted_constraints == ["JWT only", "no breaking changes"]
