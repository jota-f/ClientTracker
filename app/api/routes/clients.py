from fastapi import APIRouter, HTTPException, Request, Depends
from app.models.client import Client, Interaction
from app.services.client_service import ClientService
from app.models.user import User
from app.core.dependencies import get_current_user
from typing import List
from fastapi.templating import Jinja2Templates
import logging
from datetime import datetime, timezone

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
async def create_client(client: Client, current_user: User = Depends(get_current_user)):
    try:
        logger.info(f"Tentativa de criação de cliente: {client.dict(exclude={'id'})}")
        
        # Definir o user_id do cliente como o ID do usuário atual
        client_dict = client.dict()
        client_dict["user_id"] = str(current_user.id)
        
        try:
            # Validação completa dos campos
            client_obj = Client(**client_dict)
            
            # Validação adicional
            if not client_obj.last_contact:
                raise ValueError("Data do último contato é obrigatória")
                
            if not client_obj.next_followup:
                raise ValueError("Data do próximo follow-up é obrigatória")
                
            # Garantir que as datas têm timezone
            if client_obj.last_contact.tzinfo is None:
                client_obj.last_contact = client_obj.last_contact.replace(tzinfo=timezone.utc)
                
            if client_obj.next_followup.tzinfo is None:
                client_obj.next_followup = client_obj.next_followup.replace(tzinfo=timezone.utc)
                
        except Exception as validation_error:
            logger.error(f"Erro de validação Pydantic: {str(validation_error)}")
            # Incluir detalhes do erro para depuração
            error_detail = str(validation_error)
            # Incluir detalhes específicos se for um erro de validação Pydantic
            if hasattr(validation_error, 'errors'):
                error_detail = f"Erros de validação: {validation_error.errors()}"
            raise HTTPException(status_code=422, detail=f"Erro de validação: {error_detail}")
        
        # Tentar criar o cliente
        return await ClientService.create_client(client_obj)
    except ValueError as e:
        logger.error(f"Erro de valor ao criar cliente: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar cliente: {str(e)}")
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
        
        # Garantir que o user_id seja mantido
        client_dict = client.dict()
        client_dict["user_id"] = str(current_user.id)
        
        try:
            # Validação completa dos campos
            client_obj = Client(**client_dict)
            
            # Validação adicional
            if not client_obj.last_contact:
                raise ValueError("Data do último contato é obrigatória")
                
            if not client_obj.next_followup:
                raise ValueError("Data do próximo follow-up é obrigatória")
                
            # Garantir que as datas têm timezone
            if client_obj.last_contact.tzinfo is None:
                client_obj.last_contact = client_obj.last_contact.replace(tzinfo=timezone.utc)
                
            if client_obj.next_followup.tzinfo is None:
                client_obj.next_followup = client_obj.next_followup.replace(tzinfo=timezone.utc)
                
        except Exception as validation_error:
            logger.error(f"Erro de validação Pydantic: {str(validation_error)}")
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