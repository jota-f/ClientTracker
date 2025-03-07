import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.models.user import User, UserCreate, UserResponse, UserUpdate, PasswordUpdate
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user, get_optional_user

router = APIRouter(tags=["Autenticação"])
logger = logging.getLogger(__name__)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_create: UserCreate) -> UserResponse:
    """
    Registra um novo usuário no sistema.
    """
    try:
        user_response = await AuthService.create_user(user_create)
        if not user_response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao criar usuário"
            )
        return user_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erro ao registrar usuário: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno no servidor"
        )

@router.post("/login", response_model=Dict[str, Any])
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, Any]:
    """
    Autentica um usuário e retorna um token de acesso.
    """
    user = await AuthService.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Gera o token JWT
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username,
        "role": user.role
    }
    access_token = AuthService.create_access_token(token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    }

@router.get("/me", response_model=UserResponse)
async def get_user_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Retorna os dados do usuário autenticado.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        notification_preference=current_user.notification_preference,
        calendar_integration=current_user.calendar_integration,
        email_verified=current_user.email_verified,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login=current_user.last_login
    )

@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Atualiza os dados do usuário autenticado.
    """
    try:
        update_data = {k: v for k, v in user_update.dict().items() if v is not None}
        updated_user = await AuthService.update_user(current_user.id, update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
            
        return UserResponse(
            id=updated_user.id,
            username=updated_user.username,
            email=updated_user.email,
            full_name=updated_user.full_name,
            role=updated_user.role,
            notification_preference=updated_user.notification_preference,
            calendar_integration=updated_user.calendar_integration,
            email_verified=updated_user.email_verified,
            is_active=updated_user.is_active,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
            last_login=updated_user.last_login
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar usuário: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar usuário"
        )

@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_update: PasswordUpdate,
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Altera a senha do usuário autenticado.
    """
    if password_update.new_password != password_update.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="As senhas não coincidem"
        )
        
    if password_update.current_password == password_update.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ser diferente da senha atual"
        )
        
    success = await AuthService.change_password(
        current_user.id,
        password_update.current_password,
        password_update.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta"
        )
        
    return {"message": "Senha alterada com sucesso"}

# Rota para requisitar recuperação de senha (para implementação futura)
@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(email: str = Body(..., embed=True)) -> Dict[str, str]:
    """
    Inicia o processo de recuperação de senha para um usuário.
    """
    # Verificar se o email existe
    user = await AuthService.get_user_by_email(email)
    if not user:
        # Por segurança, não informamos se o email existe ou não
        return {"message": "Se o email estiver cadastrado, você receberá instruções para redefinir sua senha"}
    
    # Aqui você implementaria o envio de email com um token
    # para redefinir a senha (quando implementar a Sprint 4)
    
    return {"message": "Se o email estiver cadastrado, você receberá instruções para redefinir sua senha"}

@router.get("/check", response_model=Dict[str, Any])
async def check_auth(current_user: Optional[User] = Depends(get_optional_user)) -> Dict[str, Any]:
    """
    Verifica o status de autenticação do usuário atual.
    """
    if current_user:
        return {
            "authenticated": True,
            "user": {
                "id": str(current_user.id),
                "email": current_user.email,
                "username": current_user.username,
                "role": current_user.role
            }
        }
    return {
        "authenticated": False,
        "message": "Usuário não autenticado"
    } 