from datetime import datetime, timezone, timedelta
from app.models.client import Client, ClientCreate, Interaction
from app.core.database import Database
from app.services.rfm import calculate_rfm_score
from app.services.contact_schedule_service import ContactScheduleService
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
    async def create_client(client: ClientCreate) -> Client:
        try:
            logger.info("Tentando criar um novo cliente com os dados: %s", client.dict())
            
            client_dict = client.dict(by_alias=True)
            
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
                raise ValueError("O ID do usuário é obrigatório para criar um cliente")
            else:
                # Garantir que user_id seja string
                client_dict["user_id"] = str(client_dict["user_id"])
            
            # Não precisamos validar o email aqui, pois o Pydantic já valida com EmailStr
            
            # Calculate RFM scores - use lista vazia como padrão para interactions
            client_dict["rfm_scores"] = calculate_rfm_score(
                client_dict["last_contact"],
                client_dict["sales_potential"],
                client_dict.get("interaction_history", [])
            )
            
            result = await Database.database["clients"].insert_one(client_dict)
            return Client.parse_obj({"_id": str(result.inserted_id), **client_dict})
            
        except ValueError as ve:
            logger.error("Erro de validação ao criar cliente: %s", str(ve))
            raise
        except Exception as e:
            logger.error("Erro ao criar cliente: %s", str(e))
            raise

    @staticmethod
    async def update_client(client_id: str, client: Client) -> Client:
        try:
            # Primeiro, busca o cliente existente para garantir que dados importantes não serão perdidos
            existing_client = await Database.database["clients"].find_one({"_id": ObjectId(client_id)})
            if not existing_client:
                logger.error(f"Cliente não encontrado para atualização: {client_id}")
                raise ValueError("Cliente não encontrado")
            
            # Extrai os dados do novo cliente
            client_dict = client.dict(exclude={"id"}, by_alias=True)
            
            # Garantir que campos obrigatórios estejam presentes
            if "interaction_history" not in client_dict or client_dict["interaction_history"] is None:
                client_dict["interaction_history"] = existing_client.get("interaction_history", [])

            if "pending_tasks" not in client_dict or client_dict["pending_tasks"] is None:
                client_dict["pending_tasks"] = existing_client.get("pending_tasks", [])
                
            # Manter user_id original
            client_dict["user_id"] = existing_client.get("user_id")
            
            # Garantir que as datas são timezone-aware
            now = datetime.now(timezone.utc)
            
            # Atualizar created_at apenas se não existir
            if "created_at" not in client_dict or client_dict["created_at"] is None:
                client_dict["created_at"] = existing_client.get("created_at", now)
                
            # Sempre atualizar updated_at
            client_dict["updated_at"] = now
            
            # Garantir que as datas principais têm timezone
            if "last_contact" in client_dict and client_dict["last_contact"]:
                if client_dict["last_contact"].tzinfo is None:
                    client_dict["last_contact"] = client_dict["last_contact"].replace(tzinfo=timezone.utc)
            else:
                client_dict["last_contact"] = existing_client.get("last_contact", now)
            
            if "next_followup" in client_dict and client_dict["next_followup"]:
                if client_dict["next_followup"].tzinfo is None:
                    client_dict["next_followup"] = client_dict["next_followup"].replace(tzinfo=timezone.utc)
            else:
                client_dict["next_followup"] = existing_client.get("next_followup", now + timedelta(days=7))
            
            # Calculate RFM scores
            client_dict["rfm_scores"] = calculate_rfm_score(
                client_dict["last_contact"],
                client_dict["sales_potential"],
                client_dict.get("interaction_history", [])
            )
            
            # Log detalhado para depuração
            logger.info(f"Atualizando cliente {client_id} com dados: {client_dict}")
            
            result = await Database.database["clients"].update_one(
                {"_id": ObjectId(client_id)},
                {"$set": client_dict}
            )
            
            if result.modified_count == 0 and result.matched_count == 0:
                logger.error(f"Cliente não encontrado para atualização: {client_id}")
                raise ValueError("Cliente não encontrado")
                
            updated_client = await Database.database["clients"].find_one({"_id": ObjectId(client_id)})
            
            if not updated_client:
                logger.error(f"Falha ao recuperar cliente após atualização: {client_id}")
                raise ValueError("Falha ao recuperar cliente após atualização")
                
            return Client.parse_obj({"_id": str(updated_client["_id"]), **updated_client})
            
        except ValueError as ve:
            logger.error(f"Erro de validação ao atualizar cliente: {str(ve)}")
            raise ve
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
            # Garantir que a data da interação tem timezone
            if interaction.date.tzinfo is None:
                interaction.date = interaction.date.replace(tzinfo=timezone.utc)
            
            interaction_dict = interaction.dict()
            
            # Atualizar o cliente com a nova interação e última data de contato
            update_result = await Database.database["clients"].update_one(
                {"_id": ObjectId(client_id)},
                {
                    "$push": {"interaction_history": interaction_dict},
                    "$set": {"last_contact": interaction.date}
                }
            )
            
            if update_result.modified_count > 0:
                # Recalcular RFM scores
                updated_client = await ClientService.get_client_by_id(client_id)
                rfm_scores = calculate_rfm_score(
                    updated_client.last_contact,
                    updated_client.sales_potential,
                    updated_client.interaction_history
                )
                
                # Atualizar RFM e próxima data de contato
                await Database.database["clients"].update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": {"rfm_scores": rfm_scores}}
                )
                
                # Atualizar próxima data de contato baseada no novo RFM
                await ContactScheduleService.update_next_followup(client_id)
                
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

    @staticmethod
    async def ensure_client_dates_have_timezone():
        """
        Garante que todas as datas dos clientes tenham timezone UTC
        """
        try:
            logger.info("Iniciando verificação de timezone nas datas dos clientes")
            clients = await Database.database["clients"].find({}).to_list(1000)
            updated = 0

            for client in clients:
                needs_update = False
                update_fields = {}

                # Verificar last_contact
                if "last_contact" in client and client["last_contact"] and client["last_contact"].tzinfo is None:
                    update_fields["last_contact"] = client["last_contact"].replace(tzinfo=timezone.utc)
                    needs_update = True

                # Verificar next_followup
                if "next_followup" in client and client["next_followup"] and client["next_followup"].tzinfo is None:
                    update_fields["next_followup"] = client["next_followup"].replace(tzinfo=timezone.utc)
                    needs_update = True

                # Verificar created_at
                if "created_at" in client and client["created_at"] and client["created_at"].tzinfo is None:
                    update_fields["created_at"] = client["created_at"].replace(tzinfo=timezone.utc)
                    needs_update = True

                # Verificar updated_at
                if "updated_at" in client and client["updated_at"] and client["updated_at"].tzinfo is None:
                    update_fields["updated_at"] = client["updated_at"].replace(tzinfo=timezone.utc)
                    needs_update = True

                # Verificar datas nas interações
                if "interaction_history" in client and client["interaction_history"]:
                    updated_interactions = []
                    interactions_updated = False

                    for interaction in client["interaction_history"]:
                        if "date" in interaction and interaction["date"] and interaction["date"].tzinfo is None:
                            interaction["date"] = interaction["date"].replace(tzinfo=timezone.utc)
                            interactions_updated = True
                        updated_interactions.append(interaction)

                    if interactions_updated:
                        update_fields["interaction_history"] = updated_interactions
                        needs_update = True

                if needs_update:
                    await Database.database["clients"].update_one(
                        {"_id": client["_id"]},
                        {"$set": update_fields}
                    )
                    updated += 1

            logger.info(f"Atualização de timezone concluída. {updated} clientes atualizados")
            return updated
        except Exception as e:
            logger.error(f"Erro ao atualizar timezone dos clientes: {str(e)}")
            return 0 