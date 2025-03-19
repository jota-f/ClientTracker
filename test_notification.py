#!/usr/bin/env python3
from app.services.notification_service import NotificationService 
from app.models.user import User, NotificationSettings
from app.core.database import Database 
import asyncio 
import logging
import copy
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_notifications(): 
    logger.info("Iniciando teste de notificações")
    
    # Conectar ao banco de dados manualmente
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client.get_database()
    
    # Buscar um usuário com configurações de notificação
    user_dict = await db.users.find_one({'notification_settings': {'$exists': True}})
    
    if not user_dict:
        logger.error("Nenhum usuário com configurações de notificação encontrado")
        return
    
    # Converter o ObjectId para string
    user_dict["_id"] = str(user_dict["_id"])
    
    logger.info(f"Usuário encontrado: {user_dict.get('username', 'N/A')}")
    logger.info(f"Configurações de notificação: {user_dict.get('notification_settings', {})}")
    logger.info(f"Preferência de notificação: {user_dict.get('notification_preference', 'não definida')}")
    
    # Verificar configurações de notificação
    if user_dict.get('notification_settings', {}).get('rfm_reminders', False):
        logger.info("RFM Reminders: Habilitado")
    else:
        logger.info("RFM Reminders: Desabilitado")
        
    if user_dict.get('notification_settings', {}).get('task_reminders', False):
        logger.info("Task Reminders: Habilitado")
    else:
        logger.info("Task Reminders: Desabilitado")
    
    if user_dict.get('notification_settings', {}).get('followup_reminders', False):
        logger.info("Followup Reminders: Habilitado")
    else:
        logger.info("Followup Reminders: Desabilitado")
    
    # Verificar se receberia notificações
    if user_dict.get('notification_preference') in ['email', 'in_app', 'both']:
        logger.info(f"O usuário receberá notificações como: {user_dict.get('notification_preference')}")
    else:
        logger.info("O usuário não receberá notificações (notification_preference=none ou não definido)")
    
    # Criar instância do modelo de usuário
    user = User.model_validate(user_dict)
    
    # Testar serviço de notificações
    notification_service = NotificationService()
    
    # Simular verificação de envio de notificação de tarefa
    would_send_task = (user.notification_settings.task_reminders and 
                      user.notification_preference != 'none')
    logger.info(f"Enviaria notificação de tarefa? {would_send_task}")
    
    # Simular verificação de envio de notificação RFM
    would_send_rfm = (user.notification_settings.rfm_reminders and 
                     user.notification_preference != 'none')
    logger.info(f"Enviaria notificação RFM? {would_send_rfm}")
    
    # Verificar a lógica real do serviço de notificação
    logger.info("\nSimulando verificação real dos serviços:")
    
    # RFM Reminders
    rfm_would_be_sent = await simulation_for_rfm_notification(user, notification_service)
    logger.info(f"RFM lógica do serviço diz que enviaria? {rfm_would_be_sent}")
    
    # Task Reminders
    task_would_be_sent = await simulation_for_task_notification(user, notification_service)
    logger.info(f"Task lógica do serviço diz que enviaria? {task_would_be_sent}")
    
    # Testes com modificações nas configurações
    logger.info("\n🧪 TESTES COM CONFIGURAÇÕES MODIFICADAS:")
    
    # Teste 1: Desabilitar RFM reminders
    test_user = copy.deepcopy(user)
    test_user.notification_settings.rfm_reminders = False
    rfm_result = await simulation_for_rfm_notification(test_user, notification_service)
    logger.info(f"Teste 1 - RFM desabilitado, enviaria notificação? {rfm_result}")
    
    # Teste 2: Desabilitar Task reminders
    test_user = copy.deepcopy(user)
    test_user.notification_settings.task_reminders = False
    task_result = await simulation_for_task_notification(test_user, notification_service)
    logger.info(f"Teste 2 - Task desabilitado, enviaria notificação? {task_result}")
    
    # Teste 3: Preferência de notificação 'none'
    test_user = copy.deepcopy(user)
    test_user.notification_preference = 'none'
    rfm_result = await simulation_for_rfm_notification(test_user, notification_service)
    task_result = await simulation_for_task_notification(test_user, notification_service)
    logger.info(f"Teste 3 - Preferência 'none', enviaria notificação RFM? {rfm_result}")
    logger.info(f"Teste 3 - Preferência 'none', enviaria notificação Task? {task_result}")
    
    # Teste 4: Tudo habilitado, mas notificações específicas desligadas
    test_user = copy.deepcopy(user)
    test_user.notification_preference = 'both'
    test_user.notification_settings = NotificationSettings(
        rfm_reminders=False,
        task_reminders=False,
        followup_reminders=False
    )
    rfm_result = await simulation_for_rfm_notification(test_user, notification_service)
    task_result = await simulation_for_task_notification(test_user, notification_service)
    logger.info(f"Teste 4 - Notificações específicas desligadas, enviaria notificação RFM? {rfm_result}")
    logger.info(f"Teste 4 - Notificações específicas desligadas, enviaria notificação Task? {task_result}")
    
    # Fechar conexão
    client.close()
    logger.info("\nTeste concluído! ✅")

async def simulation_for_rfm_notification(user, notification_service):
    """Simula a lógica de verificação de envio de notificação RFM"""
    # Extrai diretamente a lógica do método send_client_contact_reminder
    would_send = (user.notification_settings.rfm_reminders and 
                 user.notification_preference != 'none')
    return would_send

async def simulation_for_task_notification(user, notification_service):
    """Simula a lógica de verificação de envio de notificação de tarefa"""
    # Extrai diretamente a lógica do método send_task_reminder
    would_send = (user.notification_settings.task_reminders and 
                 user.notification_preference != 'none')
    return would_send

if __name__ == "__main__":
    asyncio.run(test_notifications()) 