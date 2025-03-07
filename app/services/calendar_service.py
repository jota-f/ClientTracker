import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import json
import secrets
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException

from app.models.user import User, CalendarIntegrationType, CalendarIntegration
from app.services.user_service import UserService

# Configurar logging
logger = logging.getLogger(__name__)

# URLs e constantes
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_API_URL = "https://www.googleapis.com/calendar/v3"

OUTLOOK_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
OUTLOOK_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
OUTLOOK_API_URL = "https://graph.microsoft.com/v1.0"

# Obter credenciais do ambiente
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "mock-client-id")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "mock-client-secret")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/calendar/google/callback")

OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID", "mock-client-id")
OUTLOOK_CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET", "mock-client-secret")
OUTLOOK_REDIRECT_URI = os.getenv("OUTLOOK_REDIRECT_URI", "http://localhost:8000/api/calendar/outlook/callback")


class CalendarService:
    @staticmethod
    async def get_google_auth_url(user_id: str) -> str:
        """Gerar URL de autorização do Google Calendar"""
        state = secrets.token_urlsafe(16)
        
        # Armazenar o estado com o user_id para validação no callback
        # Idealmente, isso deve ser armazenado em um cache Redis ou similar
        # Para simplicidade, vamos usar um arquivo para esta implementação
        with open(f"tmp/{state}.json", "w") as f:
            json.dump({"user_id": user_id, "created_at": datetime.now(timezone.utc).isoformat()}, f)
        
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/calendar.events",
            "access_type": "offline",
            "state": state,
            "prompt": "consent"
        }
        
        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        return auth_url
    
    @staticmethod
    async def handle_google_callback(code: str, state: str) -> Dict[str, Any]:
        """Processar o callback do Google e obter os tokens"""
        # Verificar o estado para segurança
        try:
            with open(f"tmp/{state}.json", "r") as f:
                state_data = json.load(f)
            
            user_id = state_data.get("user_id")
            if not user_id:
                raise HTTPException(status_code=400, detail="Estado inválido")
            
            # Remover o arquivo de estado após o uso
            os.remove(f"tmp/{state}.json")
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail="Estado inválido ou expirado")
        
        # Trocar o código por tokens
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI
            }
            
            response = await client.post(GOOGLE_TOKEN_URL, data=token_data)
            
            if response.status_code != 200:
                logger.error(f"Erro ao obter token Google: {response.text}")
                raise HTTPException(status_code=400, detail="Falha ao obter token do Google")
            
            token_info = response.json()
            
            # Atualizar o usuário com as informações de integração
            calendar_integration = CalendarIntegration(
                type=CalendarIntegrationType.GOOGLE,
                enabled=True,
                auth_token=token_info.get("access_token"),
                refresh_token=token_info.get("refresh_token"),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_info.get("expires_in", 3600))
            )
            
            # Obter informações do calendário primário
            headers = {"Authorization": f"Bearer {token_info.get('access_token')}"}
            calendar_response = await client.get(f"{GOOGLE_API_URL}/users/me/calendarList", headers=headers)
            
            if calendar_response.status_code == 200:
                calendars = calendar_response.json().get("items", [])
                primary_calendar = next((cal for cal in calendars if cal.get("primary", False)), None)
                
                if primary_calendar:
                    calendar_integration.calendar_id = primary_calendar.get("id")
            
            # Atualizar o usuário no banco de dados
            user = await UserService.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")
            
            update_result = await UserService.update_calendar_integration(user_id, calendar_integration)
            
            return {
                "success": update_result,
                "message": "Integração com Google Calendar configurada com sucesso" if update_result else "Falha ao atualizar informações do usuário",
                "calendar_integration": calendar_integration
            }
    
    @staticmethod
    async def get_outlook_auth_url(user_id: str) -> str:
        """Gerar URL de autorização do Microsoft Outlook Calendar"""
        state = secrets.token_urlsafe(16)
        
        # Armazenar o estado com o user_id para validação no callback
        with open(f"tmp/{state}.json", "w") as f:
            json.dump({"user_id": user_id, "created_at": datetime.now(timezone.utc).isoformat()}, f)
        
        params = {
            "client_id": OUTLOOK_CLIENT_ID,
            "redirect_uri": OUTLOOK_REDIRECT_URI,
            "response_type": "code",
            "scope": "Calendars.ReadWrite offline_access",
            "state": state,
            "prompt": "consent"
        }
        
        auth_url = f"{OUTLOOK_AUTH_URL}?{urlencode(params)}"
        return auth_url
    
    @staticmethod
    async def handle_outlook_callback(code: str, state: str) -> Dict[str, Any]:
        """Processar o callback do Outlook e obter os tokens"""
        # Verificar o estado para segurança
        try:
            with open(f"tmp/{state}.json", "r") as f:
                state_data = json.load(f)
            
            user_id = state_data.get("user_id")
            if not user_id:
                raise HTTPException(status_code=400, detail="Estado inválido")
            
            # Remover o arquivo de estado após o uso
            os.remove(f"tmp/{state}.json")
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail="Estado inválido ou expirado")
        
        # Trocar o código por tokens
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": OUTLOOK_CLIENT_ID,
                "client_secret": OUTLOOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": OUTLOOK_REDIRECT_URI
            }
            
            response = await client.post(OUTLOOK_TOKEN_URL, data=token_data)
            
            if response.status_code != 200:
                logger.error(f"Erro ao obter token Outlook: {response.text}")
                raise HTTPException(status_code=400, detail="Falha ao obter token do Microsoft Outlook")
            
            token_info = response.json()
            
            # Atualizar o usuário com as informações de integração
            calendar_integration = CalendarIntegration(
                type=CalendarIntegrationType.OUTLOOK,
                enabled=True,
                auth_token=token_info.get("access_token"),
                refresh_token=token_info.get("refresh_token"),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_info.get("expires_in", 3600))
            )
            
            # Obter informações do calendário primário
            headers = {
                "Authorization": f"Bearer {token_info.get('access_token')}",
                "Content-Type": "application/json"
            }
            calendar_response = await client.get(f"{OUTLOOK_API_URL}/me/calendars", headers=headers)
            
            if calendar_response.status_code == 200:
                calendars = calendar_response.json().get("value", [])
                if calendars:
                    calendar_integration.calendar_id = calendars[0].get("id")
            
            # Atualizar o usuário no banco de dados
            user = await UserService.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")
            
            update_result = await UserService.update_calendar_integration(user_id, calendar_integration)
            
            return {
                "success": update_result,
                "message": "Integração com Microsoft Outlook configurada com sucesso" if update_result else "Falha ao atualizar informações do usuário",
                "calendar_integration": calendar_integration
            }
    
    @staticmethod
    async def refresh_token(user_id: str) -> bool:
        """Atualizar o token de acesso quando expirado"""
        user = await UserService.get_user_by_id(user_id)
        if not user or not user.calendar_integration or not user.calendar_integration.enabled:
            return False
        
        integration = user.calendar_integration
        
        # Verificar se o token está prestes a expirar
        if not integration.expires_at or integration.expires_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            return True  # Token ainda é válido
        
        if not integration.refresh_token:
            logger.error(f"Refresh token não disponível para o usuário {user_id}")
            return False
        
        # Configurar parâmetros baseados no tipo de integração
        if integration.type == CalendarIntegrationType.GOOGLE:
            token_url = GOOGLE_TOKEN_URL
            client_id = GOOGLE_CLIENT_ID
            client_secret = GOOGLE_CLIENT_SECRET
        elif integration.type == CalendarIntegrationType.OUTLOOK:
            token_url = OUTLOOK_TOKEN_URL
            client_id = OUTLOOK_CLIENT_ID
            client_secret = OUTLOOK_CLIENT_SECRET
        else:
            logger.error(f"Tipo de integração desconhecido: {integration.type}")
            return False
        
        # Obter novo token de acesso
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": integration.refresh_token,
                "grant_type": "refresh_token"
            }
            
            try:
                response = await client.post(token_url, data=token_data)
                
                if response.status_code != 200:
                    logger.error(f"Erro ao atualizar token: {response.text}")
                    return False
                
                token_info = response.json()
                
                # Atualizar tokens
                integration.auth_token = token_info.get("access_token")
                if token_info.get("refresh_token"):  # Nem sempre retornado
                    integration.refresh_token = token_info.get("refresh_token")
                
                integration.expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_info.get("expires_in", 3600))
                
                # Salvar no banco de dados
                return await UserService.update_calendar_integration(user_id, integration)
            
            except Exception as e:
                logger.error(f"Exceção ao atualizar token: {e}")
                return False
    
    @staticmethod
    async def create_event(user_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Criar um evento no calendário do usuário"""
        # Verificar e atualizar token se necessário
        token_refreshed = await CalendarService.refresh_token(user_id)
        if not token_refreshed:
            raise HTTPException(status_code=401, detail="Falha ao atualizar o token de acesso")
        
        user = await UserService.get_user_by_id(user_id)
        if not user or not user.calendar_integration or not user.calendar_integration.enabled:
            raise HTTPException(status_code=400, detail="Integração de calendário não configurada")
        
        integration = user.calendar_integration
        
        # Formatar evento baseado no tipo de integração
        if integration.type == CalendarIntegrationType.GOOGLE:
            return await CalendarService._create_google_event(integration, event_data)
        elif integration.type == CalendarIntegrationType.OUTLOOK:
            return await CalendarService._create_outlook_event(integration, event_data)
        else:
            raise HTTPException(status_code=400, detail="Tipo de integração não suportado")
    
    @staticmethod
    async def _create_google_event(integration: CalendarIntegration, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Criar evento no Google Calendar"""
        if not integration.calendar_id:
            raise HTTPException(status_code=400, detail="ID do calendário não disponível")
        
        # Converter para formato do Google Calendar
        google_event = {
            "summary": event_data.get("title"),
            "description": event_data.get("description", ""),
            "start": {
                "dateTime": event_data.get("start_time").isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": event_data.get("end_time").isoformat(),
                "timeZone": "UTC"
            }
        }
        
        # Adicionar participantes se houver
        if event_data.get("attendees"):
            google_event["attendees"] = [{"email": email} for email in event_data.get("attendees")]
        
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {integration.auth_token}"}
            
            response = await client.post(
                f"{GOOGLE_API_URL}/calendars/{integration.calendar_id}/events",
                json=google_event,
                headers=headers
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Erro ao criar evento no Google Calendar: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Falha ao criar evento no Google Calendar")
            
            return response.json()
    
    @staticmethod
    async def _create_outlook_event(integration: CalendarIntegration, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Criar evento no Microsoft Outlook Calendar"""
        # Converter para formato do Outlook Calendar
        outlook_event = {
            "subject": event_data.get("title"),
            "body": {
                "contentType": "text",
                "content": event_data.get("description", "")
            },
            "start": {
                "dateTime": event_data.get("start_time").isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": event_data.get("end_time").isoformat(),
                "timeZone": "UTC"
            }
        }
        
        # Adicionar participantes se houver
        if event_data.get("attendees"):
            outlook_event["attendees"] = [
                {
                    "emailAddress": {"address": email},
                    "type": "required"
                } for email in event_data.get("attendees")
            ]
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {integration.auth_token}",
                "Content-Type": "application/json"
            }
            
            calendar_id = integration.calendar_id or "primary"
            
            response = await client.post(
                f"{OUTLOOK_API_URL}/me/calendars/{calendar_id}/events",
                json=outlook_event,
                headers=headers
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Erro ao criar evento no Outlook Calendar: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Falha ao criar evento no Microsoft Outlook Calendar")
            
            return response.json()
    
    @staticmethod
    async def disconnect_calendar(user_id: str, calendar_type: CalendarIntegrationType) -> bool:
        """Desconectar a integração de calendário"""
        user = await UserService.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        # Criar uma nova integração vazia do tipo especificado
        calendar_integration = CalendarIntegration(
            type=calendar_type,
            enabled=False,
            auth_token=None,
            refresh_token=None,
            expires_at=None,
            calendar_id=None
        )
        
        # Atualizar no banco de dados
        return await UserService.update_calendar_integration(user_id, calendar_integration) 