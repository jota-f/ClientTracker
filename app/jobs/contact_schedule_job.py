from datetime import datetime, timezone
from app.services.contact_schedule_service import ContactScheduleService
import logging
import asyncio

logger = logging.getLogger(__name__)

async def process_contact_schedules():
    """
    Job para processar e atualizar as datas de contato dos clientes
    baseado em seus scores RFM
    """
    try:
        logger.info("Iniciando processamento de agendamentos de contato")
        results = await ContactScheduleService.process_all_clients()
        logger.info(f"Processamento concluído: {results}")
    except Exception as e:
        logger.error(f"Erro ao processar agendamentos de contato: {str(e)}")

async def start_contact_schedule_job():
    """
    Inicia o job de processamento de agendamentos de contato
    Executa a cada 24 horas
    """
    while True:
        await process_contact_schedules()
        await asyncio.sleep(24 * 60 * 60)  # 24 horas 