from uuid import uuid4

from reminder_common.security import Role, decode_access_token

from app.models.auth import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.schemas.users import MemberCreate, PasswordReset
from app.services.auth import create_access_token, hash_password, verify_password


def test_argon2_password_round_trip() -> None:
    password_hash = hash_password("a strong password")
    assert password_hash.startswith("$argon2")
    assert verify_password("a strong password", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_access_token_contains_identity_and_role() -> None:
    user = User(
        id=uuid4(),
        email="admin@example.com",
        name="Admin",
        password_hash="unused",
        role=Role.ADMIN,
        is_active=True,
        timezone="UTC",
    )
    principal = decode_access_token(create_access_token(user))
    assert principal.user_id == user.id
    assert principal.role is Role.ADMIN


def test_six_character_password_is_accepted_everywhere() -> None:
    password = "abc123"
    assert LoginRequest(email="member@example.com", password=password).password == password
    assert (
        ChangePasswordRequest(current_password="existing", new_password=password).new_password
        == password
    )
    assert (
        MemberCreate(
            name="Member",
            email="member@example.com",
            temporary_password=password,
        ).temporary_password
        == password
    )
    assert PasswordReset(temporary_password=password).temporary_password == password
