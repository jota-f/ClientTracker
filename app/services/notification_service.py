import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Union, Any
from bson import ObjectId

from app.core.database import Database
from app.models.user import User
from app.services.user_service import UserService
from app.services.client_service import ClientService
from app.services.rfm import calculate_rfm_score

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.user_service = UserService()
        self.client_service = ClientService()
        
        # Configurações de e-mail
        self.email_sender = os.environ.get("EMAIL_SENDER")
        self.email_password = os.environ.get("EMAIL_PASSWORD")
        self.smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", 587))
    
    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Enviar e-mail com conteúdo HTML"""
        if not self.email_sender or not self.email_password:
            logger.warning("Credenciais de e-mail não configuradas")
            return False
        
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.email_sender
            message["To"] = to_email
            
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.sendmail(self.email_sender, to_email, message.as_string())
            
            logger.info(f"Email enviado para {to_email}")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail: {e}")
            return False
    
    async def send_task_reminder(self, task_id: str) -> bool:
        """Enviar lembrete para uma tarefa específica"""
        try:
            task = await Database.database["tasks"].find_one({"_id": ObjectId(task_id)})
            
            if not task:
                logger.warning(f"Tarefa {task_id} não encontrada")
                return False
            
            user = await Database.database["users"].find_one({"_id": ObjectId(task["user_id"])})
            
            if not user:
                logger.warning(f"Usuário {task['user_id']} não encontrado")
                return False
            
            # Conteúdo simplificado do e-mail
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee;">
                        <div style="background-color: #4a6da7; color: white; padding: 10px; text-align: center;">
                            <h2>Lembrete de Tarefa</h2>
                        </div>
                        <div style="padding: 20px;">
                            <p>Olá {user.get('full_name', user.get('username', 'Usuário'))},</p>
                            <p>Este é um lembrete para a seguinte tarefa:</p>
                            <div style="margin: 20px 0; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #4a6da7;">
                                <p><strong>Título:</strong> {task.get('title')}</p>
                                <p><strong>Descrição:</strong> {task.get('description', 'Sem descrição')}</p>
                                <p><strong>Data de Vencimento:</strong> {task.get('due_date', 'Sem data definida')}</p>
                            </div>
                            <p>Acesse o ClientTracker para gerenciar suas tarefas.</p>
                        </div>
                        <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #777;">
                            <p>Este é um e-mail automático. Por favor, não responda.</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            return await self.send_email(
                user.get('email'),
                f"Lembrete: {task.get('title')}",
                html_content
            )
        except Exception as e:
            logger.error(f"Erro ao enviar lembrete de tarefa: {e}")
            return False
    
    async def send_client_contact_reminder(self, user_id: str, client_id: str) -> bool:
        """Enviar lembrete para contatar um cliente com base no RFM"""
        try:
            user = await Database.database["users"].find_one({"_id": ObjectId(user_id)})
            client = await Database.database["clients"].find_one({"_id": ObjectId(client_id)})
            
            if not user or not client:
                logger.warning(f"Usuário {user_id} ou cliente {client_id} não encontrado")
                return False
            
            # Obter o score RFM atual
            rfm_scores = client.get("rfm_scores", {})
            if not rfm_scores:
                # Se não tiver RFM, calcular agora
                last_contact = client.get("last_contact", datetime.now(timezone.utc) - timedelta(days=365))
                sales_potential = client.get("sales_potential", 1)
                interactions = client.get("interaction_history", [])
                
                rfm_scores = calculate_rfm_score(last_contact, sales_potential, interactions)
            
            total_score = rfm_scores.get("total", 0)
            
            # Determinar a prioridade com base no score
            priority_text = "Baixa"
            if total_score >= 9:
                priority_text = "Muito Alta"
            elif total_score >= 7:
                priority_text = "Alta"
            elif total_score >= 5:
                priority_text = "Média"
            
            # Incluir informações de frequência de contato
            contact_frequency = await self._get_contact_frequency(total_score)
            frequency_text = ""
            
            if contact_frequency <= 7:
                frequency_text = "semanal"
            elif contact_frequency <= 14:
                frequency_text = "quinzenal"
            elif contact_frequency <= 30:
                frequency_text = "mensal"
            else:
                frequency_text = "bimestral"
            
            # Conteúdo do e-mail com mais informações
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee;">
                        <div style="background-color: #4a6da7; color: white; padding: 10px; text-align: center;">
                            <h2>Lembrete de Contato com Cliente</h2>
                        </div>
                        <div style="padding: 20px;">
                            <p>Olá {user.get('full_name', user.get('username', 'Usuário'))},</p>
                            <p>É hora de entrar em contato com o seguinte cliente:</p>
                            <div style="margin: 20px 0; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #4a6da7;">
                                <p><strong>Nome:</strong> {client.get('name')}</p>
                                <p><strong>Empresa:</strong> {client.get('company', 'N/A')}</p>
                                <p><strong>Email:</strong> {client.get('email', 'N/A')}</p>
                                <p><strong>Telefone:</strong> {client.get('phone', 'N/A')}</p>
                                <p><strong>Último contato:</strong> {client.get('last_contact', 'Nunca').strftime('%d/%m/%Y') if isinstance(client.get('last_contact'), datetime) else 'Nunca'}</p>
                                <p><strong>Potencial de vendas:</strong> {client.get('sales_potential', 'N/A')}/5</p>
                                <p><strong>Score RFM total:</strong> {total_score}/15</p>
                                <p><strong>Prioridade:</strong> {priority_text}</p>
                                <p><strong>Frequência de contato recomendada:</strong> {frequency_text}</p>
                            </div>
                            <p>Acesse o ClientTracker para ver mais detalhes do cliente e registrar seu contato.</p>
                        </div>
                        <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #777;">
                            <p>Este é um e-mail automático. Por favor, não responda.</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            return await self.send_email(
                user.get('email'),
                f"Lembrete de contato: {client.get('name')} - {client.get('company', '')}",
                html_content
            )
        except Exception as e:
            logger.error(f"Erro ao enviar lembrete de contato: {e}")
            return False
    
    async def _get_contact_frequency(self, rfm_score: int) -> int:
        """Determinar a frequência de contato (em dias) com base no score RFM"""
        if rfm_score >= 9:  # Clientes VIP
            return 7  # Contato semanal
        elif rfm_score >= 7:  # Clientes importantes
            return 14  # Contato quinzenal
        elif rfm_score >= 5:  # Clientes regulares
            return 30  # Contato mensal
        else:  # Clientes ocasionais
            return 60  # Contato bimestral
    
    async def schedule_client_reminders(self) -> Dict[str, Any]:
        """Agendar lembretes para contatar clientes com base no RFM"""
        results = {
            "success": True,
            "processed": 0,
            "reminders_sent": 0,
            "errors": []
        }
        
        try:
            logger.info("Iniciando processamento de lembretes de clientes baseados em RFM")
            # Buscar todos os usuários
            users = await Database.database["users"].find().to_list(100)
            
            for user in users:
                user_id = str(user["_id"])
                # Buscar clientes do usuário
                clients = await Database.database["clients"].find({"user_id": user_id}).to_list(1000)
                
                for client in clients:
                    try:
                        results["processed"] += 1
                        client_id = str(client["_id"])
                        
                        # Verificar se o cliente tem RFM score
                        rfm_scores = client.get("rfm_scores", {})
                        if not rfm_scores:
                            # Se não tiver RFM, calcular agora
                            last_contact = client.get("last_contact", datetime.now(timezone.utc) - timedelta(days=365))
                            sales_potential = client.get("sales_potential", 1)
                            interactions = client.get("interaction_history", [])
                            
                            rfm_scores = calculate_rfm_score(last_contact, sales_potential, interactions)
                            
                            # Atualizar cliente com o score RFM calculado
                            await Database.database["clients"].update_one(
                                {"_id": ObjectId(client_id)},
                                {"$set": {"rfm_scores": rfm_scores}}
                            )
                        
                        rfm_score = rfm_scores.get("total", 0)
                        
                        # Calcular dias desde o último contato
                        last_contact = client.get("last_contact")
                        days_since_contact = 999  # Valor alto por padrão
                        
                        if last_contact:
                            last_contact_date = last_contact
                            days_since_contact = (datetime.now(timezone.utc) - last_contact_date).days
                        
                        # Definir frequência de contato com base no RFM
                        contact_frequency = await self._get_contact_frequency(rfm_score)
                        
                        logger.info(f"Cliente {client['name']} (ID: {client_id}) - Dias desde contato: {days_since_contact}, "
                                   f"Frequência recomendada: {contact_frequency} dias, Score RFM: {rfm_score}")
                        
                        # Se estiver na hora de fazer contato, enviar lembrete
                        if days_since_contact >= contact_frequency:
                            logger.info(f"Enviando lembrete para o cliente {client['name']} (ID: {client_id})")
                            reminder_sent = await self.send_client_contact_reminder(user_id, client_id)
                            
                            if reminder_sent:
                                results["reminders_sent"] += 1
                                logger.info(f"Lembrete enviado com sucesso para o cliente {client['name']}")
                            else:
                                error_msg = f"Falha ao enviar lembrete para o cliente {client['name']} (ID: {client_id})"
                                results["errors"].append(error_msg)
                                logger.warning(error_msg)
                    except Exception as client_error:
                        error_msg = f"Erro ao processar cliente {client.get('name', 'Desconhecido')} (ID: {client.get('_id', 'Desconhecido')}): {str(client_error)}"
                        results["errors"].append(error_msg)
                        logger.error(error_msg)
                        continue
                        
            logger.info(f"Processamento de lembretes concluído. Processados: {results['processed']}, "
                      f"Lembretes enviados: {results['reminders_sent']}, Erros: {len(results['errors'])}")
            return results
            
        except Exception as e:
            error_msg = f"Erro ao agendar lembretes de clientes: {str(e)}"
            logger.error(error_msg)
            results["success"] = False
            results["errors"].append(error_msg)
            return results

    async def check_upcoming_client_followups(self, days_ahead: int = 3) -> Dict[str, Any]:
        """Verifica clientes com próximo contato agendado nos próximos X dias e envia lembretes"""
        results = {
            "success": True,
            "processed": 0,
            "reminders_sent": 0,
            "errors": []
        }
        
        try:
            logger.info(f"Verificando clientes com contatos agendados para os próximos {days_ahead} dias")
            
            # Data atual e data limite
            now = datetime.now(timezone.utc)
            future_date = now + timedelta(days=days_ahead)
            
            # Buscar todos os usuários
            users = await Database.database["users"].find().to_list(100)
            
            for user in users:
                user_id = str(user["_id"])
                # Buscar clientes do usuário com next_followup nos próximos X dias
                clients = await Database.database["clients"].find({
                    "user_id": user_id,
                    "next_followup": {"$gte": now, "$lte": future_date}
                }).to_list(1000)
                
                for client in clients:
                    try:
                        results["processed"] += 1
                        client_id = str(client["_id"])
                        
                        # Formatar a data do próximo contato
                        next_followup = client.get("next_followup")
                        followup_date_str = next_followup.strftime("%d/%m/%Y") if next_followup else "N/A"
                        
                        # Conteúdo do e-mail
                        html_content = f"""
                        <html>
                            <body style="font-family: Arial, sans-serif;">
                                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee;">
                                    <div style="background-color: #4a6da7; color: white; padding: 10px; text-align: center;">
                                        <h2>Lembrete de Acompanhamento Agendado</h2>
                                    </div>
                                    <div style="padding: 20px;">
                                        <p>Olá {user.get('full_name', user.get('username', 'Usuário'))},</p>
                                        <p>Você tem um contato agendado com o cliente:</p>
                                        <div style="margin: 20px 0; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #4a6da7;">
                                            <p><strong>Nome:</strong> {client.get('name')}</p>
                                            <p><strong>Empresa:</strong> {client.get('company', 'N/A')}</p>
                                            <p><strong>Data agendada:</strong> {followup_date_str}</p>
                                        </div>
                                        <p>Acesse o ClientTracker para ver mais detalhes do cliente e preparar seu contato.</p>
                                    </div>
                                    <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #777;">
                                        <p>Este é um e-mail automático. Por favor, não responda.</p>
                                    </div>
                                </div>
                            </body>
                        </html>
                        """
                        
                        # Enviar o lembrete
                        reminder_sent = await self.send_email(
                            user.get('email'),
                            f"Acompanhamento Agendado: {client.get('name')} - {followup_date_str}",
                            html_content
                        )
                        
                        if reminder_sent:
                            results["reminders_sent"] += 1
                            logger.info(f"Lembrete de acompanhamento enviado para o cliente {client['name']}")
                        else:
                            error_msg = f"Falha ao enviar lembrete de acompanhamento para {client['name']}"
                            results["errors"].append(error_msg)
                            logger.warning(error_msg)
                            
                    except Exception as client_error:
                        error_msg = f"Erro ao processar lembrete de acompanhamento: {str(client_error)}"
                        results["errors"].append(error_msg)
                        logger.error(error_msg)
                        continue
            
            logger.info(f"Verificação de acompanhamentos concluída. Processados: {results['processed']}, "
                      f"Lembretes enviados: {results['reminders_sent']}, Erros: {len(results['errors'])}")
            return results
            
        except Exception as e:
            error_msg = f"Erro ao verificar acompanhamentos agendados: {str(e)}"
            logger.error(error_msg)
            results["success"] = False
            results["errors"].append(error_msg)
            return results

    @staticmethod
    async def send_task_reminders():
        """Enviar lembretes de tarefas pendentes"""
        try:
            # Obter tarefas pendentes
            now = datetime.now(timezone.utc)
            tasks = await Database.database["tasks"].find({
                "status": {"$ne": "completed"},
                "due_date": {"$lte": now + timedelta(days=1)}
            }).to_list(100)
            
            for task in tasks:
                # Obter usuário
                user = await UserService.get_user_by_id(task["user_id"])
                if not user or not user.email:
                    continue
                
                # Enviar lembrete
                notification_service = NotificationService()
                await notification_service.send_email(
                    to_email=user.email,
                    subject=f"Lembrete: Tarefa {task['title']} próxima do vencimento",
                    html_content=f"""
                    <h2>Lembrete de Tarefa</h2>
                    <p>A tarefa <strong>{task['title']}</strong> está próxima do vencimento.</p>
                    <p>Data de vencimento: {task['due_date'].strftime('%d/%m/%Y %H:%M')}</p>
                    <p>Status: {task['status']}</p>
                    <p>Prioridade: {task['priority']}</p>
                    """
                )
            
            logger.info(f"Lembretes de tarefas enviados: {len(tasks)} tarefas")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar lembretes de tarefas: {str(e)}")
            return False
    
    @staticmethod
    async def schedule_client_reminders():
        """Agendar lembretes de contato com clientes"""
        try:
            # Obter clientes que precisam de contato
            now = datetime.now(timezone.utc)
            clients = await Database.database["clients"].find({
                "next_followup": {"$lte": now + timedelta(days=1)}
            }).to_list(100)
            
            for client in clients:
                # Obter usuário
                user = await UserService.get_user_by_id(client["user_id"])
                if not user or not user.email:
                    continue
                
                # Enviar lembrete
                notification_service = NotificationService()
                await notification_service.send_email(
                    to_email=user.email,
                    subject=f"Lembrete: Contato com cliente {client['name']}",
                    html_content=f"""
                    <h2>Lembrete de Contato com Cliente</h2>
                    <p>É hora de entrar em contato com <strong>{client['name']}</strong> ({client['company']}).</p>
                    <p>Data agendada: {client['next_followup'].strftime('%d/%m/%Y %H:%M')}</p>
                    <p>Email: {client['email']}</p>
                    <p>Telefone: {client['phone']}</p>
                    """
                )
            
            logger.info(f"Lembretes de clientes enviados: {len(clients)} clientes")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar lembretes de clientes: {str(e)}")
            return False 