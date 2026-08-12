from unittest.mock import Mock, patch

from app.tasks.scan import scan_due_occurrences


def test_scan_task_calls_authoritative_service() -> None:
    response = Mock()
    response.json.return_value = {"created": 2, "state_changes": 1}
    response.raise_for_status.return_value = None
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response
    with patch("app.tasks.scan.httpx.Client", return_value=client):
        assert scan_due_occurrences.run() == {"created": 2, "state_changes": 1}
