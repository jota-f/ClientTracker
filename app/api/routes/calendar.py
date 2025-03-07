import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response, Request
from pydantic import BaseModel, Field, validator
from datetime import datetime, timezone

from app.models.user import User, CalendarIntegrationType
from app.services.calendar_service import CalendarService
from app.core.dependencies import get_current_user

# Configurar logging
logger = logging.getLogger(__name__)

# Modelo para criação de eventos
class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    attendees: Optional[List[str]] = None
    all_day: Optional[bool] = False
    
    @validator('end_time')
    def end_time_after_start_time(cls, v, values):
        if 'start_time' in values and v < values['start_time']:
            raise ValueError('O horário de término deve ser posterior ao horário de início')
        return v
    
    @validator('start_time', 'end_time')
    def ensure_timezone(cls, v):
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

router = APIRouter(tags=["Integração de Calendário"])

@router.get("/google/auth-url")
async def get_google_auth_url(current_user: User = Depends(get_current_user)):
    """
    Obtém a URL de autorização para o Google Calendar.
    """
    try:
        auth_url = await CalendarService.get_google_auth_url(str(current_user.id))
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Erro ao obter URL de autorização do Google: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter URL de autorização"
        )

@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None)
):
    """
    Processamento do callback do Google OAuth2.
    """
    try:
        if error:
            return {"success": False, "error": error}
        
        result = await CalendarService.handle_google_callback(code, state)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Erro no callback do Google: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar callback do Google"
        )

@router.get("/outlook/auth-url")
async def get_outlook_auth_url(current_user: User = Depends(get_current_user)):
    """
    Obtém a URL de autorização para o Microsoft Outlook Calendar.
    """
    try:
        auth_url = await CalendarService.get_outlook_auth_url(str(current_user.id))
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Erro ao obter URL de autorização do Outlook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter URL de autorização"
        )

@router.get("/outlook/callback")
async def outlook_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None)
):
    """
    Processamento do callback do Microsoft OAuth2.
    """
    try:
        if error:
            return {"success": False, "error": error}
        
        result = await CalendarService.handle_outlook_callback(code, state)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Erro no callback do Outlook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar callback do Outlook"
        )

@router.post("/events", status_code=status.HTTP_201_CREATED)
async def create_event(
    event: EventCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Cria um evento no calendário do usuário.
    """
    try:
        if not current_user.calendar_integration or not current_user.calendar_integration.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhuma integração de calendário configurada"
            )
        
        result = await CalendarService.create_event(str(current_user.id), event.dict())
        return {"success": True, "event": result}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Erro ao criar evento: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar evento no calendário"
        )

@router.delete("/disconnect/{calendar_type}")
async def disconnect_calendar(
    calendar_type: CalendarIntegrationType,
    current_user: User = Depends(get_current_user)
):
    """
    Desconecta a integração com o calendário.
    """
    try:
        result = await CalendarService.disconnect_calendar(str(current_user.id), calendar_type)
        if result:
            return {"success": True, "message": f"Desconexão do {calendar_type} realizada com sucesso"}
        else:
            return {"success": False, "message": "Falha ao desconectar calendário"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Erro ao desconectar calendário: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao desconectar calendário"
        ) 