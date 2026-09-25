from datetime import datetime, timezone
from app.services.notification_service import NotificationService
import logging
import asyncio

logger = logging.getLogger(__name__)

async def process_notifications():
    """
    Job para processar todos os tipos de notificações
    """
    try:
        logger.info("Iniciando processamento de notificações")
        notification_service = NotificationService()
        results = await notification_service.process_all_notifications()
        
        # Log dos resultados
        logger.info("Resultados do processamento de notificações:")
        
        # RFM Reminders
        rfm_processed = results.get("rfm_reminders", {}).get("processed", 0)
        rfm_sent = results.get("rfm_reminders", {}).get("sent", 0)
        logger.info(f"RFM: {rfm_sent}/{rfm_processed} enviados")
        
        # Follow-up Reminders
        followup_processed = results.get("followup_reminders", {}).get("processed", 0)
        followup_sent = results.get("followup_reminders", {}).get("sent", 0)
        logger.info(f"Follow-ups: {followup_sent}/{followup_processed} enviados")
        
        # Task Reminders
        task_processed = results.get("task_reminders", {}).get("processed", 0)
        task_sent = results.get("task_reminders", {}).get("sent", 0)
        logger.info(f"Tarefas: {task_sent}/{task_processed} enviados")
        
        # Log de erros
        if results.get("errors"):
            logger.warning(f"Erros encontrados: {len(results['errors'])}")
            for error in results["errors"]:
                logger.error(error)
                
        # Log de erros específicos de cada tipo
        for reminder_type in ["rfm_reminders", "followup_reminders", "task_reminders"]:
            if results.get(reminder_type, {}).get("errors"):
                logger.warning(f"Erros em {reminder_type}: {len(results[reminder_type]['errors'])}")
                for error in results[reminder_type]["errors"]:
                    logger.error(error)
    
    except Exception as e:
        logger.error(f"Erro ao processar notificações: {str(e)}")

async def start_notification_job():
    """
    Inicia o job de processamento de notificações em segundo plano.
    Executa a cada 1 hora com delay inicial para não competir com a inicialização web.
    """
    # Aguarda 30 segundos após o boot para que a aplicação responda a requisições imediatamente
    await asyncio.sleep(30)
    while True:
        await process_notifications()
        await asyncio.sleep(60 * 60)  # 1 hora 