from datetime import datetime, timezone
from app.core.database import Database
from app.models.client import Client
import logging

logger = logging.getLogger(__name__)

class DashboardService:
    @staticmethod
    async def get_dashboard_metrics(user_id: str = None):
        """
        Retorna as métricas para o dashboard:
        - Total de clientes
        - Clientes prioritários (RFM >= 10)
        - Follow-ups pendentes
        
        Se user_id for fornecido, considera apenas os clientes desse usuário.
        """
        now = datetime.now(timezone.utc)
        
        # Filtro base
        base_filter = {}
        
        # Adicionar filtro de usuário se fornecido
        if user_id:
            base_filter["user_id"] = user_id
            logger.info(f"Filtrando métricas do dashboard por user_id: {user_id}")
        
        # Total de clientes
        total_clients = await Database.database["clients"].count_documents(base_filter)
        
        # Clientes prioritários (RFM >= 10)
        priority_filter = base_filter.copy()
        priority_filter["rfm_scores.total"] = {"$gte": 10}
        priority_clients = await Database.database["clients"].count_documents(priority_filter)
        
        # Follow-ups pendentes
        followup_filter = base_filter.copy()
        followup_filter["next_followup"] = {"$gte": now}
        pending_followups = await Database.database["clients"].count_documents(followup_filter)
        
        # Adicionar tarefas pendentes
        tasks_filter = {}
        if user_id:
            tasks_filter["user_id"] = user_id
        tasks_filter["status"] = {"$ne": "DONE"}
        pending_tasks = await Database.database["tasks"].count_documents(tasks_filter)
        
        return {
            "total_clients": total_clients,
            "priority_clients": priority_clients,
            "pending_followups": pending_followups,
            "pending_tasks": pending_tasks
        } 