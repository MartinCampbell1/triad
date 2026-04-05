from triad.core.modes.delegate import DelegateTask, DelegateConfig


def test_delegate_task_creation():
    task = DelegateTask(prompt="Review auth", provider="codex")
    assert task.prompt == "Review auth"
    assert task.provider == "codex"
    assert task.status == "pending"


def test_delegate_config():
    cfg = DelegateConfig(
        tasks=[
            DelegateTask(prompt="Review auth", provider="codex"),
            DelegateTask(prompt="Write tests", provider="claude"),
        ],
    )
    assert len(cfg.tasks) == 2
