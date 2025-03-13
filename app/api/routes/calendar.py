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

# Criar router
router = APIRouter(prefix="/calendar", tags=["calendar"])

# Models para requisições e respostas
class GoogleAuthResponse(BaseModel):
    url: str

class CalendarEventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    attendees: Optional[List[str]] = None
    all_day: Optional[bool] = False

class CalendarEvent(BaseModel):
    id: str
    title: str
    description: Optional[str]
    start: str
    end: str
    link: Optional[str]
    all_day: bool

class CalendarEventListResponse(BaseModel):
    success: bool
    events: Optional[List[CalendarEvent]] = None
    error: Optional[str] = None

class EventCreateResponse(BaseModel):
    success: bool
    event_id: Optional[str] = None
    html_link: Optional[str] = None
    web_link: Optional[str] = None
    error: Optional[str] = None

class BasicResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

# Rotas
@router.get("/google/auth", response_model=GoogleAuthResponse)
async def get_google_auth_url(current_user: User = Depends(get_current_user)):
    """Obter URL de autorização para Google Calendar"""
    try:
        auth_url = await CalendarService.get_google_auth_url(current_user.id)
        return {"url": auth_url}
    except Exception as e:
        logger.error(f"Erro ao obter URL de autenticação Google: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar URL de autenticação: {str(e)}")

@router.get("/google/callback")
async def google_callback(code: str, state: str):
    """Processar callback do Google OAuth"""
    try:
        result = await CalendarService.handle_google_callback(code, state)
        # Redirecionar para uma página de confirmação
        return {"success": True, "message": "Integração com Google Calendar concluída com sucesso!"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro no callback do Google: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro no callback: {str(e)}")

@router.get("/outlook/auth", response_model=GoogleAuthResponse)
async def get_outlook_auth_url(current_user: User = Depends(get_current_user)):
    """Obter URL de autorização para Outlook Calendar"""
    try:
        auth_url = await CalendarService.get_outlook_auth_url(current_user.id)
        return {"url": auth_url}
    except Exception as e:
        logger.error(f"Erro ao obter URL de autenticação Outlook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar URL de autenticação: {str(e)}")

@router.get("/outlook/callback")
async def outlook_callback(code: str, state: str):
    """Processar callback do Outlook OAuth"""
    try:
        result = await CalendarService.handle_outlook_callback(code, state)
        # Redirecionar para uma página de confirmação
        return {"success": True, "message": "Integração com Outlook Calendar concluída com sucesso!"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro no callback do Outlook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro no callback: {str(e)}")

@router.post("/events", response_model=EventCreateResponse)
async def create_calendar_event(
    event: CalendarEventCreate,
    current_user: User = Depends(get_current_user)
):
    """Criar um evento no calendário integrado do usuário"""
    try:
        result = await CalendarService.create_event(
            user_id=current_user.id,
            title=event.title,
            start_time=event.start_time,
            end_time=event.end_time,
            description=event.description,
            attendees=event.attendees,
            all_day=event.all_day
        )
        return result
    except Exception as e:
        logger.error(f"Erro ao criar evento no calendário: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar evento: {str(e)}")

@router.post("/client/{client_id}/followup", response_model=EventCreateResponse)
async def create_client_followup(
    client_id: str,
    followup_date: datetime,
    current_user: User = Depends(get_current_user)
):
    """Criar um evento de acompanhamento para um cliente"""
    try:
        result = await CalendarService.create_client_followup_event(
            user_id=current_user.id,
            client_id=client_id,
            followup_date=followup_date
        )
        return result
    except Exception as e:
        logger.error(f"Erro ao criar evento de acompanhamento: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar evento de acompanhamento: {str(e)}")

@router.get("/events", response_model=CalendarEventListResponse)
async def list_calendar_events(
    max_results: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user)
):
    """Listar próximos eventos do calendário do usuário"""
    try:
        result = await CalendarService.list_upcoming_events(
            user_id=current_user.id,
            max_results=max_results
        )
        return result
    except Exception as e:
        logger.error(f"Erro ao listar eventos do calendário: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar eventos: {str(e)}")

@router.delete("/disconnect/{calendar_type}", response_model=BasicResponse)
async def disconnect_calendar(
    calendar_type: str,
    current_user: User = Depends(get_current_user)
):
    """Desconectar um calendário integrado"""
    try:
        # Converter string para enum
        cal_type = CalendarIntegrationType.GOOGLE
        if calendar_type.lower() == "outlook":
            cal_type = CalendarIntegrationType.OUTLOOK
        
        result = await CalendarService.disconnect_calendar(current_user.id, cal_type)
        
        if result:
            return {"success": True, "message": f"Calendário {calendar_type} desconectado com sucesso"}
        else:
            return {"success": False, "error": "Não foi possível desconectar o calendário"}
    except Exception as e:
        logger.error(f"Erro ao desconectar calendário: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao desconectar calendário: {str(e)}") 