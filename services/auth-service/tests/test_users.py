from uuid import uuid4

import pytest
from fastapi import HTTPException
from reminder_common.security import Principal, Role, require_admin


class FakeRequest:
    def __init__(self, token: str = "") -> None:
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}


def test_member_role_is_not_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    from reminder_common import security

    monkeypatch.setattr(
        security,
        "require_principal",
        lambda request: Principal(user_id=uuid4(), role=Role.MEMBER),
    )
    with pytest.raises(HTTPException) as error:
        require_admin(FakeRequest())  # type: ignore[arg-type]
    assert error.value.status_code == 403
