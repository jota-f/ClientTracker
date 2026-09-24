from fastapi import APIRouter, Depends, HTTPException, Body
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_400_BAD_REQUEST
from typing import Dict, List, Optional
import json

from app.services.auth_service import get_current_user
from app.services.notification_service import NotificationService
from app.models.user import User

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

notification_service = NotificationService()

@router.post("/send-test")
async def send_test_email(
    current_user: User = Depends(get_current_user)
):
    """Enviar e-mail de teste para o usuário atual"""
    html_content = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4a6da7; color: white; padding: 10px 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #777; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>E-mail de Teste</h2>
                </div>
                <div class="content">
                    <p>Olá {current_user.name},</p>
                    <p>Este é um e-mail de teste do ClientTracker.</p>
                    <p>Se você está recebendo esta mensagem, significa que o sistema de notificações está configurado corretamente.</p>
                </div>
                <div class="footer">
                    <p>ClientTracker - Gerenciamento de Clientes e Tarefas</p>
                </div>
            </div>
        </body>
    </html>
    """
    
    success = await notification_service.send_email(
        current_user.email,
        "ClientTracker - E-mail de Teste",
        html_content
    )
    
    if success:
        return {"message": "E-mail enviado com sucesso!"}
    else:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Falha ao enviar e-mail")

@router.post("/task-reminder/{task_id}")
async def send_task_reminder(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Enviar lembrete manual para uma tarefa"""
    success = await notification_service.send_task_reminder(task_id)
    
    if success:
        return {"message": "Lembrete enviado com sucesso!"}
    else:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Falha ao enviar lembrete")

@router.post("/client-reminder/{client_id}")
async def send_client_reminder(
    client_id: str,
    current_user: User = Depends(get_current_user)
):
    """Enviar lembrete manual para contatar um cliente"""
    success = await notification_service.send_client_contact_reminder(current_user.id, client_id)
    
    if success:
        return {"message": "Lembrete enviado com sucesso!"}
    else:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Falha ao enviar lembrete") 