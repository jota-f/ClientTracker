import logging
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.services.notification_service import NotificationService
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.task_service import TaskService
from app.services.client_service import ClientService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

notification_service = NotificationService()

# Models para requisições e respostas
class EmailNotification(BaseModel):
    subject: str
    recipient: str
    body: str
    html_content: Optional[str] = None

class TaskReminderRequest(BaseModel):
    task_id: str
    send_now: bool = False

class ClientReminderRequest(BaseModel):
    client_id: str
    send_now: bool = False

class NotificationResponse(BaseModel):
    success: bool
    message: str

@router.post("/email", response_model=NotificationResponse)
async def send_email(
    notification: EmailNotification,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Enviar email de notificação"""
    try:
        # Verificar se o usuário tem permissão para enviar emails
        if not current_user.is_admin and notification.recipient != current_user.email:
            raise HTTPException(status_code=403, detail="Sem permissão para enviar emails para outros usuários")
        
        # Enviar email em background para não bloquear a resposta
        background_tasks.add_task(
            NotificationService.send_email,
            recipient=notification.recipient,
            subject=notification.subject,
            body=notification.body,
            html_content=notification.html_content
        )
        
        return {
            "success": True,
            "message": f"Email agendado para envio para {notification.recipient}"
        }
    except Exception as e:
        logger.error(f"Erro ao enviar email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao enviar email: {str(e)}")

@router.post("/task-reminder", response_model=NotificationResponse)
async def send_task_reminder(
    reminder: TaskReminderRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Enviar lembrete de tarefa"""
    try:
        # Verificar se a tarefa existe e pertence ao usuário
        task = await TaskService.get_task_by_id(reminder.task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        
        if task.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Sem permissão para enviar lembrete para esta tarefa")
        
        if reminder.send_now:
            # Enviar imediatamente
            result = await NotificationService.send_task_reminder(reminder.task_id)
            
            if result:
                return {
                    "success": True,
                    "message": "Lembrete de tarefa enviado com sucesso"
                }
            else:
                return {
                    "success": False,
                    "message": "Falha ao enviar lembrete de tarefa"
                }
        else:
            # Agendar para envio em background
            background_tasks.add_task(
                NotificationService.send_task_reminder,
                task_id=reminder.task_id
            )
            
            return {
                "success": True,
                "message": "Lembrete de tarefa agendado para envio"
            }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao enviar lembrete de tarefa: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao enviar lembrete de tarefa: {str(e)}")

@router.post("/client-reminder", response_model=NotificationResponse)
async def send_client_reminder(
    reminder: ClientReminderRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Enviar lembrete de contato com cliente"""
    try:
        # Verificar se o cliente existe e pertence ao usuário
        client = await ClientService.get_client_by_id(reminder.client_id)
        
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        if client.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Sem permissão para enviar lembrete para este cliente")
        
        if reminder.send_now:
            # Enviar imediatamente
            result = await NotificationService.send_client_contact_reminder(reminder.client_id)
            
            if result:
                return {
                    "success": True,
                    "message": "Lembrete de contato com cliente enviado com sucesso"
                }
            else:
                return {
                    "success": False,
                    "message": "Falha ao enviar lembrete de contato com cliente"
                }
        else:
            # Agendar para envio em background
            background_tasks.add_task(
                NotificationService.send_client_contact_reminder,
                client_id=reminder.client_id
            )
            
            return {
                "success": True,
                "message": "Lembrete de contato com cliente agendado para envio"
            }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao enviar lembrete de contato com cliente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao enviar lembrete de contato com cliente: {str(e)}")

@router.post("/schedule-all-reminders", response_model=NotificationResponse)
async def schedule_all_reminders(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Agendar todos os lembretes (apenas para administradores)"""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Apenas administradores podem agendar todos os lembretes")
        
        # Agendar lembretes em background
        background_tasks.add_task(NotificationService.send_task_reminders)
        background_tasks.add_task(NotificationService.schedule_client_reminders)
        
        return {
            "success": True,
            "message": "Todos os lembretes foram agendados para envio"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao agendar lembretes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao agendar lembretes: {str(e)}")

@router.post("/test-email")
async def send_test_email(current_user: User = Depends(get_current_user)):
    """Enviar e-mail de teste para o usuário atual"""
    
    try:
        user_name = current_user.full_name if current_user.full_name else current_user.username
        email_content = f"<p>Olá {user_name},</p>"

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee;">
                    <div style="background-color: #4a6da7; color: white; padding: 10px; text-align: center;">
                        <h2>Email de Teste</h2>
                    </div>
                    <div style="padding: 20px;">
                        {email_content}
                        <p>Este é um email de teste do sistema ClientTracker.</p>
                        <p>Se você está recebendo este email, significa que o sistema de notificações está configurado corretamente.</p>
                    </div>
                    <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #777;">
                        <p>Este é um e-mail automático. Por favor, não responda.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        success = await notification_service.send_email(
            current_user.email,
            "ClientTracker - Email de Teste",
            html_content
        )
        
        if success:
            return {"message": "Email de teste enviado com sucesso!"}
        else:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Falha ao enviar email de teste")

    except Exception as e:
        logger.error(f"Erro ao enviar email de teste: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao enviar email de teste: {str(e)}"
        ) 