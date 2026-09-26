import pytest
from app.models.invite_request import InviteRequest, InviteRequestCreate
from app.models.user import InviteCode, UserCreate
from app.services.invite_request_service import InviteRequestService
from app.services.invite_service import InviteService
from datetime import datetime, timezone, timedelta

def test_invite_request_create_validation():
    valid = InviteRequestCreate(
        name="Teste Usuário",
        email="teste@empresa.com",
        company="Empresa ABC"
    )
    assert valid.name == "Teste Usuário"
    assert valid.email == "teste@empresa.com"
    assert valid.company == "Empresa ABC"

def test_invite_request_email_validation():
    assert InviteRequestService._is_valid_email("usuario@dominio.com") is True
    assert InviteRequestService._is_valid_email("invalido") is False
    assert InviteRequestService._is_valid_email("@dominio.com") is False
    assert InviteRequestService._is_valid_email("usuario@") is False

def test_invite_code_model():
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    code = InviteCode(
        code="test-code-12345",
        created_by="admin-user-id",
        email="convidado@empresa.com",
        expires_at=expires
    )
    assert code.code == "test-code-12345"
    assert code.used is False
    assert code.used_at is None

def test_user_create_with_invite_code():
    user = UserCreate(
        username="novo_usuario",
        email="novo@empresa.com",
        password="securepassword123",
        full_name="Novo Usuário",
        invite_code="test-code-12345"
    )
    assert user.invite_code == "test-code-12345"
    assert user.username == "novo_usuario"
