from datetime import datetime, timezone
from app.models.client import Client, Interaction
from app.core.database import Database
from app.services.rfm import calculate_rfm_score
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Optional
import logging
import re

logger = logging.getLogger(__name__)

class ClientService:
    @staticmethod
    async def get_all_clients(user_id: str = None) -> List[Client]:
        try:
            # Criar filtro baseado no user_id, se fornecido
            query = {}
            if user_id:
                query["user_id"] = user_id
                logger.info(f"Filtrando clientes por user_id: {user_id}")
            
            clients = await Database.database["clients"].find(query).to_list(100)
            result = []
            
            for client in clients:
                # Garantir que os campos RFM estão corretos
                if "rfm_scores" in client and client["rfm_scores"]:
                    if "engagement" not in client["rfm_scores"] or client["rfm_scores"]["engagement"] is None:
                        client["rfm_scores"]["engagement"] = 0
                    
                    # Recalcular total se necessário
                    if "total" not in client["rfm_scores"] or client["rfm_scores"]["total"] is None:
                        if "recency" in client["rfm_scores"] and "potential" in client["rfm_scores"]:
                            client["rfm_scores"]["total"] = (
                                client["rfm_scores"]["recency"] + 
                                client["rfm_scores"]["potential"] + 
                                client["rfm_scores"]["engagement"]
                            )
                
                # Adicionar à lista de resultados
                try:
                    result.append(Client.parse_obj({"_id": str(client["_id"]), **client}))
                except Exception as e:
                    logger.error(f"Erro ao converter cliente {client.get('_id')}: {str(e)}")
                    
            logger.info(f"Recuperados {len(result)} clientes")
            return result
        except Exception as e:
            logger.error(f"Erro ao buscar clientes: {str(e)}")
            return []

    @staticmethod
    async def get_client_by_id(client_id: str) -> Client:
        try:
            client = await Database.database["clients"].find_one({"_id": ObjectId(client_id)})
            if client:
                # Garantir que os campos RFM estão corretos
                if "rfm_scores" in client and client["rfm_scores"]:
                    if "engagement" not in client["rfm_scores"] or client["rfm_scores"]["engagement"] is None:
                        client["rfm_scores"]["engagement"] = 0
                    
                    # Recalcular total se necessário
                    if "total" not in client["rfm_scores"] or client["rfm_scores"]["total"] is None:
                        if "recency" in client["rfm_scores"] and "potential" in client["rfm_scores"]:
                            client["rfm_scores"]["total"] = (
                                client["rfm_scores"]["recency"] + 
                                client["rfm_scores"]["potential"] + 
                                client["rfm_scores"]["engagement"]
                            )
                
                return Client.parse_obj({"_id": str(client["_id"]), **client})
            return None
        except (InvalidId, Exception) as e:
            logger.error(f"Erro ao buscar cliente: {str(e)}")
            return None

    @staticmethod
    async def create_client(client: Client) -> Client:
        try:
            logger.info("Tentando criar um novo cliente com os dados: %s", client.dict())
            
            client_dict = client.dict(exclude={"id"}, by_alias=True)
            
            # Garantir que as datas são timezone-aware
            now = datetime.now(timezone.utc)
            
            if client_dict["last_contact"].tzinfo is None:
                client_dict["last_contact"] = client_dict["last_contact"].replace(tzinfo=timezone.utc)
            
            if client_dict["next_followup"].tzinfo is None:
                client_dict["next_followup"] = client_dict["next_followup"].replace(tzinfo=timezone.utc)
            
            client_dict["created_at"] = now
            client_dict["updated_at"] = now
            
            # Verificar se o user_id está presente
            if "user_id" not in client_dict or not client_dict["user_id"]:
                logger.warning("Criando cliente sem user_id. Isso pode causar problemas de permissão.")
            else:
                # Garantir que user_id seja string
                client_dict["user_id"] = str(client_dict["user_id"])
                
            # Validate the client data
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', client_dict['email']):
                logger.error("Email inválido: %s", client_dict['email'])
                raise ValueError("Email inválido")
            
            # Calculate RFM scores - use lista vazia como padrão para interactions
            client_dict["rfm_scores"] = calculate_rfm_score(
                client_dict["last_contact"],
                client_dict["sales_potential"],
                client_dict.get("interaction_history", [])
            )
            
            result = await Database.database["clients"].insert_one(client_dict)
            return Client.parse_obj({"_id": str(result.inserted_id), **client_dict})
            
        except Exception as e:
            logger.error("Erro ao criar cliente: %s", str(e))
            raise

    @staticmethod
    async def update_client(client_id: str, client: Client) -> Client:
        try:
            client_dict = client.dict(exclude={"id"}, by_alias=True)
            
            # Garantir que as datas são timezone-aware
            now = datetime.now(timezone.utc)
            
            if client_dict["last_contact"].tzinfo is None:
                client_dict["last_contact"] = client_dict["last_contact"].replace(tzinfo=timezone.utc)
            
            if client_dict["next_followup"].tzinfo is None:
                client_dict["next_followup"] = client_dict["next_followup"].replace(tzinfo=timezone.utc)
            
            client_dict["updated_at"] = now
            
            # Calculate RFM scores
            client_dict["rfm_scores"] = calculate_rfm_score(
                client_dict["last_contact"],
                client_dict["sales_potential"],
                client_dict.get("interaction_history", [])
            )
            
            result = await Database.database["clients"].update_one(
                {"_id": ObjectId(client_id)},
                {"$set": client_dict}
            )
            
            if result.modified_count == 0:
                raise ValueError("Cliente não encontrado")
                
            updated_client = await Database.database["clients"].find_one({"_id": ObjectId(client_id)})
            return Client.parse_obj({"_id": str(updated_client["_id"]), **updated_client})
            
        except Exception as e:
            logger.error(f"Erro ao atualizar cliente: {str(e)}")
            raise

    @staticmethod
    async def delete_client(client_id: str) -> bool:
        try:
            result = await Database.database["clients"].delete_one({"_id": ObjectId(client_id)})
            return result.deleted_count > 0
        except (InvalidId, Exception) as e:
            logger.error(f"Erro ao deletar cliente: {str(e)}")
            return False

    @staticmethod
    async def add_interaction(client_id: str, interaction: Interaction) -> Client:
        try:
            client = await ClientService.get_client_by_id(client_id)
            if not client:
                return None
            
            # Garantir que a data da interação é timezone-aware
            interaction_dict = interaction.dict()
            if interaction_dict["date"].tzinfo is None:
                interaction_dict["date"] = interaction_dict["date"].replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            
            # Add the new interaction
            update_result = await Database.database["clients"].update_one(
                {"_id": ObjectId(client_id)},
                {
                    "$push": {"interaction_history": interaction_dict},
                    "$set": {
                        "last_contact": interaction_dict["date"],
                        "updated_at": now
                    }
                }
            )
            
            if update_result.modified_count > 0:
                # Recalculate RFM scores
                updated_client = await ClientService.get_client_by_id(client_id)
                rfm_scores = calculate_rfm_score(
                    updated_client.last_contact,
                    updated_client.sales_potential,
                    updated_client.interaction_history
                )
                
                await Database.database["clients"].update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": {"rfm_scores": rfm_scores}}
                )
                
                return await ClientService.get_client_by_id(client_id)
            return None
        except Exception as e:
            logger.error(f"Erro ao adicionar interação: {str(e)}")
            raise

    @staticmethod
    async def get_upcoming_followups(user_id: str = None) -> List[Client]:
        """
        Retorna a lista de clientes com follow-ups pendentes,
        ordenados por data de follow-up. Se user_id for fornecido,
        retorna apenas os clientes desse usuário.
        """
        try:
            today = datetime.now(timezone.utc)
            
            # Criar filtro
            query = {"next_followup": {"$gte": today}}
            
            # Adicionar filtro de usuário se fornecido
            if user_id:
                query["user_id"] = user_id
                logger.info(f"Filtrando follow-ups por user_id: {user_id}")
                
            upcoming_followups = await Database.database["clients"].find(query).sort("next_followup", 1).limit(10).to_list(10)

            result = []
            for client in upcoming_followups:
                # Garantir que os campos RFM estão corretos
                if "rfm_scores" in client and client["rfm_scores"]:
                    if "engagement" not in client["rfm_scores"] or client["rfm_scores"]["engagement"] is None:
                        client["rfm_scores"]["engagement"] = 0
                    
                    # Recalcular total se necessário
                    if "total" not in client["rfm_scores"] or client["rfm_scores"]["total"] is None:
                        if "recency" in client["rfm_scores"] and "potential" in client["rfm_scores"]:
                            client["rfm_scores"]["total"] = (
                                client["rfm_scores"]["recency"] + 
                                client["rfm_scores"]["potential"] + 
                                client["rfm_scores"]["engagement"]
                            )
                
                # Adicionar à lista de resultados
                try:
                    result.append(Client.parse_obj({"_id": str(client["_id"]), **client}))
                except Exception as e:
                    logger.error(f"Erro ao converter cliente {client.get('_id')}: {str(e)}")
            
            return result
        except Exception as e:
            logger.error(f"Erro ao buscar follow-ups: {str(e)}")
            return []

    @staticmethod
    async def get_clients_by_user(user_id: str) -> List[Client]:
        """Alias para get_all_clients com user_id específico"""
        return await ClientService.get_all_clients(user_id) 