import json

from roster_sync.automation_status import record_automation_run


def test_record_automation_run_writes_status_and_history(tmp_path):
    status_path = tmp_path / "automation-status.json"
    history_path = tmp_path / "automation-history.jsonl"
    payload = {"status": "ok", "synced_event_count_by_period": {"2026-04": 16}}

    record_automation_run(
        status_path=status_path,
        history_path=history_path,
        payload=payload,
    )

    assert json.loads(status_path.read_text(encoding="utf-8")) == payload
    history_lines = history_path.read_text(encoding="utf-8").splitlines()
    assert history_lines == [json.dumps(payload)]


def test_record_automation_run_appends_history(tmp_path):
    status_path = tmp_path / "automation-status.json"
    history_path = tmp_path / "automation-history.jsonl"

    record_automation_run(
        status_path=status_path,
        history_path=history_path,
        payload={"status": "failed"},
    )
    record_automation_run(
        status_path=status_path,
        history_path=history_path,
        payload={"status": "ok"},
    )

    history_lines = history_path.read_text(encoding="utf-8").splitlines()
    assert history_lines == [
        json.dumps({"status": "failed"}),
        json.dumps({"status": "ok"}),
    ]
    assert json.loads(status_path.read_text(encoding="utf-8")) == {"status": "ok"}
