import asyncio
import schedule
from datetime import datetime, timedelta
import time
import threading
from bson import ObjectId

# Ajuste as importações para corresponder à estrutura do seu projeto
from app.core.database import Database
from app.services.notification_service import NotificationService

notification_service = NotificationService()

async def send_task_reminders():
    """Enviar lembretes para tarefas próximas do vencimento"""
    tasks_collection = Database.database["tasks"]
    
    # Buscar tarefas que vencem em 1 dia e ainda não foram notificadas
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    tasks = await tasks_collection.find({
        "due_date": tomorrow,
        "reminder_sent": {"$ne": True}
    }).to_list(length=100)
    
    for task in tasks:
        success = await notification_service.send_task_reminder(task["_id"])
        if success:
            await tasks_collection.update_one(
                {"_id": ObjectId(task["_id"])},
                {"$set": {"reminder_sent": True}}
            )

async def schedule_client_contacts():
    """Agendar contatos com clientes com base no RFM"""
    await notification_service.schedule_client_reminders()

async def run_scheduler():
    """Iniciar agendador de tarefas"""
    schedule.every().day.at("08:00").do(send_task_reminders)
    schedule.every().monday.at("09:00").do(schedule_client_contacts)
    
    while True:
        await schedule.run_pending()
        await asyncio.sleep(60)  # Verificar a cada minuto

def start_scheduler():
    """Iniciar agendador em um thread separado"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_scheduler()) 