import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from datetime import datetime, timezone
from bson import ObjectId
import traceback

from app.models.user import User, UserResponse, UserProfileUpdate
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user
from app.models.notification_settings import NotificationSettings
from app.core.database import Database
from app.core.config import settings
from pydantic import BaseModel

router = APIRouter(tags=["Usuários"])
logger = logging.getLogger(__name__)

class NotificationUpdate(BaseModel):
    settings: Dict[str, bool]
    notification_preference: str

@router.post("/update", response_model=UserResponse)
async def update_user_profile(
    user_update: UserProfileUpdate,
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Atualiza os dados de perfil do usuário autenticado de forma segura,
    bloqueando qualquer tentativa de mass assignment ou elevação de privilégio.
    """
    try:
        raw_data = user_update.model_dump(exclude_unset=True)
        
        # Permitir estritamente campos autorizados para edição de perfil
        allowed_fields = {
            "username", "email", "full_name", "notification_preference", "notification_settings"
        }
        update_data = {}
        
        # Converter 'name' para 'full_name' se fornecido
        if "name" in raw_data and raw_data["name"] is not None:
            update_data["full_name"] = raw_data["name"]
        if "full_name" in raw_data and raw_data["full_name"] is not None:
            update_data["full_name"] = raw_data["full_name"]
            
        for field in ["username", "email", "notification_preference", "notification_settings"]:
            if field in raw_data and raw_data[field] is not None:
                update_data[field] = raw_data[field]
                
        # Tratar senha com hash seguro se fornecida
        if raw_data.get("password"):
            update_data["hashed_password"] = AuthService.get_password_hash(raw_data["password"])
            
        # Assegurar explicitamente que nenhum campo de privilégio é injetado
        for forbidden in ["role", "is_admin", "is_active", "email_verified", "id", "_id"]:
            update_data.pop(forbidden, None)
            
        if not update_data:
            # Nada a atualizar, retorna o usuário atual
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

@router.patch("/notifications", status_code=status.HTTP_200_OK)
@router.patch("/notification-settings", status_code=status.HTTP_200_OK, include_in_schema=False, deprecated=True)  # Rota legada, mantida para compatibilidade
async def update_notification_settings(
    update_data: NotificationUpdate,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Atualiza as configurações de notificação do usuário.
    A rota /notification-settings está deprecada, use /notifications no lugar.
    """
    try:
        logger.info(f"[DEBUG - PATCH NOTIFICATION-SETTINGS] Endpoint chamado!")
        logger.info(f"Atualizando configurações de notificação para usuário {current_user.id}")
        logger.info(f"Dados recebidos: {update_data}")
        logger.info(f"Tipo de dados em settings: {type(update_data.settings)}")
        logger.info(f"Valores booleanos recebidos: rfm_reminders={type(update_data.settings.get('rfm_reminders'))}:{update_data.settings.get('rfm_reminders')}, task_reminders={type(update_data.settings.get('task_reminders'))}:{update_data.settings.get('task_reminders')}, followup_reminders={type(update_data.settings.get('followup_reminders'))}:{update_data.settings.get('followup_reminders')}")
        
        # Validar notification_preference
        if update_data.notification_preference not in ["email", "in_app", "both", "none"]:
            logger.warning(f"[DEBUG] Preferência de notificação inválida: {update_data.notification_preference}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Preferência de notificação inválida"
            )
        
        # Criar novo objeto NotificationSettings com as configurações atualizadas e converter explicitamente para bool
        notification_settings = NotificationSettings(
            rfm_reminders=bool(update_data.settings.get("rfm_reminders", True)),
            task_reminders=bool(update_data.settings.get("task_reminders", True)),
            followup_reminders=bool(update_data.settings.get("followup_reminders", True))
        )
        
        logger.info(f"NotificationSettings criado: {notification_settings.model_dump()}")
        logger.info(f"Tipos após conversão: rfm_reminders={type(notification_settings.rfm_reminders)}, task_reminders={type(notification_settings.task_reminders)}, followup_reminders={type(notification_settings.followup_reminders)}")
        
        # Atualizar diretamente no banco de dados
        update_data_db = {
            "notification_settings": notification_settings.model_dump(),
            "notification_preference": update_data.notification_preference,
            "updated_at": datetime.now(timezone.utc)
        }
        
        logger.info(f"Dados para atualização: {update_data_db}")
        
        # Usar find_one_and_update para obter o documento atualizado
        result = await Database.database["users"].find_one_and_update(
            {"_id": ObjectId(current_user.id)},
            {"$set": update_data_db},
            return_document=True
        )
        
        if not result:
            logger.error(f"Usuário {current_user.id} não encontrado no banco de dados")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
            
        # Converter o resultado para um objeto User e validar
        updated_user = User.model_validate(result)
        
        # Retornar os dados atualizados
        notification_settings_dict = updated_user.notification_settings.model_dump()
        
        # Garantir que os valores são booleanos explícitos
        sanitized_settings = {
            "rfm_reminders": bool(notification_settings_dict.get("rfm_reminders", False)),
            "task_reminders": bool(notification_settings_dict.get("task_reminders", False)),
            "followup_reminders": bool(notification_settings_dict.get("followup_reminders", False))
        }
        
        logger.info(f"Valores retornados depois de sanitizar: {sanitized_settings}")
        
        # Retornar apenas os dados necessários, sem informações sensíveis do usuário
        return {
            "message": "Configurações de notificação atualizadas com sucesso",
            "notification_settings": sanitized_settings,
            "notification_preference": updated_user.notification_preference
        }
        
    except Exception as e:
        logger.error(f"Erro ao atualizar configurações de notificação: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar configurações de notificação: {str(e)}"
        ) 