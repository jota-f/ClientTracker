from fastapi import APIRouter, Depends, HTTPException, Request, Query, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_400_BAD_REQUEST
from typing import Dict, Optional, Any
import json
import logging
from datetime import datetime, timedelta
from fastapi.templating import Jinja2Templates

from app.core.dependencies import get_current_user, get_optional_user
from app.models.user import User, CalendarIntegrationType
from app.services.calendar_service import CalendarService
from app.services.client_service import ClientService
from app.services.user_service import UserService
from app.services.auth_service import AuthService

# Configurar logging
logger = logging.getLogger(__name__)

# Criar router
router = APIRouter(prefix="/calendar", tags=["calendar_web"])

# Templates
templates = Jinja2Templates(directory="app/templates")

# Rotas para Google Calendar
@router.get("/google/auth")
async def google_auth(current_user: User = Depends(get_current_user)):
    """Iniciar processo de autenticação com Google Calendar"""
    try:
        auth_url = await CalendarService.get_google_auth_url(current_user.id)
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Erro ao obter URL de autenticação Google: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar URL de autenticação: {str(e)}")

@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Callback para autorização do Google Calendar"""
    try:
        result = await CalendarService.handle_google_callback(code, state)
        
        if not result.get("success"):
            return RedirectResponse(url="/calendar/connect?error=Falha+na+integração+com+Google+Calendar", status_code=303)
        
        # Obter o token do usuário
        user = await UserService.get_user_by_id(result["user_id"])
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        # Gerar novo token JWT
        access_token = AuthService.create_access_token(data={"sub": user.email})
        
        # Redirecionar com o token
        response = RedirectResponse(url="/calendar?msg=Integração+com+Google+Calendar+concluída+com+sucesso", status_code=303)
        response.set_cookie(key="Authorization", value=f"Bearer {access_token}", httponly=True, secure=True, samesite="strict")
        return response
        
    except Exception as e:
        logger.error(f"Erro no callback do Google: {str(e)}")
        return RedirectResponse(url="/calendar/connect?error=Erro+no+callback+do+Google", status_code=303)

@router.post("/google/event")
async def add_google_event(
    event_data: Dict,
    current_user: User = Depends(get_current_user)
):
    """Adicionar evento ao Google Calendar"""
    try:
        result = await CalendarService.create_event(
            user_id=current_user.id,
            title=event_data.get("title"),
            start_time=event_data.get("start_time"),
            end_time=event_data.get("end_time"),
            description=event_data.get("description"),
            attendees=event_data.get("attendees"),
            all_day=event_data.get("all_day", False)
        )
        return result
    except Exception as e:
        logger.error(f"Erro ao criar evento no Google Calendar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar evento: {str(e)}")

# Rotas para Outlook Calendar
@router.get("/outlook/auth")
async def outlook_auth(current_user: User = Depends(get_current_user)):
    """Iniciar processo de autenticação com Outlook Calendar"""
    try:
        auth_url = await CalendarService.get_outlook_auth_url(current_user.id)
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Erro ao obter URL de autenticação Outlook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar URL de autenticação: {str(e)}")

@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Callback para autorização do Google Calendar"""
    try:
        result = await CalendarService.handle_google_callback(code, state)
        
        if not result.get("success"):
            return RedirectResponse(url="/calendar/connect?error=Falha+na+integração+com+Google+Calendar", status_code=303)
        
        # Obter o token do usuário
        user = await UserService.get_user_by_id(result["user_id"])
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        # Gerar novo token JWT
        access_token = AuthService.create_access_token(data={"sub": user.email})
        
        # Redirecionar com o token
        response = RedirectResponse(url="/calendar?msg=Integração+com+Google+Calendar+concluída+com+sucesso", status_code=303)
        response.set_cookie(key="Authorization", value=f"Bearer {access_token}", httponly=True, secure=True, samesite="strict")
        return response
        
    except Exception as e:
        logger.error(f"Erro no callback do Google: {str(e)}")
        return RedirectResponse(url="/calendar/connect?error=Erro+no+callback+do+Google", status_code=303)

@router.post("/outlook/event")
async def add_outlook_event(
    event_data: Dict,
    current_user: User = Depends(get_current_user)
):
    """Adicionar evento ao Outlook Calendar"""
    try:
        result = await CalendarService.create_event(
            user_id=current_user.id,
            title=event_data.get("title"),
            start_time=event_data.get("start_time"),
            end_time=event_data.get("end_time"),
            description=event_data.get("description"),
            attendees=event_data.get("attendees"),
            all_day=event_data.get("all_day", False)
        )
        return result
    except Exception as e:
        logger.error(f"Erro ao criar evento no Outlook Calendar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar evento: {str(e)}")

# Rotas gerais do calendário
@router.get("/integrations")
async def get_calendar_integrations(current_user: User = Depends(get_current_user)):
    """Obter informações sobre as integrações de calendário do usuário"""
    has_integration = (
        current_user.calendar_integration and 
        current_user.calendar_integration.enabled and
        current_user.calendar_integration.type != CalendarIntegrationType.NONE
    )
    
    return {
        "has_integration": has_integration,
        "integration_type": current_user.calendar_integration.type if has_integration else None
    }

@router.get("/", response_class=HTMLResponse)
async def calendar_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Página principal do calendário"""
    try:
        # Obter eventos do calendário
        events_result = await CalendarService.list_upcoming_events(current_user.id)
        events = events_result.get("events", []) if events_result.get("success") else []
        
        # Verificar se o usuário tem integração de calendário
        has_integration = (
            current_user.calendar_integration and 
            current_user.calendar_integration.enabled and
            current_user.calendar_integration.type != CalendarIntegrationType.NONE
        )
        
        integration_type = current_user.calendar_integration.type if has_integration else None
        
        # Renderizar template
        return templates.TemplateResponse(
            "calendar.html",
            {
                "request": request,
                "user": current_user,
                "events": events,
                "has_integration": has_integration,
                "integration_type": integration_type,
                "error": events_result.get("error") if not events_result.get("success") else None
            }
        )
    except Exception as e:
        logger.error(f"Erro ao carregar página do calendário: {str(e)}")
        return templates.TemplateResponse(
            "calendar.html",
            {
                "request": request,
                "user": current_user,
                "events": [],
                "has_integration": False,
                "error": f"Erro ao carregar eventos: {str(e)}"
            }
        )

@router.get("/connect", response_class=HTMLResponse)
async def connect_calendar_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Página para conectar calendários"""
    return templates.TemplateResponse(
        "connect_calendar.html",
        {
            "request": request,
            "user": current_user
        }
    )

@router.get("/connect/google")
async def connect_google_calendar(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Iniciar processo de conexão com Google Calendar"""
    try:
        auth_url = await CalendarService.get_google_auth_url(current_user.id)
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Erro ao conectar Google Calendar: {str(e)}")
        return templates.TemplateResponse(
            "connect_calendar.html",
            {
                "request": request,
                "user": current_user,
                "error": f"Erro ao conectar Google Calendar: {str(e)}"
            }
        )

@router.get("/connect/outlook")
async def connect_outlook_calendar(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Iniciar processo de conexão com Outlook Calendar"""
    try:
        auth_url = await CalendarService.get_outlook_auth_url(current_user.id)
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Erro ao conectar Outlook Calendar: {str(e)}")
        return templates.TemplateResponse(
            "connect_calendar.html",
            {
                "request": request,
                "user": current_user,
                "error": f"Erro ao conectar Outlook Calendar: {str(e)}"
            }
        )

@router.post("/disconnect/{calendar_type}")
async def disconnect_calendar(
    calendar_type: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Desconectar calendário"""
    try:
        cal_type = CalendarIntegrationType.GOOGLE
        if calendar_type.lower() == "outlook":
            cal_type = CalendarIntegrationType.OUTLOOK
            
        result = await CalendarService.disconnect_calendar(current_user.id, cal_type)
        
        if result:
            return RedirectResponse(url="/calendar?msg=Calendário+desconectado+com+sucesso", status_code=303)
        else:
            return templates.TemplateResponse(
                "calendar.html",
                {
                    "request": request,
                    "user": current_user,
                    "error": "Não foi possível desconectar o calendário"
                }
            )
    except Exception as e:
        logger.error(f"Erro ao desconectar calendário: {str(e)}")
        return templates.TemplateResponse(
            "calendar.html",
            {
                "request": request,
                "user": current_user,
                "error": f"Erro ao desconectar calendário: {str(e)}"
            }
        )

@router.get("/create", response_class=HTMLResponse)
async def create_event_page(
    request: Request,
    client_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Página para criar evento no calendário"""
    client = None
    if client_id:
        client = await ClientService.get_client_by_id(client_id)
        if client and client.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Acesso não autorizado a este cliente")
    
    # Verificar se o usuário tem integração de calendário
    has_integration = (
        current_user.calendar_integration and 
        current_user.calendar_integration.enabled and
        current_user.calendar_integration.type != CalendarIntegrationType.NONE
    )
    
    if not has_integration:
        return RedirectResponse(url="/calendar/connect?msg=Conecte+um+calendário+primeiro", status_code=303)
    
    # Obter lista de clientes para o dropdown
    clients = await ClientService.get_clients_by_user(current_user.id)
    
    return templates.TemplateResponse(
        "create_event.html",
        {
            "request": request,
            "user": current_user,
            "client": client,
            "clients": clients,
            "default_date": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "default_end_date": (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        }
    )

@router.post("/create", response_class=HTMLResponse)
async def create_event(
    request: Request,
    title: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    description: str = Form(""),
    attendees: str = Form(""),
    all_day: bool = Form(False),
    client_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Criar evento no calendário"""
    try:
        # Converter strings para datetime
        start_datetime = datetime.fromisoformat(start_time)
        end_datetime = datetime.fromisoformat(end_time)
        
        # Processar lista de participantes
        attendee_list = [email.strip() for email in attendees.split(",") if email.strip()]
        
        # Criar evento
        result = await CalendarService.create_event(
            user_id=current_user.id,
            title=title,
            start_time=start_datetime,
            end_time=end_datetime,
            description=description,
            attendees=attendee_list,
            all_day=all_day
        )
        
        if result.get("success"):
            # Se o evento foi criado para um cliente, atualizar a data de próximo contato
            if client_id:
                client = await ClientService.get_client_by_id(client_id)
                if client:
                    client.next_followup = start_datetime
                    await ClientService.update_client(client_id=client_id, client=client)
            
            return RedirectResponse(url="/calendar?msg=Evento+criado+com+sucesso", status_code=303)
        else:
            return templates.TemplateResponse(
                "create_event.html",
                {
                    "request": request,
                    "user": current_user,
                    "error": result.get("error", "Erro desconhecido ao criar evento"),
                    "default_date": start_time,
                    "default_end_date": end_time,
                    "form_data": {
                        "title": title,
                        "description": description,
                        "attendees": attendees,
                        "all_day": all_day,
                        "client_id": client_id
                    }
                }
            )
    except Exception as e:
        logger.error(f"Erro ao criar evento: {str(e)}")
        return templates.TemplateResponse(
            "create_event.html",
            {
                "request": request,
                "user": current_user,
                "error": f"Erro ao criar evento: {str(e)}",
                "default_date": datetime.now().strftime("%Y-%m-%dT%H:%M"),
                "default_end_date": (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
            }
        )

@router.get("/client/{client_id}/followup")
async def create_client_followup_page(
    client_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Página para criar evento de acompanhamento de cliente"""
    try:
        client = await ClientService.get_client_by_id(client_id)
        
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        if client.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Acesso não autorizado a este cliente")
        
        # Verificar se o usuário tem integração de calendário
        has_integration = (
            current_user.calendar_integration and 
            current_user.calendar_integration.enabled and
            current_user.calendar_integration.type != CalendarIntegrationType.NONE
        )
        
        if not has_integration:
            return RedirectResponse(url="/calendar/connect?msg=Conecte+um+calendário+primeiro", status_code=303)
        
        # Sugerir data para o próximo contato com base no RFM
        suggested_date = datetime.now() + timedelta(days=30)  # Padrão: 30 dias
        
        if hasattr(client, 'rfm_score'):
            # Ajustar com base no RFM
            if client.rfm_score >= 4.5:  # Clientes VIP
                suggested_date = datetime.now() + timedelta(days=7)
            elif client.rfm_score >= 3.5:  # Clientes importantes
                suggested_date = datetime.now() + timedelta(days=14)
            elif client.rfm_score >= 2.5:  # Clientes regulares
                suggested_date = datetime.now() + timedelta(days=30)
            else:  # Clientes ocasionais
                suggested_date = datetime.now() + timedelta(days=60)
        
        return templates.TemplateResponse(
            "client_followup.html",
            {
                "request": request,
                "user": current_user,
                "client": client,
                "suggested_date": suggested_date.strftime("%Y-%m-%dT%H:%M")
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao carregar página de acompanhamento: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "user": current_user,
                "error": f"Erro ao carregar página de acompanhamento: {str(e)}"
            }
        )

@router.post("/client/{client_id}/followup")
async def create_client_followup(
    client_id: str,
    request: Request,
    followup_date: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Criar evento de acompanhamento de cliente"""
    try:
        # Converter string para datetime
        followup_datetime = datetime.fromisoformat(followup_date)
        
        # Criar evento
        result = await CalendarService.create_client_followup_event(
            user_id=current_user.id,
            client_id=client_id,
            followup_date=followup_datetime
        )
        
        if result.get("success"):
            return RedirectResponse(url=f"/clients/{client_id}?msg=Evento+de+acompanhamento+criado+com+sucesso", status_code=303)
        else:
            client = await ClientService.get_client_by_id(client_id)
            return templates.TemplateResponse(
                "client_followup.html",
                {
                    "request": request,
                    "user": current_user,
                    "client": client,
                    "suggested_date": followup_date,
                    "error": result.get("error", "Erro desconhecido ao criar evento de acompanhamento")
                }
            )
    except Exception as e:
        logger.error(f"Erro ao criar evento de acompanhamento: {str(e)}")
        return templates.TemplateResponse(
            "client_followup.html",
            {
                "request": request,
                "user": current_user,
                "error": f"Erro ao criar evento de acompanhamento: {str(e)}",
                "suggested_date": datetime.now().strftime("%Y-%m-%dT%H:%M")
            }
        ) 