from fastapi import APIRouter, HTTPException, Request, Depends
from app.models.client import Client, ClientCreate, Interaction
from app.services.client_service import ClientService
from app.models.user import User
from app.core.dependencies import get_current_user
from typing import List
from fastapi.templating import Jinja2Templates
import logging
from datetime import datetime, timezone, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[Client])
async def get_clients(current_user: User = Depends(get_current_user)):
    try:
        return await ClientService.get_all_clients(user_id=str(current_user.id))
    except Exception as e:
        logger.error(f"Erro ao listar clientes: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao listar clientes")

@router.post("/", response_model=Client)
async def create_client(client: ClientCreate, current_user: User = Depends(get_current_user)):
    try:
        # Log mais detalhado do payload recebido
        logger.info(f"ID do usuário atual: {current_user.id}")
        logger.info(f"Tentativa de criação de cliente. Payload completo: {client.dict()}")
        
        # Definir o user_id do cliente como o ID do usuário atual
        client_dict = client.dict()
        client_dict["user_id"] = str(current_user.id)
        
        try:
            # Verificar campos obrigatórios
            required_fields = ["name", "company", "email", "phone", "status", "sales_potential"]
            missing_fields = [field for field in required_fields if not client_dict.get(field)]
            
            if missing_fields:
                logger.error(f"Campos obrigatórios ausentes: {', '.join(missing_fields)}")
                raise ValueError(f"Campos obrigatórios ausentes: {', '.join(missing_fields)}")
            
            # Log para debugar datas
            logger.info(f"Datas recebidas - last_contact: {client_dict.get('last_contact')}, next_followup: {client_dict.get('next_followup')}")
            logger.info(f"Tipo last_contact: {type(client_dict.get('last_contact'))}, Tipo next_followup: {type(client_dict.get('next_followup'))}")
            
            # Garantir que temos listas vazias para histórico e tarefas
            if "interaction_history" not in client_dict or client_dict["interaction_history"] is None:
                logger.info("Inicializando interaction_history vazio")
                client_dict["interaction_history"] = []
                
            if "pending_tasks" not in client_dict or client_dict["pending_tasks"] is None:
                logger.info("Inicializando pending_tasks vazio")
                client_dict["pending_tasks"] = []
                
            # Validação completa dos campos
            try:
                # Tente criar o objeto diretamente com os dados existentes
                client_obj = Client(**client_dict)
                logger.info("Cliente validado com sucesso na primeira tentativa")
            except Exception as validation_error:
                # Log detalhado do erro
                logger.error(f"Erro na primeira tentativa de validação: {str(validation_error)}")
                if hasattr(validation_error, 'errors'):
                    for error in validation_error.errors():
                        logger.error(f"Campo: {error.get('loc', [])}, erro: {error.get('msg', '')}")
                
                # Se falhar, tente ajustar os dados e tentar novamente
                # Validação adicional para datas
                now = datetime.now(timezone.utc)
                
                # Se last_contact não foi fornecido ou não tem timezone, use a data atual
                if not client_dict.get("last_contact"):
                    logger.info("Data do último contato não fornecida, usando data atual")
                    client_dict["last_contact"] = now
                elif hasattr(client_dict["last_contact"], "tzinfo") and client_dict["last_contact"].tzinfo is None:
                    logger.info("Adicionando timezone UTC à data do último contato")
                    client_dict["last_contact"] = client_dict["last_contact"].replace(tzinfo=timezone.utc)
                    
                # Se next_followup não foi fornecido ou não tem timezone, use data atual + 7 dias
                if not client_dict.get("next_followup"):
                    logger.info("Data do próximo follow-up não fornecida, usando data atual + 7 dias")
                    client_dict["next_followup"] = now + timedelta(days=7)
                elif hasattr(client_dict["next_followup"], "tzinfo") and client_dict["next_followup"].tzinfo is None:
                    logger.info("Adicionando timezone UTC à data do próximo follow-up")
                    client_dict["next_followup"] = client_dict["next_followup"].replace(tzinfo=timezone.utc)
                
                # Tente novamente com os dados ajustados
                try:
                    client_obj = Client(**client_dict)
                    logger.info("Cliente validado com sucesso após ajustes")
                except Exception as second_validation_error:
                    logger.error(f"Erro na segunda tentativa de validação: {str(second_validation_error)}")
                    if hasattr(second_validation_error, 'errors'):
                        for error in second_validation_error.errors():
                            logger.error(f"Campo: {error.get('loc', [])}, erro: {error.get('msg', '')}")
                    raise second_validation_error
            
            # Validação adicional para datas
            now = datetime.now(timezone.utc)
            
            # Se last_contact não foi fornecido ou não tem timezone, use a data atual
            if not client_obj.last_contact:
                logger.info("Data do último contato não fornecida, usando data atual")
                client_obj.last_contact = now
            elif client_obj.last_contact.tzinfo is None:
                logger.info("Adicionando timezone UTC à data do último contato")
                client_obj.last_contact = client_obj.last_contact.replace(tzinfo=timezone.utc)
                
            # Se next_followup não foi fornecido ou não tem timezone, use data atual + 7 dias
            if not client_obj.next_followup:
                logger.info("Data do próximo follow-up não fornecida, usando data atual + 7 dias")
                client_obj.next_followup = now + timedelta(days=7)
            elif client_obj.next_followup.tzinfo is None:
                logger.info("Adicionando timezone UTC à data do próximo follow-up")
                client_obj.next_followup = client_obj.next_followup.replace(tzinfo=timezone.utc)
                
            # Garantir que interaction_history e pending_tasks existem
            if not client_obj.interaction_history:
                client_obj.interaction_history = []
                
            if not client_obj.pending_tasks:
                client_obj.pending_tasks = []
                
            # Logging detalhado dos campos para fins de depuração
            logger.info(f"Cliente validado com sucesso: {client_obj.dict(exclude={'id'})}")
            logger.info(f"last_contact: {client_obj.last_contact}, next_followup: {client_obj.next_followup}")
                
        except Exception as validation_error:
            logger.error(f"Erro de validação Pydantic: {str(validation_error)}")
            # Incluir detalhes do erro para depuração
            error_detail = str(validation_error)
            # Incluir detalhes específicos se for um erro de validação Pydantic
            if hasattr(validation_error, 'errors'):
                errors = validation_error.errors()
                logger.error(f"Detalhes dos erros de validação: {errors}")
                error_detail = f"Erros de validação: {errors}"
            raise HTTPException(status_code=422, detail=error_detail)
        
        # Tentar criar o cliente
        logger.info("Enviando dados para o ClientService para criação do cliente")
        client_result = await ClientService.create_client(client_obj)
        logger.info(f"Cliente criado com sucesso com ID {client_result.id}")
        return client_result
    except ValueError as e:
        logger.error(f"Erro de valor ao criar cliente: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as he:
        logger.error(f"HTTPException ao criar cliente: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Erro ao criar cliente: {str(e)}")
        logger.error(f"Tipo da exceção: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar cliente: {str(e)}")

@router.get("/{client_id}", response_model=Client)
async def get_client(client_id: str, current_user: User = Depends(get_current_user)):
    try:
        client = await ClientService.get_client_by_id(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        # Verificar se o cliente pertence ao usuário atual
        if client.user_id and client.user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Acesso não autorizado a este cliente")
            
        return client
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar cliente: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao buscar cliente")

@router.put("/{client_id}", response_model=Client)
async def update_client(client_id: str, client: Client, current_user: User = Depends(get_current_user)):
    try:
        # Verificar se o cliente existe e pertence ao usuário atual
        existing_client = await ClientService.get_client_by_id(client_id)
        if not existing_client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
            
        if existing_client.user_id and existing_client.user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Acesso não autorizado a este cliente")
        
        # Log detalhado dos dados recebidos
        logger.info(f"Tentativa de atualização do cliente {client_id}: {client.dict(exclude={'id'})}")
        
        # Garantir que o user_id seja mantido
        client_dict = client.dict()
        client_dict["user_id"] = str(current_user.id)
        
        try:
            # Verificar campos obrigatórios
            required_fields = ["name", "company", "email", "phone", "status", "sales_potential"]
            missing_fields = [field for field in required_fields if not client_dict.get(field)]
            
            if missing_fields:
                logger.error(f"Campos obrigatórios ausentes: {', '.join(missing_fields)}")
                raise ValueError(f"Campos obrigatórios ausentes: {', '.join(missing_fields)}")
            
            # Validação completa dos campos
            client_obj = Client(**client_dict)
            
            # Validação adicional para datas
            now = datetime.now(timezone.utc)
            
            # Manter as datas originais se não fornecidas
            if not client_obj.last_contact:
                if existing_client.last_contact:
                    client_obj.last_contact = existing_client.last_contact
                else:
                    logger.info("Data do último contato não fornecida, usando data atual")
                    client_obj.last_contact = now
            elif client_obj.last_contact.tzinfo is None:
                logger.info("Adicionando timezone UTC à data do último contato")
                client_obj.last_contact = client_obj.last_contact.replace(tzinfo=timezone.utc)
                
            if not client_obj.next_followup:
                if existing_client.next_followup:
                    client_obj.next_followup = existing_client.next_followup
                else:
                    logger.info("Data do próximo follow-up não fornecida, usando data atual + 7 dias")
                    client_obj.next_followup = now + timedelta(days=7)
            elif client_obj.next_followup.tzinfo is None:
                logger.info("Adicionando timezone UTC à data do próximo follow-up")
                client_obj.next_followup = client_obj.next_followup.replace(tzinfo=timezone.utc)
                
            # Manter o histórico de interações e tarefas pendentes existentes se não fornecidos
            if not client_obj.interaction_history and existing_client.interaction_history:
                client_obj.interaction_history = existing_client.interaction_history
                
            if not client_obj.pending_tasks and existing_client.pending_tasks:
                client_obj.pending_tasks = existing_client.pending_tasks
                
            # Logging detalhado dos campos para fins de depuração
            logger.info(f"Cliente validado com sucesso para atualização: {client_obj.dict(exclude={'id'})}")
            logger.info(f"last_contact: {client_obj.last_contact}, next_followup: {client_obj.next_followup}")
                
        except Exception as validation_error:
            logger.error(f"Erro de validação Pydantic na atualização: {str(validation_error)}")
            # Incluir detalhes do erro para depuração
            error_detail = str(validation_error)
            # Incluir detalhes específicos se for um erro de validação Pydantic
            if hasattr(validation_error, 'errors'):
                error_detail = f"Erros de validação: {validation_error.errors()}"
            raise HTTPException(status_code=422, detail=f"Erro de validação: {error_detail}")
        
        updated_client = await ClientService.update_client(client_id, client_obj)
        return updated_client
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Erro de valor ao atualizar cliente: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao atualizar cliente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar cliente: {str(e)}")

@router.delete("/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user)):
    try:
        # Verificar se o cliente existe e pertence ao usuário atual
        client = await ClientService.get_client_by_id(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
            
        if client.user_id and client.user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Acesso não autorizado a este cliente")
            
        success = await ClientService.delete_client(client_id)
        return {"message": "Cliente excluído com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao excluir cliente: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao excluir cliente")

@router.post("/{client_id}/interactions", response_model=Client)
async def add_interaction(client_id: str, interaction: Interaction, current_user: User = Depends(get_current_user)):
    try:
        # Verificar se o cliente existe e pertence ao usuário atual
        client = await ClientService.get_client_by_id(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
            
        if client.user_id and client.user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Acesso não autorizado a este cliente")
            
        updated_client = await ClientService.add_interaction(client_id, interaction)
        return updated_client
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao adicionar interação: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao adicionar interação") 