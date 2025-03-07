import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.models.user import User, CalendarIntegration
from app.core.database import Database

# Configurar logging
logger = logging.getLogger(__name__)

class UserService:
    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[User]:
        """Obtém um usuário pelo ID."""
        try:
            user_dict = await Database.database["users"].find_one({"_id": ObjectId(user_id)})
            if not user_dict:
                return None
            return User.parse_obj(user_dict)
        except Exception as e:
            logger.error(f"Erro ao buscar usuário por ID: {str(e)}")
            return None
    
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[User]:
        """Obtém um usuário pelo email."""
        try:
            user_dict = await Database.database["users"].find_one({"email": email})
            if not user_dict:
                return None
            return User.parse_obj(user_dict)
        except Exception as e:
            logger.error(f"Erro ao buscar usuário por email: {str(e)}")
            return None
    
    @staticmethod
    async def update_user(user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """Atualiza os dados de um usuário."""
        try:
            # Remove campos vazios e None
            clean_data = {k: v for k, v in update_data.items() if v is not None}
            
            if not clean_data:
                return await UserService.get_user_by_id(user_id)
                
            # Adiciona a data de atualização
            clean_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await Database.database["users"].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": clean_data}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                return await UserService.get_user_by_id(user_id)
            return None
        except Exception as e:
            logger.error(f"Erro ao atualizar usuário: {str(e)}")
            return None
    
    @staticmethod
    async def update_calendar_integration(user_id: str, calendar_integration: CalendarIntegration) -> bool:
        """Atualiza as configurações de integração de calendário de um usuário."""
        try:
            now = datetime.now(timezone.utc)
            
            # Converter o objeto para dicionário
            integration_dict = calendar_integration.dict()
            
            result = await Database.database["users"].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "calendar_integration": integration_dict,
                    "updated_at": now
                }}
            )
            
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            logger.error(f"Erro ao atualizar integração de calendário: {str(e)}")
            return False
    
    @staticmethod
    async def get_users_with_enabled_calendar(calendar_type: Optional[str] = None) -> List[User]:
        """Obtém uma lista de usuários com integração de calendário ativada."""
        try:
            query = {"calendar_integration.enabled": True}
            
            if calendar_type:
                query["calendar_integration.type"] = calendar_type
            
            users_dicts = await Database.database["users"].find(query).to_list(length=100)
            
            return [User.parse_obj(user_dict) for user_dict in users_dicts]
        except Exception as e:
            logger.error(f"Erro ao buscar usuários com calendário ativado: {str(e)}")
            return [] 