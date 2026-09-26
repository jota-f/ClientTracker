from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body
from app.core.dependencies import get_admin_user
from typing import Dict, Any, List, Optional
from app.models.user import User
from app.core.database import Database
from app.services.invite_request_service import InviteRequestService
from app.services.invite_service import InviteService
from app.services.notification_service import NotificationService
from datetime import datetime, timezone
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/invite-requests", status_code=status.HTTP_200_OK)
async def list_invite_requests(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """
    Lista todas as solicitações de convite com filtro opcional por status.
    Apenas administradores podem chamar este endpoint.
    """
    try:
        logger.info(f"Admin {current_user.email} solicitou lista de convites com filtro: {status_filter}")
        
        if status_filter and status_filter not in ["pending", "approved", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filtro de status inválido: {status_filter}. Valores aceitos: pending, approved, rejected"
            )
        
        requests = await InviteRequestService.get_invite_requests(status_filter)
        stats = await InviteRequestService.get_statistics()
        
        response_data = {
            "total": len(requests),
            "statistics": stats,
            "invite_requests": [
                {
                    "id": req.id,
                    "name": req.name,
                    "email": req.email,
                    "company": req.company,
                    "status": req.status,
                    "created_at": req.created_at.isoformat() if req.created_at else None,
                    "processed_at": req.processed_at.isoformat() if req.processed_at else None,
                    "processed_by": req.processed_by,
                    "notes": req.notes
                }
                for req in requests
            ]
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao listar solicitações de convite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor ao listar solicitações"
        )

@router.get("/invite-requests/statistics", status_code=status.HTTP_200_OK)
async def get_invite_statistics(
    current_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """
    Obtém estatísticas das solicitações de convite.
    Apenas administradores podem chamar este endpoint.
    """
    try:
        stats = await InviteRequestService.get_statistics()
        total = stats.get("total", 0)
        approved = stats.get("approved", 0)
        rejected = stats.get("rejected", 0)
        pending = stats.get("pending", 0)
        
        approval_rate = 0
        if approved + rejected > 0:
            approval_rate = round((approved / (approved + rejected)) * 100, 2)
            
        return {
            **stats,
            "approval_rate": approval_rate,
            "pending_percentage": round((pending / total * 100) if total > 0 else 0, 2),
            "approved_percentage": round((approved / total * 100) if total > 0 else 0, 2),
            "rejected_percentage": round((rejected / total * 100) if total > 0 else 0, 2)
        }
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de convites: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao obter estatísticas"
        )

@router.get("/invite-requests/{request_id}", status_code=status.HTTP_200_OK)
async def get_invite_request(
    request_id: str,
    current_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Obtém uma solicitação específica por ID."""
    try:
        invite_request = await InviteRequestService.get_invite_request_by_id(request_id)
        if not invite_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação de convite não encontrada"
            )
            
        return {
            "id": invite_request.id,
            "name": invite_request.name,
            "email": invite_request.email,
            "company": invite_request.company,
            "status": invite_request.status,
            "created_at": invite_request.created_at.isoformat() if invite_request.created_at else None,
            "processed_at": invite_request.processed_at.isoformat() if invite_request.processed_at else None,
            "processed_by": invite_request.processed_by,
            "notes": invite_request.notes
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar solicitação {request_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/invite-requests/{request_id}/process", status_code=status.HTTP_200_OK)
async def process_invite_request(
    request_id: str,
    status: str = Body(..., pattern="^(approved|rejected)$"),
    notes: Optional[str] = Body(None, max_length=500),
    create_invite: bool = Body(False),
    current_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """
    Processa uma solicitação de convite (aprovar/rejeitar).
    Opcionalmente cria código de convite e envia e-mail com link.
    """
    try:
        logger.info(f"Admin {current_user.email} processando solicitação {request_id} -> {status}")
        
        if status == "rejected":
            create_invite = False
            
        success = await InviteRequestService.update_invite_request_status(
            request_id,
            status,
            str(current_user.id),
            notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação não encontrada ou já processada"
            )
            
        result = {
            "status": "success",
            "message": f"Solicitação de convite {'aprovada' if status == 'approved' else 'rejeitada'} com sucesso",
            "invite_code": None,
            "request_id": request_id,
            "processed_by": current_user.email,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        if status == "approved" and create_invite:
            invite_request = await InviteRequestService.get_invite_request_by_id(request_id)
            if invite_request:
                invite = await InviteService.create_invite_code(
                    created_by=str(current_user.id),
                    email=invite_request.email,
                    expires_in_days=30
                )
                result["invite_code"] = invite.code
                result["message"] += f". Código de convite gerado: {invite.code}"
                
                try:
                    notification_service = NotificationService()
                    email_sent = await notification_service.send_invite_code_email(
                        email=invite_request.email,
                        name=invite_request.name,
                        invite_code=invite.code,
                        company=invite_request.company
                    )
                    result["email_sent"] = email_sent
                    if email_sent:
                        result["message"] += " e e-mail enviado com sucesso"
                except Exception as mail_err:
                    logger.error(f"Erro ao enviar email de convite: {mail_err}")
                    result["email_sent"] = False
                    result["email_error"] = str(mail_err)
                    
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar solicitação {request_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/invite-requests/{request_id}", status_code=status.HTTP_200_OK)
async def delete_invite_request(
    request_id: str,
    current_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Remove uma solicitação de convite."""
    try:
        invite_request = await InviteRequestService.get_invite_request_by_id(request_id)
        if not invite_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação não encontrada"
            )
            
        result = await Database.database["invite_requests"].delete_one({"_id": ObjectId(request_id)})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação não encontrada"
            )
            
        return {
            "status": "success",
            "message": "Solicitação removida com sucesso",
            "deleted_id": request_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao remover solicitação: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/invite-requests/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_old_requests(
    days: int = Body(90, ge=30, le=365),
    current_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Remove solicitações rejeitadas antigas."""
    try:
        deleted_count = await InviteRequestService.cleanup_old_rejected_requests(days)
        return {
            "status": "success",
            "message": f"Limpeza concluída: {deleted_count} solicitações removidas",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Erro ao limpar solicitações: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
