#!/usr/bin/env python3
import os
import sys
import asyncio 
import logging
import copy

# Ajustar PYTHONPATH para encontrar os módulos da aplicação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.notification_service import NotificationService 
from app.models.user import User, NotificationSettings
from app.core.database import Database 
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_notifications(): 
    # Verificar ambiente para evitar execução em produção
    if settings.ENVIRONMENT != "development":
        logger.error("⚠️ Este script de teste não deve ser executado em ambiente de produção!")
        logger.error("Configure o ambiente como 'development' no arquivo .env para executar este teste.")
        return
    
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
    
    # Criar um objeto User a partir do dicionário
    user = User.model_validate(user_dict)
    
    # Log das configurações de notificação
    logger.info(f"Usuário encontrado: {user.email}")
    logger.info(f"Configurações de notificação: {user.notification_settings.model_dump()}")
    logger.info(f"Preferência de notificação: {user.notification_preference}")
    
    # Verificar as configurações individuais
    logger.info(f"RFM Reminders: {'Habilitado' if user.notification_settings.rfm_reminders else 'Desabilitado'}")
    logger.info(f"Task Reminders: {'Habilitado' if user.notification_settings.task_reminders else 'Desabilitado'}")
    logger.info(f"Followup Reminders: {'Habilitado' if user.notification_settings.followup_reminders else 'Desabilitado'}")
    logger.info(f"O usuário receberá notificações como: {user.notification_preference}")
    
    # Verificar se as notificações seriam enviadas
    notification_service = NotificationService()
    
    # Verifica se enviaria notificação de tarefa
    would_send_task = user.notification_settings.task_reminders and user.notification_preference != "none"
    logger.info(f"Enviaria notificação de tarefa? {would_send_task}")
    
    # Verifica se enviaria notificação RFM
    would_send_rfm = user.notification_settings.rfm_reminders and user.notification_preference != "none"
    logger.info(f"Enviaria notificação RFM? {would_send_rfm}")
    
    # Verificação real usando a lógica das funções do serviço
    logger.info(f"\nSimulando verificação real dos serviços:")
    
    # Verificações manuais baseadas na lógica interna do serviço
    def should_send_notification(user_obj, setting_name):
        """Simulação da lógica interna do serviço para decidir enviar notificação"""
        # Verificar se o tipo específico de notificação está ativado
        if not getattr(user_obj.notification_settings, setting_name, False):
            return False
        
        # Verificar se o usuário quer receber notificações em geral
        if user_obj.notification_preference == "none":
            return False
            
        return True
    
    # Teste da lógica interna do serviço para RFM
    would_send_rfm_service = should_send_notification(user, "rfm_reminders")
    logger.info(f"RFM lógica do serviço diz que enviaria? {would_send_rfm_service}")
    
    # Teste da lógica interna do serviço para Tarefas
    would_send_task_service = should_send_notification(user, "task_reminders")
    logger.info(f"Task lógica do serviço diz que enviaria? {would_send_task_service}")
    
    # Testes com configurações diferentes
    logger.info(f"\n🧪 TESTES COM CONFIGURAÇÕES MODIFICADAS:")
    
    # Teste 1: Desabilitar RFM
    test_user = copy.deepcopy(user)
    test_user.notification_settings.rfm_reminders = False
    test_user.notification_settings.task_reminders = True
    test_user.notification_preference = "email"
    
    would_send_rfm_1 = should_send_notification(test_user, "rfm_reminders")
    logger.info(f"Teste 1 - RFM desabilitado, enviaria notificação? {would_send_rfm_1}")
    
    # Teste 2: Desabilitar Task
    test_user = copy.deepcopy(user)
    test_user.notification_settings.rfm_reminders = True
    test_user.notification_settings.task_reminders = False
    test_user.notification_preference = "email"
    
    would_send_task_2 = should_send_notification(test_user, "task_reminders")
    logger.info(f"Teste 2 - Task desabilitado, enviaria notificação? {would_send_task_2}")
    
    # Teste 3: Preferência none
    test_user = copy.deepcopy(user)
    test_user.notification_settings.rfm_reminders = True
    test_user.notification_settings.task_reminders = True
    test_user.notification_preference = "none"
    
    would_send_rfm_3 = should_send_notification(test_user, "rfm_reminders")
    would_send_task_3 = should_send_notification(test_user, "task_reminders")
    logger.info(f"Teste 3 - Preferência 'none', enviaria notificação RFM? {would_send_rfm_3}")
    logger.info(f"Teste 3 - Preferência 'none', enviaria notificação Task? {would_send_task_3}")
    
    # Teste 4: Todas notificações específicas desligadas
    test_user = copy.deepcopy(user)
    test_user.notification_settings.rfm_reminders = False
    test_user.notification_settings.task_reminders = False
    test_user.notification_settings.followup_reminders = False
    test_user.notification_preference = "email"
    
    would_send_rfm_4 = should_send_notification(test_user, "rfm_reminders")
    would_send_task_4 = should_send_notification(test_user, "task_reminders")
    
    logger.info(f"Teste 4 - Notificações específicas desligadas, enviaria notificação RFM? {would_send_rfm_4}")
    logger.info(f"Teste 4 - Notificações específicas desligadas, enviaria notificação Task? {would_send_task_4}")
    
    # Fechar conexão com o banco
    client.close()
    
    logger.info(f"\nTeste concluído! ✅")

if __name__ == "__main__":
    # Verificar argumentos para requisito de confirmação
    force_run = False
    for arg in sys.argv:
        if arg == "--force":
            force_run = True
    
    # Verifica se o usuário está ciente de que este é um teste
    if not force_run:
        print("\n⚠️  AVISO: Este script é um teste e acessa diretamente o banco de dados.")
        print("Não é recomendado executá-lo em ambiente de produção.")
        print("Use apenas para diagnóstico em ambiente de desenvolvimento.")
        
        confirmation = input("\nDeseja continuar? (s/N): ")
        if confirmation.lower() != 's':
            print("Teste cancelado pelo usuário.")
            sys.exit(0)
    
    # Executar teste
    asyncio.run(test_notifications()) 