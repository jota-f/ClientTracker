import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body

from app.models.user import User, UserResponse
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user

router = APIRouter(tags=["Usuários"])
logger = logging.getLogger(__name__)

@router.post("/update", response_model=UserResponse)
async def update_user_profile(
    user_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Atualiza os dados do usuário autenticado.
    """
    try:
        update_data = {k: v for k, v in user_data.items() if v is not None}
        
        # Se a senha estiver presente, vamos hashear
        if "password" in update_data and update_data["password"]:
            hashed_password = AuthService.get_password_hash(update_data["password"])
            update_data["hashed_password"] = hashed_password
            del update_data["password"]
        
        # Converter 'name' para 'full_name' se presente
        if "name" in update_data:
            update_data["full_name"] = update_data.pop("name")
        
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
            detail=f"Erro ao atualizar usuário: {str(e)}"
        )

@router.patch("/notification-settings", status_code=status.HTTP_200_OK)
async def update_notification_settings(
    settings: Dict[str, bool] = Body(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Atualiza as configurações de notificação do usuário.
    """
    try:
        # Inicializa notification_preference se não existir
        if not hasattr(current_user, 'notification_preference') or not current_user.notification_preference:
            notification_preference = {}
        else:
            # Lidar com notification_preference sendo string ou objeto
            if isinstance(current_user.notification_preference, str):
                notification_preference = {"type": current_user.notification_preference}
            else:
                notification_preference = current_user.notification_preference.copy() if current_user.notification_preference else {}
        
        # Atualiza as configurações
        for key, value in settings.items():
            notification_preference[key] = value
        
        # Salva as configurações
        update_data = {"notification_preference": notification_preference}
        updated_user = await AuthService.update_user(current_user.id, update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
            
        return {"message": "Configurações de notificação atualizadas com sucesso"}
    except Exception as e:
        logger.error(f"Erro ao atualizar configurações de notificação: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar configurações de notificação: {str(e)}"
        ) 