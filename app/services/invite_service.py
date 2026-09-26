import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from bson import ObjectId
import secrets
import traceback

from app.core.database import Database
from app.models.user import InviteCode

logger = logging.getLogger(__name__)

class InviteService:
    @staticmethod
    async def create_invite_code(created_by: str, email: Optional[str] = None, expires_in_days: int = 7) -> InviteCode:
        """Cria um novo código de convite."""
        try:
            logger.info(f"Iniciando criação de convite para email: {email}, criado por: {created_by}")
            code = secrets.token_urlsafe(16)
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            
            invite_dict = {
                "code": code,
                "created_by": created_by,
                "email": email,
                "used": False,
                "created_at": datetime.now(timezone.utc),
                "expires_at": expires_at,
                "used_at": None,
                "used_by": None
            }
            
            logger.info(f"Criando novo convite: {invite_dict}")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao criar convite: Conexão com banco de dados não inicializada")
                raise ValueError("Conexão com banco de dados não inicializada")
                
            result = await Database.database["invite_codes"].insert_one(invite_dict)
            logger.info(f"Convite criado com sucesso. ID: {result.inserted_id}")
            
            return InviteCode(**invite_dict)
        except Exception as e:
            logger.error(f"Erro ao criar código de convite: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    @staticmethod
    async def validate_invite_code(code: str, email: Optional[str] = None) -> bool:
        """Valida um código de convite."""
        try:
            logger.info(f"Validando código de convite: {code}, email: {email}")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao validar convite: Conexão com banco de dados não inicializada")
                return False
                
            invite = await Database.database["invite_codes"].find_one({
                "code": code,
                "used": False,
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            })
            
            if not invite:
                logger.info(f"Código de convite inválido ou expirado: {code}")
                return False
                
            # Se o convite foi criado para um email específico, verifica se corresponde
            if invite.get("email") and email and invite["email"] != email:
                logger.info(f"Email do convite não corresponde. Esperado: {invite.get('email')}, Recebido: {email}")
                return False
                
            logger.info(f"Código de convite válido: {code}")
            return True
        except Exception as e:
            logger.error(f"Erro ao validar código de convite: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    @staticmethod
    async def use_invite_code(code: str, used_by: str) -> bool:
        """Marca um código de convite como usado."""
        try:
            logger.info(f"Marcando código de convite {code} como usado por {used_by}")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao usar convite: Conexão com banco de dados não inicializada")
                return False
                
            result = await Database.database["invite_codes"].update_one(
                {
                    "code": code,
                    "used": False,
                    "expires_at": {"$gt": datetime.now(timezone.utc)}
                },
                {
                    "$set": {
                        "used": True,
                        "used_at": datetime.now(timezone.utc),
                        "used_by": used_by
                    }
                }
            )
            
            success = result.modified_count > 0
            logger.info(f"Código de convite {code} marcado como usado: {success}")
            return success
        except Exception as e:
            logger.error(f"Erro ao marcar código de convite como usado: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    @staticmethod
    async def list_invite_codes(created_by: Optional[str] = None) -> List[InviteCode]:
        """Lista todos os códigos de convite."""
        try:
            logger.info(f"Listando códigos de convite para o criador: {created_by}")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao listar convites: Conexão com banco de dados não inicializada")
                raise ValueError("Conexão com banco de dados não inicializada")
                
            query = {"created_by": created_by} if created_by else {}
            logger.info(f"Query para listar convites: {query}")
            
            cursor = Database.database["invite_codes"].find(query)
            invite_codes = []
            
            async for doc in cursor:
                invite_codes.append(InviteCode(**doc))
                
            logger.info(f"Encontrados {len(invite_codes)} convites")
            return invite_codes
        except Exception as e:
            logger.error(f"Erro ao listar códigos de convite: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise 