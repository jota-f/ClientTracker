import logging
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
import traceback
import re

from app.core.database import Database
from app.models.invite_request import InviteRequest, InviteRequestCreate

logger = logging.getLogger(__name__)

class InviteRequestService:
    @staticmethod
    async def create_invite_request(request_data: InviteRequestCreate) -> InviteRequest:
        """Cria uma nova solicitação de convite com validações avançadas."""
        try:
            logger.info(f"Criando solicitação de convite para: {request_data.email}")
            
            # Validar email
            if not InviteRequestService._is_valid_email(request_data.email):
                raise ValueError(f"Email inválido: {request_data.email}")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao criar solicitação: Conexão com banco de dados não inicializada")
                raise ValueError("Conexão com banco de dados não inicializada")
            
            # Verificar se já existe uma solicitação pendente para este email
            existing_request = await Database.database["invite_requests"].find_one({
                "email": request_data.email.lower(),
                "status": "pending"
            })
            
            if existing_request:
                logger.warning(f"Solicitação duplicada detectada para email: {request_data.email}")
                # Retornar a solicitação existente em vez de criar uma nova
                existing_request["_id"] = str(existing_request["_id"])
                return InviteRequest(**existing_request)
            
            # Verificar se já existe uma solicitação aprovada recente (últimos 30 dias)
            from datetime import timedelta
            thirty_days_ago = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
            
            recent_approved = await Database.database["invite_requests"].find_one({
                "email": request_data.email.lower(),
                "status": "approved",
                "processed_at": {"$gte": thirty_days_ago}
            })
            
            if recent_approved:
                logger.warning(f"Solicitação já aprovada recentemente para email: {request_data.email}")
                raise ValueError("Uma solicitação para este email já foi aprovada recentemente")
                
            invite_dict = {
                "name": request_data.name.strip(),
                "email": request_data.email.lower().strip(),
                "company": request_data.company.strip(),
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "processed_at": None,
                "processed_by": None,
                "notes": None
            }
            
            result = await Database.database["invite_requests"].insert_one(invite_dict)
            logger.info(f"Solicitação de convite criada com sucesso. ID: {result.inserted_id}")
            
            invite_dict["_id"] = str(result.inserted_id)
            return InviteRequest(**invite_dict)
            
        except ValueError as e:
            logger.warning(f"Erro de validação ao criar solicitação: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao criar solicitação de convite: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise ValueError(f"Erro interno ao processar solicitação: {str(e)}")

    @staticmethod
    async def get_invite_requests(status: Optional[str] = None) -> List[InviteRequest]:
        """Obtém a lista de solicitações de convite com filtro opcional por status."""
        try:
            logger.info(f"Listando solicitações de convite com status: {status}")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao listar solicitações: Conexão com banco de dados não inicializada")
                raise ValueError("Conexão com banco de dados não inicializada")
            
            query = {}
            if status:
                if status not in ["pending", "approved", "rejected"]:
                    raise ValueError(f"Status inválido: {status}")
                query["status"] = status
                
            cursor = Database.database["invite_requests"].find(query).sort("created_at", -1)
            requests = []
            
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                requests.append(InviteRequest(**doc))
            
            logger.info(f"Encontradas {len(requests)} solicitações de convite")
            return requests
            
        except ValueError as e:
            logger.warning(f"Erro de validação ao listar solicitações: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao listar solicitações de convite: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise ValueError(f"Erro interno ao listar solicitações: {str(e)}")

    @staticmethod
    async def update_invite_request_status(
        request_id: str, 
        status: str, 
        admin_id: str, 
        notes: Optional[str] = None
    ) -> bool:
        """Atualiza o status de uma solicitação de convite com validações."""
        try:
            logger.info(f"Atualizando status da solicitação {request_id} para {status} por admin {admin_id}")
            
            # Validar status
            if status not in ["approved", "rejected"]:
                raise ValueError(f"Status inválido: {status}")
            
            # Validar ObjectId
            try:
                ObjectId(request_id)
            except Exception:
                raise ValueError(f"ID de solicitação inválido: {request_id}")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao atualizar solicitação: Conexão com banco de dados não inicializada")
                return False
            
            # Verificar se a solicitação existe e está pendente
            existing_request = await Database.database["invite_requests"].find_one({
                "_id": ObjectId(request_id)
            })
            
            if not existing_request:
                logger.warning(f"Solicitação não encontrada: {request_id}")
                raise ValueError("Solicitação não encontrada")
            
            if existing_request["status"] != "pending":
                logger.warning(f"Tentativa de alterar solicitação já processada: {request_id} (status atual: {existing_request['status']})")
                raise ValueError(f"Esta solicitação já foi processada (status: {existing_request['status']})")
                
            update_data = {
                "status": status,
                "processed_at": datetime.now(timezone.utc),
                "processed_by": admin_id
            }
            
            if notes and notes.strip():
                update_data["notes"] = notes.strip()[:500]  # Limitar tamanho das notas
                
            result = await Database.database["invite_requests"].update_one(
                {"_id": ObjectId(request_id)},
                {"$set": update_data}
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Solicitação {request_id} atualizada com sucesso para {status}")
            else:
                logger.warning(f"Nenhuma alteração feita na solicitação {request_id}")
                
            return success
            
        except ValueError as e:
            logger.warning(f"Erro de validação ao atualizar solicitação: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao atualizar solicitação de convite: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    @staticmethod
    async def get_invite_request_by_id(request_id: str) -> Optional[InviteRequest]:
        """Obtém uma solicitação específica por ID."""
        try:
            logger.info(f"Buscando solicitação por ID: {request_id}")
            
            # Validar ObjectId
            try:
                ObjectId(request_id)
            except Exception:
                raise ValueError(f"ID de solicitação inválido: {request_id}")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao buscar solicitação: Conexão com banco de dados não inicializada")
                raise ValueError("Conexão com banco de dados não inicializada")
            
            doc = await Database.database["invite_requests"].find_one({
                "_id": ObjectId(request_id)
            })
            
            if not doc:
                logger.info(f"Solicitação não encontrada: {request_id}")
                return None
            
            doc["_id"] = str(doc["_id"])
            return InviteRequest(**doc)
            
        except ValueError as e:
            logger.warning(f"Erro de validação ao buscar solicitação: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar solicitação: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    @staticmethod
    async def get_statistics() -> dict:
        """Obtém estatísticas das solicitações de convite."""
        try:
            logger.info("Obtendo estatísticas das solicitações de convite")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao obter estatísticas: Conexão com banco de dados não inicializada")
                raise ValueError("Conexão com banco de dados não inicializada")
            
            pipeline = [
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            cursor = Database.database["invite_requests"].aggregate(pipeline)
            results = {}
            
            async for doc in cursor:
                results[doc["_id"]] = doc["count"]
            
            # Garantir que todos os status estejam presentes
            stats = {
                "pending": results.get("pending", 0),
                "approved": results.get("approved", 0),
                "rejected": results.get("rejected", 0),
                "total": sum(results.values())
            }
            
            logger.info(f"Estatísticas obtidas: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"pending": 0, "approved": 0, "rejected": 0, "total": 0}

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Valida formato de email."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email.strip()) is not None

    @staticmethod
    async def cleanup_old_rejected_requests(days: int = 90) -> int:
        """Remove solicitações rejeitadas antigas para limpeza do banco."""
        try:
            logger.info(f"Limpando solicitações rejeitadas com mais de {days} dias")
            
            # Verificar conexão com o banco de dados
            if Database.database is None:
                logger.error("Erro ao limpar solicitações: Conexão com banco de dados não inicializada")
                return 0
            
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
            
            result = await Database.database["invite_requests"].delete_many({
                "status": "rejected",
                "processed_at": {"$lt": cutoff_date}
            })
            
            deleted_count = result.deleted_count
            logger.info(f"Removidas {deleted_count} solicitações rejeitadas antigas")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Erro ao limpar solicitações antigas: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0 