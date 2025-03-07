from fastapi import APIRouter, HTTPException, Request, Depends
from app.models.client import Client, Interaction
from app.services.client_service import ClientService
from typing import List
from fastapi.templating import Jinja2Templates
import logging
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[Client])
async def get_clients():
    try:
        return await ClientService.get_all_clients()
    except Exception as e:
        logger.error(f"Erro ao listar clientes: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao listar clientes")

@router.post("/", response_model=Client)
async def create_client(client: Client):
    try:
        return await ClientService.create_client(client)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao criar cliente: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao criar cliente")

@router.get("/{client_id}", response_model=Client)
async def get_client(client_id: str):
    try:
        client = await ClientService.get_client_by_id(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        return client
    except Exception as e:
        logger.error(f"Erro ao buscar cliente: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao buscar cliente")

@router.put("/{client_id}", response_model=Client)
async def update_client(client_id: str, client: Client):
    try:
        updated_client = await ClientService.update_client(client_id, client)
        if not updated_client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        return updated_client
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao atualizar cliente: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao atualizar cliente")

@router.delete("/{client_id}")
async def delete_client(client_id: str):
    try:
        success = await ClientService.delete_client(client_id)
        if not success:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        return {"message": "Cliente excluído com sucesso"}
    except Exception as e:
        logger.error(f"Erro ao excluir cliente: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao excluir cliente")

@router.post("/{client_id}/interactions", response_model=Client)
async def add_interaction(client_id: str, interaction: Interaction):
    try:
        client = await ClientService.add_interaction(client_id, interaction)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        return client
    except Exception as e:
        logger.error(f"Erro ao adicionar interação: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao adicionar interação") 