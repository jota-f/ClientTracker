from fastapi import APIRouter, HTTPException, status, Body, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from app.models.invite_request import InviteRequestCreate
from app.services.invite_request_service import InviteRequestService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/invite-request", status_code=status.HTTP_201_CREATED)
async def create_invite_request(
    request: Request,
    invite_data: InviteRequestCreate = Body(...)
) -> Dict[str, Any]:
    """
    Cria uma nova solicitação de convite a partir da landing page.
    Esta rota é pública e não requer autenticação.
    """
    try:
        # Verificar se a requisição veio da landing page (proteção contra abuso)
        referer = request.headers.get("Referer", "")
        client_host = request.client.host if request.client else None
        
        logger.info(f"Nova solicitação de convite: {invite_data.email} (IP: {client_host}, Referer: {referer})")
        
        # Criar a solicitação de convite
        invite_request = await InviteRequestService.create_invite_request(invite_data)
        
        return {
            "status": "success",
            "message": "Solicitação de convite recebida com sucesso",
            "request_id": invite_request.id
        }
    except Exception as e:
        logger.error(f"Erro ao processar solicitação de convite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar sua solicitação. Por favor, tente novamente mais tarde."
        ) 