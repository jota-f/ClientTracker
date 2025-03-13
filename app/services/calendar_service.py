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
from app.models.client import Client, Interaction
from app.services.client_service import ClientService

# Configurar logging
logger = logging.getLogger(__name__)

# URLs e constantes
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_API_URL = "https://www.googleapis.com/calendar/v3"



# Obter credenciais do ambiente
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "754743042879-rk3m7tlqcrgvpaunm6qf7smcv0sm182f.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://pgs.app.br:8000/calendar/google/callback")


# Diretório para armazenar arquivos temporários
TMP_DIR = "tmp"
if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR)

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
            "prompt": "consent",
            "include_granted_scopes": "true"
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
                token_expiry=datetime.now() + timedelta(seconds=token_info.get("expires_in", 3600))
            )
            
            try:
                await UserService.update_calendar_integration(user_id, calendar_integration)
                return {"success": True, "user_id": user_id}
            except Exception as e:
                logger.error(f"Erro ao atualizar integração do calendário: {str(e)}")
                raise HTTPException(status_code=500, detail="Erro ao atualizar integração do calendário")
    
    @staticmethod
    async def get_outlook_auth_url(user_id: str) -> str:
        """Gerar URL de autorização do Outlook Calendar"""
        state = secrets.token_urlsafe(16)
        
        # Armazenar o estado com o user_id para validação no callback
        with open(f"tmp/{state}.json", "w") as f:
            json.dump({"user_id": user_id, "created_at": datetime.now(timezone.utc).isoformat()}, f)
        
        params = {
            "client_id": OUTLOOK_CLIENT_ID,
            "redirect_uri": OUTLOOK_REDIRECT_URI,
            "response_type": "code",
            "scope": "offline_access Calendars.ReadWrite",
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
                raise HTTPException(status_code=400, detail="Falha ao obter token do Outlook")
            
            token_info = response.json()
            
            # Atualizar o usuário com as informações de integração
            calendar_integration = CalendarIntegration(
                type=CalendarIntegrationType.OUTLOOK,
                enabled=True,
                auth_token=token_info.get("access_token"),
                refresh_token=token_info.get("refresh_token"),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_info.get("expires_in", 3600))
            )
            
            await UserService.update_calendar_integration(user_id, calendar_integration)
            
            return {"success": True, "user_id": user_id}

    @staticmethod
    async def refresh_google_token(user_id: str) -> bool:
        """Atualizar o token do Google Calendar quando expirado"""
        try:
            user = await UserService.get_user_by_id(user_id)
            
            if not user or not user.calendar_integration.enabled or user.calendar_integration.type != CalendarIntegrationType.GOOGLE:
                logger.warning(f"Usuário {user_id} não tem integração Google Calendar ativa")
                return False
            
            if not user.calendar_integration.refresh_token:
                logger.warning(f"Usuário {user_id} não tem refresh token para Google Calendar")
                return False
                
            # Verificar se o token está expirado ou próximo de expirar (menos de 5 minutos)
            now = datetime.now(timezone.utc)
            if user.calendar_integration.expires_at and user.calendar_integration.expires_at > now + timedelta(minutes=5):
                # Token ainda é válido
                return True
                
            # Atualizar o token
            async with httpx.AsyncClient() as client:
                token_data = {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "refresh_token": user.calendar_integration.refresh_token,
                    "grant_type": "refresh_token"
                }
                
                response = await client.post(GOOGLE_TOKEN_URL, data=token_data)
                
                if response.status_code != 200:
                    logger.error(f"Erro ao atualizar token Google: {response.text}")
                    return False
                
                token_info = response.json()
                
                # Atualizar a integração de calendário
                # Note que o refresh_token pode não ser retornado, nesse caso mantém o anterior
                calendar_integration = CalendarIntegration(
                    type=CalendarIntegrationType.GOOGLE,
                    enabled=True,
                    auth_token=token_info.get("access_token"),
                    refresh_token=token_info.get("refresh_token", user.calendar_integration.refresh_token),
                    expires_at=now + timedelta(seconds=token_info.get("expires_in", 3600))
                )
                
                await UserService.update_calendar_integration(user_id, calendar_integration)
                logger.info(f"Token Google Calendar renovado para usuário {user_id}")
                
                return True
                
        except Exception as e:
            logger.error(f"Erro ao atualizar token Google: {str(e)}")
            return False
    
    @staticmethod
    async def refresh_outlook_token(user_id: str) -> bool:
        """Atualizar o token do Outlook Calendar quando expirado"""
        try:
            user = await UserService.get_user_by_id(user_id)
            
            if not user or not user.calendar_integration.enabled or user.calendar_integration.type != CalendarIntegrationType.OUTLOOK:
                logger.warning(f"Usuário {user_id} não tem integração Outlook Calendar ativa")
                return False
            
            if not user.calendar_integration.refresh_token:
                logger.warning(f"Usuário {user_id} não tem refresh token para Outlook Calendar")
                return False
                
            # Verificar se o token está expirado ou próximo de expirar (menos de 5 minutos)
            now = datetime.now(timezone.utc)
            if user.calendar_integration.expires_at and user.calendar_integration.expires_at > now + timedelta(minutes=5):
                # Token ainda é válido
                return True
                
            # Atualizar o token
            async with httpx.AsyncClient() as client:
                token_data = {
                    "client_id": OUTLOOK_CLIENT_ID,
                    "client_secret": OUTLOOK_CLIENT_SECRET,
                    "refresh_token": user.calendar_integration.refresh_token,
                    "grant_type": "refresh_token"
                }
                
                response = await client.post(OUTLOOK_TOKEN_URL, data=token_data)
                
                if response.status_code != 200:
                    logger.error(f"Erro ao atualizar token Outlook: {response.text}")
                    return False
                
                token_info = response.json()
                
                # Atualizar a integração de calendário
                calendar_integration = CalendarIntegration(
                    type=CalendarIntegrationType.OUTLOOK,
                    enabled=True,
                    auth_token=token_info.get("access_token"),
                    refresh_token=token_info.get("refresh_token", user.calendar_integration.refresh_token),
                    expires_at=now + timedelta(seconds=token_info.get("expires_in", 3600))
                )
                
                await UserService.update_calendar_integration(user_id, calendar_integration)
                logger.info(f"Token Outlook Calendar renovado para usuário {user_id}")
                
                return True
                
        except Exception as e:
            logger.error(f"Erro ao atualizar token Outlook: {str(e)}")
            return False
    
    @staticmethod
    async def create_google_event(
        user_id: str, 
        title: str, 
        start_time: datetime, 
        end_time: datetime, 
        description: str = None,
        attendees: List[str] = None,
        all_day: bool = False
    ) -> Dict[str, Any]:
        """Criar um evento no Google Calendar"""
        try:
            # Verificar e atualizar token se necessário
            token_valid = await CalendarService.refresh_google_token(user_id)
            if not token_valid:
                return {"success": False, "error": "Token inválido ou expirado"}
            
            user = await UserService.get_user_by_id(user_id)
            
            # Preparar dados do evento
            event_data = {
                "summary": title,
                "description": description or "",
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "America/Sao_Paulo"
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "America/Sao_Paulo"
                },
                "extendedProperties": {
                    "private": {
                        "createdBy": "ClientTracker"
                    }
                }
            }
            
            # Se for evento de dia inteiro
            if all_day:
                event_data["start"] = {
                    "date": start_time.date().isoformat(),
                    "timeZone": "America/Sao_Paulo"
                }
                event_data["end"] = {
                    "date": end_time.date().isoformat(),
                    "timeZone": "America/Sao_Paulo"
                }
            
            # Adicionar participantes se especificados
            if attendees and len(attendees) > 0:
                event_data["attendees"] = [{"email": email} for email in attendees]
            
            # Enviar a requisição para a API
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {user.calendar_integration.auth_token}",
                    "Content-Type": "application/json"
                }
                
                response = await client.post(
                    f"{GOOGLE_API_URL}/calendars/primary/events",
                    json=event_data,
                    headers=headers
                )
                
                if response.status_code not in [200, 201]:
                    logger.error(f"Erro ao criar evento Google: {response.text}")
                    return {"success": False, "error": f"Falha ao criar evento: {response.text}"}
                
                event = response.json()
                logger.info(f"Evento Google criado com sucesso: {event.get('id')}")
                
                return {
                    "success": True,
                    "event_id": event.get("id"),
                    "html_link": event.get("htmlLink")
                }
                
        except Exception as e:
            error_msg = f"Erro ao criar evento Google: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    @staticmethod
    async def create_outlook_event(
        user_id: str, 
        title: str, 
        start_time: datetime, 
        end_time: datetime, 
        description: str = None,
        attendees: List[str] = None,
        all_day: bool = False
    ) -> Dict[str, Any]:
        """Criar um evento no Outlook Calendar"""
        try:
            # Verificar e atualizar token se necessário
            token_valid = await CalendarService.refresh_outlook_token(user_id)
            if not token_valid:
                return {"success": False, "error": "Token inválido ou expirado"}
            
            user = await UserService.get_user_by_id(user_id)
            
            # Formatar o evento de acordo com a API do Microsoft Graph
            event_data = {
                "subject": title,
                "body": {
                    "contentType": "HTML",
                    "content": description or ""
                },
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "America/Sao_Paulo"
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "America/Sao_Paulo"
                },
                "isAllDay": all_day
            }
            
            # Adicionar participantes se especificados
            if attendees and len(attendees) > 0:
                event_data["attendees"] = [
                    {
                        "emailAddress": {"address": email},
                        "type": "required"
                    } for email in attendees
                ]
            
            # Enviar a requisição para a API
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {user.calendar_integration.auth_token}",
                    "Content-Type": "application/json"
                }
                
                response = await client.post(
                    f"{OUTLOOK_API_URL}/me/events",
                    json=event_data,
                    headers=headers
                )
                
                if response.status_code not in [200, 201]:
                    logger.error(f"Erro ao criar evento Outlook: {response.text}")
                    return {"success": False, "error": f"Falha ao criar evento: {response.text}"}
                
                event = response.json()
                logger.info(f"Evento Outlook criado com sucesso: {event.get('id')}")
                
                return {
                    "success": True,
                    "event_id": event.get("id"),
                    "web_link": event.get("webLink")
                }
                
        except Exception as e:
            error_msg = f"Erro ao criar evento Outlook: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    @staticmethod
    async def create_event(
        user_id: str, 
        title: str, 
        start_time: datetime, 
        end_time: datetime, 
        description: str = None,
        attendees: List[str] = None,
        all_day: bool = False
    ) -> Dict[str, Any]:
        """Criar um evento no calendário do usuário (Google ou Outlook)"""
        try:
            user = await UserService.get_user_by_id(user_id)
            
            if not user or not user.calendar_integration.enabled:
                return {"success": False, "error": "Usuário não tem integração de calendário ativa"}
            
            # Escolher o método apropriado conforme o tipo de calendário
            if user.calendar_integration.type == CalendarIntegrationType.GOOGLE:
                return await CalendarService.create_google_event(
                    user_id, title, start_time, end_time, description, attendees, all_day
                )
            elif user.calendar_integration.type == CalendarIntegrationType.OUTLOOK:
                return await CalendarService.create_outlook_event(
                    user_id, title, start_time, end_time, description, attendees, all_day
                )
            else:
                return {"success": False, "error": "Tipo de calendário não suportado"}
        
        except Exception as e:
            error_msg = f"Erro ao criar evento: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    @staticmethod
    async def disconnect_calendar(user_id: str, calendar_type: CalendarIntegrationType) -> bool:
        """Desconectar a integração de calendário"""
        try:
            # Resetar a integração de calendário para o tipo "none"
            calendar_integration = CalendarIntegration(
                type=CalendarIntegrationType.NONE,
                enabled=False
            )
            
            result = await UserService.update_calendar_integration(user_id, calendar_integration)
            
            if result:
                logger.info(f"Calendário {calendar_type} desconectado para usuário {user_id}")
                return True
            else:
                logger.warning(f"Falha ao desconectar calendário {calendar_type} para usuário {user_id}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao desconectar calendário: {str(e)}")
            return False
    
    @staticmethod
    async def list_upcoming_google_events(user_id: str, max_results: int = 10) -> Dict[str, Any]:
        """Listar próximos eventos do Google Calendar"""
        try:
            # Verificar e atualizar token se necessário
            token_valid = await CalendarService.refresh_google_token(user_id)
            if not token_valid:
                return {"success": False, "error": "Token inválido ou expirado"}
            
            user = await UserService.get_user_by_id(user_id)
            
            # Preparar a requisição
            now = datetime.now(timezone.utc).isoformat()
            
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {user.calendar_integration.auth_token}"
                }
                
                params = {
                    "timeMin": now,
                    "maxResults": max_results,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "privateExtendedProperty": "createdBy=ClientTracker"
                }
                
                response = await client.get(
                    f"{GOOGLE_API_URL}/calendars/primary/events",
                    headers=headers,
                    params=params
                )
                
                if response.status_code != 200:
                    logger.error(f"Erro ao listar eventos Google: {response.text}")
                    return {"success": False, "error": f"Falha ao listar eventos: {response.text}"}
                
                data = response.json()
                events = data.get("items", [])
                
                # Processar e formatar eventos
                formatted_events = []
                for event in events:
                    start = event.get("start", {})
                    end = event.get("end", {})
                    
                    formatted_events.append({
                        "id": event.get("id"),
                        "title": event.get("summary"),
                        "description": event.get("description"),
                        "start": start.get("dateTime") or start.get("date"),
                        "end": end.get("dateTime") or end.get("date"),
                        "link": event.get("htmlLink"),
                        "all_day": "date" in start
                    })
                
                return {
                    "success": True,
                    "events": formatted_events
                }
                
        except Exception as e:
            error_msg = f"Erro ao listar eventos Google: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    @staticmethod
    async def list_upcoming_outlook_events(user_id: str, max_results: int = 10) -> Dict[str, Any]:
        """Listar próximos eventos do Outlook Calendar"""
        try:
            # Verificar e atualizar token se necessário
            token_valid = await CalendarService.refresh_outlook_token(user_id)
            if not token_valid:
                return {"success": False, "error": "Token inválido ou expirado"}
            
            user = await UserService.get_user_by_id(user_id)
            
            # Preparar a requisição
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {user.calendar_integration.auth_token}"
                }
                
                params = {
                    "$orderby": "start/dateTime",
                    "$top": max_results
                }
                
                response = await client.get(
                    f"{OUTLOOK_API_URL}/me/events",
                    headers=headers,
                    params=params
                )
                
                if response.status_code != 200:
                    logger.error(f"Erro ao listar eventos Outlook: {response.text}")
                    return {"success": False, "error": f"Falha ao listar eventos: {response.text}"}
                
                data = response.json()
                events = data.get("value", [])
                
                # Processar e formatar eventos
                formatted_events = []
                for event in events:
                    formatted_events.append({
                        "id": event.get("id"),
                        "title": event.get("subject"),
                        "description": event.get("bodyPreview"),
                        "start": event.get("start", {}).get("dateTime"),
                        "end": event.get("end", {}).get("dateTime"),
                        "link": event.get("webLink"),
                        "all_day": event.get("isAllDay", False)
                    })
                
                return {
                    "success": True,
                    "events": formatted_events
                }
                
        except Exception as e:
            error_msg = f"Erro ao listar eventos Outlook: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    @staticmethod
    async def list_upcoming_events(user_id: str, max_results: int = 10) -> Dict[str, Any]:
        """Listar próximos eventos do calendário do usuário (Google ou Outlook)"""
        try:
            user = await UserService.get_user_by_id(user_id)
            
            if not user or not user.calendar_integration.enabled:
                return {"success": False, "error": "Usuário não tem integração de calendário ativa"}
            
            # Escolher o método apropriado conforme o tipo de calendário
            if user.calendar_integration.type == CalendarIntegrationType.GOOGLE:
                return await CalendarService.list_upcoming_google_events(user_id, max_results)
            elif user.calendar_integration.type == CalendarIntegrationType.OUTLOOK:
                return await CalendarService.list_upcoming_outlook_events(user_id, max_results)
            else:
                return {"success": False, "error": "Tipo de calendário não suportado"}
        
        except Exception as e:
            error_msg = f"Erro ao listar eventos: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
            
    @staticmethod
    async def create_client_followup_event(user_id: str, client_id: str, followup_date: datetime) -> Dict[str, Any]:
        """Criar um evento de acompanhamento de cliente no calendário"""
        from app.services.client_service import ClientService
        
        try:
            client = await ClientService.get_client_by_id(client_id)
            
            if not client:
                return {"success": False, "error": "Cliente não encontrado"}
            
            if client.user_id != user_id:
                return {"success": False, "error": "Acesso não autorizado a este cliente"}
            
            # Configurar o evento
            start_time = followup_date
            end_time = followup_date + timedelta(minutes=30)  # 30 minutos por padrão
            
            title = f"Contato com {client.name} ({client.company})"
            description = f"""
            <p><strong>Cliente:</strong> {client.name}<br>
            <strong>Empresa:</strong> {client.company}<br>
            <strong>Email:</strong> {client.email}<br>
            <strong>Telefone:</strong> {client.phone}</p>
            
            <p>Este evento foi criado automaticamente pelo ClientTracker.</p>
            """
            
            # Criando o evento no calendário do usuário
            result = await CalendarService.create_event(
                user_id=user_id,
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                attendees=[client.email] if client.email else None
            )
            
            if result.get("success"):
                # Atualizar a data de próximo contato no cliente
                await ClientService.update_client(
                    client_id=client_id,
                    client=client
                )
                
                logger.info(f"Evento de acompanhamento criado para o cliente {client.name}")
            
            return result
            
        except Exception as e:
            error_msg = f"Erro ao criar evento de acompanhamento: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg} 