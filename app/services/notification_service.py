import asyncio
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
from app.services.rfm import calculate_rfm_score
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    # Circuit breaker global para evitar travamento se a porta SMTP estiver bloqueada na nuvem
    _smtp_reachable: bool = True
    _last_failure_time: Optional[datetime] = None

    def __init__(self):
        self.user_service = UserService()
        
        # Configurações de e-mail do settings
        self.email_sender = settings.MAIL_USERNAME
        self.email_password = settings.MAIL_PASSWORD
        self.smtp_server = settings.MAIL_SERVER
        self.smtp_port = settings.MAIL_PORT
        self.use_tls = settings.MAIL_TLS

        # Log das configurações (ocultando a senha)
        logger.info(f"Inicializando NotificationService com:")
        logger.info(f"- SMTP Server: {self.smtp_server}")
        logger.info(f"- SMTP Port: {self.smtp_port}")
        logger.info(f"- Sender: {self.email_sender}")
        logger.info(f"- Password: {'*' * 8 if self.email_password else 'Não configurado'}")
        logger.info(f"- TLS: {self.use_tls}")

        # Validar configurações
        if not all([self.email_sender, self.email_password, self.smtp_server, self.smtp_port]):
            missing = []
            if not self.email_sender: missing.append("MAIL_USERNAME")
            if not self.email_password: missing.append("MAIL_PASSWORD")
            if not self.smtp_server: missing.append("MAIL_SERVER")
            if not self.smtp_port: missing.append("MAIL_PORT")
            logger.error(f"Configurações de email incompletas. Faltando: {', '.join(missing)}")

    def _send_email_sync(self, to_email: str, subject: str, html_content: str) -> bool:
        """Execução síncrona do envio de e-mail com timeout estrito de 4s em thread isolada."""
        now = datetime.now(timezone.utc)
        # Se a rede foi marcada como inacessível nos últimos 15 minutos, não trava a aplicação
        if not NotificationService._smtp_reachable and NotificationService._last_failure_time:
            if (now - NotificationService._last_failure_time).total_seconds() < 900:
                logger.debug("SMTP circuit-breaker ativo: ignorando tentativa de envio enquanto a rede estiver inalcançável.")
                return False
            else:
                NotificationService._smtp_reachable = True

        msg = MIMEMultipart()
        msg['From'] = self.email_sender
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        try:
            # Timeout curto de 4s: evita congelar a máquina caso portas SMTP estejam bloqueadas pelo provedor
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=4.0) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
                logger.info(f"Email enviado com sucesso para {to_email}")
                NotificationService._smtp_reachable = True
                return True
        except (OSError, smtplib.SMTPException, TimeoutError) as net_err:
            err_str = str(net_err)
            if "Network is unreachable" in err_str or "101" in err_str or "timed out" in err_str:
                logger.warning(f"SMTP inacessível no ambiente atual (porta {self.smtp_port} bloqueada ou sem rota): {err_str}. Circuit breaker ativado.")
                NotificationService._smtp_reachable = False
                NotificationService._last_failure_time = now
            else:
                logger.error(f"Erro ao enviar e-mail via SMTP: {err_str}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado no envio de e-mail: {str(e)}")
            return False

    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Enviar e-mail de forma assíncrona sem travar o event loop do FastAPI."""
        if not all([self.email_sender, self.email_password, self.smtp_server, self.smtp_port]):
            logger.error("Configurações de email incompletas")
            return False

        # Roda em thread separada com asyncio.to_thread para manter o servidor web 100% responsivo
        return await asyncio.to_thread(self._send_email_sync, to_email, subject, html_content)
    
    async def send_task_reminder(self, task_id: str) -> bool:
        """Enviar lembrete para uma tarefa específica"""
        try:
            task = await Database.database["tasks"].find_one({"_id": ObjectId(task_id)})
            
            if not task:
                logger.warning(f"Tarefa {task_id} não encontrada")
                return False
            
            user = await self.user_service.get_user_by_id(task["user_id"])
            
            if not user:
                logger.warning(f"Usuário {task['user_id']} não encontrado")
                return False
                
            # Verificar configurações de notificação
            if not user.notification_settings.task_reminders:
                logger.info(f"Notificações de tarefas desativadas para o usuário {user.email}")
                return False
                
            if user.notification_preference == "none":
                logger.info(f"Usuário {user.email} optou por não receber notificações")
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
                            <p>Olá {user.full_name or user.username or 'Usuário'},</p>
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
                user.email,
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
                
            # Verificar configurações de notificação
            user_obj = User.parse_obj(user)
            if not user_obj.notification_settings.rfm_reminders:
                logger.info(f"Notificações RFM desativadas para o usuário {user_obj.email}")
                return False
                
            if user_obj.notification_preference == "none":
                logger.info(f"Usuário {user_obj.email} optou por não receber notificações")
                return False
            
            # Obter o score RFM atual
            rfm_scores = client.get("rfm_scores", {})
            if not rfm_scores:
                # Se não tiver RFM, calcular agora
                last_contact = client.get("last_contact", datetime.now(timezone.utc) - timedelta(days=365))
                # Garantir que last_contact seja timezone-aware
                if last_contact.tzinfo is None:
                    last_contact = last_contact.replace(tzinfo=timezone.utc)
                    
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
            frequency_text = await self._get_contact_frequency(total_score)
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #2c3e50;">Lembrete de Contato</h2>
                        <p>Olá {user.get('name', 'Usuário')},</p>
                        <p>Este é um lembrete para entrar em contato com o cliente:</p>
                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <p><strong>Cliente:</strong> {client.get('name')} - {client.get('company', '')}</p>
                            <p><strong>Prioridade:</strong> {priority_text}</p>
                            <p><strong>Frequência de contato recomendada:</strong> {frequency_text}</p>
                        </div>
                        <p>Acesse o ClientTracker para ver mais detalhes do cliente e registrar seu contato.</p>
                    </div>
                    <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #777;">
                        <p>Este é um e-mail automático. Por favor, não responda.</p>
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
            logger.error(f"Erro ao enviar lembrete de contato: {str(e)}")
            return False
    
    async def _get_contact_frequency(self, rfm_score: int) -> str:
        """Determinar a frequência de contato (em texto) com base no score RFM"""
        if rfm_score >= 9:  # Clientes VIP
            return "Contato semanal"
        elif rfm_score >= 7:  # Clientes importantes
            return "Contato quinzenal"
        elif rfm_score >= 5:  # Clientes regulares
            return "Contato mensal"
        else:  # Clientes ocasionais
            return "Contato bimestral"
    
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
                            # Garantir que last_contact seja timezone-aware
                            if last_contact.tzinfo is None:
                                last_contact = last_contact.replace(tzinfo=timezone.utc)
                                
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
                            # Garantir que last_contact seja timezone-aware
                            if last_contact.tzinfo is None:
                                last_contact = last_contact.replace(tzinfo=timezone.utc)
                            days_since_contact = (datetime.now(timezone.utc) - last_contact).days
                        
                        # Definir frequência de contato com base no RFM
                        if rfm_score >= 9:  # VIP - contato semanal
                            if days_since_contact >= 7:
                                await self.send_client_contact_reminder(user_id, client_id)
                                results["reminders_sent"] += 1
                        elif rfm_score >= 7:  # Importante - contato quinzenal
                            if days_since_contact >= 14:
                                await self.send_client_contact_reminder(user_id, client_id)
                                results["reminders_sent"] += 1
                        elif rfm_score >= 5:  # Regular - contato mensal
                            if days_since_contact >= 30:
                                await self.send_client_contact_reminder(user_id, client_id)
                                results["reminders_sent"] += 1
                        else:  # Ocasional - contato bimestral
                            if days_since_contact >= 60:
                                await self.send_client_contact_reminder(user_id, client_id)
                                results["reminders_sent"] += 1
                                
                    except Exception as e:
                        error_msg = f"Erro ao processar cliente {client_id}: {str(e)}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
            
            return results
        except Exception as e:
            error_msg = f"Erro ao processar lembretes: {str(e)}"
            logger.error(error_msg)
            results["success"] = False
            results["errors"].append(error_msg)
            return results

    async def check_upcoming_client_followups(self, days_ahead: int = 3) -> Dict[str, Any]:
        """Verifica clientes com próximo contato agendado nos próximos X dias e envia lembretes"""
        results = {
            "processed": 0,
            "sent": 0,
            "errors": []
        }
        
        try:
            logger.info(f"Verificando clientes com contatos agendados para os próximos {days_ahead} dias")
            
            # Data atual e data limite
            now = datetime.now(timezone.utc)
            future_date = now + timedelta(days=days_ahead)
            
            # Buscar todos os usuários com notificações de follow-up ativas
            users = await Database.database["users"].find({
                "notification_settings.followup_reminders": True,
                "notification_preference": {"$ne": "none"}
            }).to_list(100)
            
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
                        if await self.send_email(
                            user.get('email'),
                            f"Acompanhamento Agendado: {client.get('name')} - {followup_date_str}",
                            html_content
                        ):
                            results["sent"] += 1
                            logger.info(f"Lembrete de acompanhamento enviado para o cliente {client['name']}")
                        else:
                            error_msg = f"Falha ao enviar lembrete de acompanhamento para {client['name']}"
                            results["errors"].append(error_msg)
                            logger.warning(error_msg)
                            
                    except Exception as e:
                        error_msg = f"Erro ao processar lembrete de acompanhamento: {str(e)}"
                        results["errors"].append(error_msg)
                        logger.error(error_msg)
                        continue
            
            logger.info(f"Verificação de acompanhamentos concluída. Processados: {results['processed']}, "
                      f"Lembretes enviados: {results['sent']}, Erros: {len(results['errors'])}")
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

    async def process_all_notifications(self) -> Dict[str, Any]:
        """
        Processa todos os tipos de notificações:
        - Lembretes de contato baseados em RFM
        - Follow-ups agendados
        - Tarefas pendentes
        """
        results = {
            "success": True,
            "rfm_reminders": {"processed": 0, "sent": 0, "errors": []},
            "followup_reminders": {"processed": 0, "sent": 0, "errors": []},
            "task_reminders": {"processed": 0, "sent": 0, "errors": []}
        }

        try:
            # 1. Processar lembretes baseados em RFM
            rfm_results = await self.process_rfm_reminders()
            results["rfm_reminders"]["processed"] = rfm_results["processed"]
            results["rfm_reminders"]["sent"] = rfm_results["sent"]
            results["rfm_reminders"]["errors"].extend(rfm_results["errors"])

            # 2. Processar follow-ups agendados
            followup_results = await self.check_upcoming_client_followups()
            results["followup_reminders"]["processed"] = followup_results["processed"]
            results["followup_reminders"]["sent"] = followup_results["sent"]
            results["followup_reminders"]["errors"].extend(followup_results["errors"])

            # 3. Processar tarefas pendentes
            task_results = await self.process_task_reminders()
            results["task_reminders"]["processed"] = task_results["processed"]
            results["task_reminders"]["sent"] = task_results["sent"]
            results["task_reminders"]["errors"].extend(task_results["errors"])

            logger.info(f"Processamento de notificações concluído: {results}")
            return results

        except Exception as e:
            error_msg = f"Erro ao processar notificações: {str(e)}"
            logger.error(error_msg)
            results["success"] = False
            for reminder_type in ["rfm_reminders", "followup_reminders", "task_reminders"]:
                results[reminder_type]["errors"].append(error_msg)
            return results

    async def process_rfm_reminders(self) -> Dict[str, Any]:
        """Processa lembretes baseados no RFM"""
        results = {
            "processed": 0,
            "sent": 0,
            "errors": []
        }

        try:
            # Buscar usuários com notificações RFM ativas
            users = await Database.database["users"].find({
                "notification_settings.rfm_reminders": True
            }).to_list(100)

            for user in users:
                user_id = str(user["_id"])
                clients = await Database.database["clients"].find({
                    "user_id": user_id
                }).to_list(1000)

                results["processed"] += len(clients)
                
                for client in clients:
                    try:
                        client_id = str(client["_id"])
                        
                        # Calcular score RFM e dias desde último contato
                        last_contact = client.get("last_contact", datetime.now(timezone.utc) - timedelta(days=365))
                        # Garantir que last_contact seja timezone-aware
                        if last_contact.tzinfo is None:
                            last_contact = last_contact.replace(tzinfo=timezone.utc)
                            
                        sales_potential = client.get("sales_potential", 1)
                        interactions = client.get("interaction_history", [])
                        
                        rfm_scores = calculate_rfm_score(last_contact, sales_potential, interactions)
                        total_score = rfm_scores.get("total", 0)
                        
                        # Garantir que last_contact seja timezone-aware novamente para o cálculo de dias
                        last_contact = client.get("last_contact")
                        if last_contact:
                            if last_contact.tzinfo is None:
                                last_contact = last_contact.replace(tzinfo=timezone.utc)
                            days_since_contact = (datetime.now(timezone.utc) - last_contact).days
                        else:
                            days_since_contact = float('inf')
                        
                        needs_contact = False
                        
                        # Definir regras de contato baseadas no score RFM
                        if total_score >= 7 and days_since_contact >= 14:  # Importante
                            needs_contact = True
                        elif total_score >= 5 and days_since_contact >= 30:  # Regular
                            needs_contact = True
                        elif days_since_contact >= 60:  # Ocasional
                            needs_contact = True

                        if needs_contact:
                            if await self.send_client_contact_reminder(user_id, client_id):
                                results["sent"] += 1

                    except Exception as e:
                        error_msg = f"Erro ao processar cliente {client_id}: {str(e)}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)

            return results

        except Exception as e:
            error_msg = f"Erro ao processar lembretes RFM: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            return results

    async def process_task_reminders(self) -> Dict[str, Any]:
        """Processa lembretes de tarefas pendentes"""
        results = {
            "processed": 0,
            "sent": 0,
            "errors": []
        }

        try:
            # Buscar usuários com notificações de tarefas ativas
            users = await Database.database["users"].find({
                "notification_settings.task_reminders": True
            }).to_list(100)

            for user in users:
                user_id = str(user["_id"])
                now = datetime.now(timezone.utc)
                tomorrow = now + timedelta(days=1)

                # Buscar tarefas próximas do vencimento para este usuário
                tasks = await Database.database["tasks"].find({
                    "user_id": user_id,
                    "status": {"$ne": "DONE"},
                    "due_date": {"$lte": tomorrow}
                }).to_list(100)

                results["processed"] += len(tasks)

                for task in tasks:
                    try:
                        if await self.send_task_reminder(str(task["_id"])):
                            results["sent"] += 1
                    except Exception as e:
                        error_msg = f"Erro ao processar tarefa {task['_id']}: {str(e)}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)

            return results

        except Exception as e:
            error_msg = f"Erro ao processar lembretes de tarefas: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            return results 