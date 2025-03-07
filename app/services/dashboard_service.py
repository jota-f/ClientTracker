from datetime import datetime, timezone
from app.core.database import Database
from app.models.client import Client

class DashboardService:
    @staticmethod
    async def get_dashboard_metrics():
        """
        Retorna as métricas para o dashboard:
        - Total de clientes
        - Clientes prioritários (RFM >= 10)
        - Follow-ups pendentes
        """
        now = datetime.now(timezone.utc)
        
        # Total de clientes
        total_clients = await Database.database["clients"].count_documents({})
        
        # Clientes prioritários (RFM >= 10)
        priority_clients = await Database.database["clients"].count_documents({
            "rfm_scores.total": {"$gte": 10}
        })
        
        # Follow-ups pendentes
        pending_followups = await Database.database["clients"].count_documents({
            "next_followup": {"$gte": now}
        })
        
        return {
            "total_clients": total_clients,
            "priority_clients": priority_clients,
            "pending_followups": pending_followups
        } 