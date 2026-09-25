from datetime import datetime, timezone, timedelta
from app.core.database import Database
from app.models.client import Client, ClientStatus
from app.models.task import TaskStatus, TaskPriority
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
    
    @staticmethod
    async def get_advanced_dashboard_metrics(user_id: str = None):
        """
        Retorna métricas avançadas para o dashboard, incluindo:
        - Métricas básicas
        - Distribuição de clientes por status
        - Clientes por nível de prioridade (RFM)
        - Distribuição de tarefas por quadrante Eisenhower
        - Previsão de follow-ups para as próximas 4 semanas
        - Taxa de conversão (leads para clientes)
        """
        # Obter métricas básicas
        basic_metrics = await DashboardService.get_dashboard_metrics(user_id)
        
        now = datetime.now(timezone.utc)
        
        # Filtro base para clientes
        client_filter = {}
        if user_id:
            client_filter["user_id"] = user_id
        
        # Filtro base para tarefas
        task_filter = {}
        if user_id:
            task_filter["user_id"] = user_id
        
        # Distribuição de clientes por status
        client_status_distribution = {}
        
        for status in ClientStatus:
            status_filter = client_filter.copy()
            status_filter["status"] = status.value
            count = await Database.database["clients"].count_documents(status_filter)
            client_status_distribution[status.value] = count
        
        # Distribuição de clientes por nível RFM
        low_rfm_filter = client_filter.copy()
        low_rfm_filter["rfm_scores.total"] = {"$lt": 7}
        low_rfm_count = await Database.database["clients"].count_documents(low_rfm_filter)
        
        medium_rfm_filter = client_filter.copy()
        medium_rfm_filter["rfm_scores.total"] = {"$gte": 7, "$lt": 10}
        medium_rfm_count = await Database.database["clients"].count_documents(medium_rfm_filter)
        
        high_rfm_filter = client_filter.copy()
        high_rfm_filter["rfm_scores.total"] = {"$gte": 10}
        high_rfm_count = await Database.database["clients"].count_documents(high_rfm_filter)
        
        rfm_distribution = {
            "low": low_rfm_count,
            "medium": medium_rfm_count,
            "high": high_rfm_count
        }
        
        # Distribuição de tarefas por quadrante Eisenhower
        task_priority_distribution = {}
        
        for priority in TaskPriority:
            priority_filter = task_filter.copy()
            priority_filter["priority"] = priority.value
            count = await Database.database["tasks"].count_documents(priority_filter)
            task_priority_distribution[priority.value] = count
        
        # Tarefas por status
        task_status_distribution = {}
        
        for status in TaskStatus:
            status_filter = task_filter.copy()
            status_filter["status"] = status.value
            count = await Database.database["tasks"].count_documents(status_filter)
            task_status_distribution[status.value] = count
        
        # Previsão de follow-ups para as próximas 4 semanas
        today = now.date()
        current_week_start = today - timedelta(days=today.weekday())
        followup_forecast = []
        
        # Calculando por semana para as próximas 4 semanas (calendário)
        for week in range(4):
            week_start_date = current_week_start + timedelta(weeks=week)
            week_end_date = week_start_date + timedelta(days=6)
            
            week_start_dt = datetime.combine(week_start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            week_end_dt = datetime.combine(week_end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            
            followup_filter = client_filter.copy()
            followup_filter["next_followup"] = {"$gte": week_start_dt, "$lte": week_end_dt}
            count = await Database.database["clients"].count_documents(followup_filter)
            
            followup_forecast.append({
                "week": week + 1,
                "is_current": week == 0,
                "count": count,
                "start_date": week_start_date.strftime("%d/%m"),
                "end_date": week_end_date.strftime("%d/%m")
            })
        
        # Taxa de conversão (lead para cliente)
        lead_filter = client_filter.copy()
        lead_filter["status"] = ClientStatus.LEAD.value
        lead_count = await Database.database["clients"].count_documents(lead_filter)
        
        customer_filter = client_filter.copy()
        customer_filter["status"] = ClientStatus.CUSTOMER.value
        customer_count = await Database.database["clients"].count_documents(customer_filter)
        
        conversion_rate = 0
        if lead_count > 0:
            conversion_rate = (customer_count / (lead_count + customer_count)) * 100
        
        # Métricas completas
        return {
            **basic_metrics,
            "client_status_distribution": client_status_distribution,
            "rfm_distribution": rfm_distribution,
            "task_priority_distribution": task_priority_distribution,
            "task_status_distribution": task_status_distribution,
            "followup_forecast": followup_forecast,
            "followup_history": followup_forecast,  # Manter compatibilidade com código legado
            "conversion_rate": conversion_rate
        }
    
    @staticmethod
    async def get_weekly_review_metrics(user_id: str = None):
        """
        Retorna métricas para a revisão semanal, incluindo:
        - Tarefas concluídas esta semana
        - Tarefas criadas esta semana
        - Clientes contatados esta semana
        - Próximos follow-ups para a próxima semana
        - Novos clientes adicionados esta semana
        - Tarefas vencidas
        - Clientes que precisam de follow-up urgente (alto RFM e sem contato recente)
        """
        now = datetime.now(timezone.utc)
        # Início e fim da semana atual (segunda a domingo)
        today = now.date()
        start_of_week = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        end_of_week = (today + timedelta(days=6 - today.weekday())).strftime("%Y-%m-%d")
        
        # Início e fim da próxima semana
        next_week_start = (today + timedelta(days=7 - today.weekday())).strftime("%Y-%m-%d")
        next_week_end = (today + timedelta(days=13 - today.weekday())).strftime("%Y-%m-%d")
        
        # Converter para datetime
        start_of_week_dt = datetime.strptime(f"{start_of_week}T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        end_of_week_dt = datetime.strptime(f"{end_of_week}T23:59:59Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        next_week_start_dt = datetime.strptime(f"{next_week_start}T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        next_week_end_dt = datetime.strptime(f"{next_week_end}T23:59:59Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        
        # Filtro base
        base_filter = {}
        if user_id:
            base_filter["user_id"] = user_id
        
        # 1. Tarefas concluídas esta semana
        completed_tasks_filter = base_filter.copy()
        completed_tasks_filter["status"] = TaskStatus.DONE.value
        completed_tasks_filter["updated_at"] = {"$gte": start_of_week_dt, "$lte": end_of_week_dt}
        completed_tasks = await Database.database["tasks"].count_documents(completed_tasks_filter)
        
        # 2. Tarefas criadas esta semana
        new_tasks_filter = base_filter.copy()
        new_tasks_filter["created_at"] = {"$gte": start_of_week_dt, "$lte": end_of_week_dt}
        new_tasks = await Database.database["tasks"].count_documents(new_tasks_filter)
        
        # 3. Clientes contatados esta semana (com interações registradas)
        contacted_clients = await Database.database["clients"].distinct("_id", {
            **base_filter,
            "interaction_history.date": {"$gte": start_of_week_dt, "$lte": end_of_week_dt}
        })
        
        # 4. Próximos follow-ups para a próxima semana
        upcoming_followups_filter = base_filter.copy()
        upcoming_followups_filter["next_followup"] = {"$gte": next_week_start_dt, "$lte": next_week_end_dt}
        upcoming_followups = await Database.database["clients"].count_documents(upcoming_followups_filter)
        
        # Listar os clientes com follow-ups na próxima semana (limitado a 10)
        upcoming_followup_clients = await Database.database["clients"].find(
            upcoming_followups_filter,
            {"name": 1, "company": 1, "next_followup": 1, "rfm_scores": 1}
        ).sort("next_followup", 1).limit(10).to_list(length=10)
        
        # 5. Novos clientes adicionados esta semana
        new_clients_filter = base_filter.copy()
        new_clients_filter["created_at"] = {"$gte": start_of_week_dt, "$lte": end_of_week_dt}
        new_clients = await Database.database["clients"].count_documents(new_clients_filter)
        
        # 6. Tarefas vencidas
        overdue_tasks_filter = base_filter.copy()
        overdue_tasks_filter["status"] = {"$ne": TaskStatus.DONE.value}
        overdue_tasks_filter["due_date"] = {"$lt": now}
        overdue_tasks = await Database.database["tasks"].count_documents(overdue_tasks_filter)
        
        # Listar as tarefas vencidas (limitado a 10)
        overdue_tasks_list = await Database.database["tasks"].find(
            overdue_tasks_filter,
            {"title": 1, "due_date": 1, "priority": 1, "client_name": 1}
        ).sort("due_date", 1).limit(10).to_list(length=10)
        
        # 7. Clientes prioritários sem contato recente (30 dias)
        thirty_days_ago = now - timedelta(days=30)
        priority_clients_filter = base_filter.copy()
        priority_clients_filter["rfm_scores.total"] = {"$gte": 10}
        priority_clients_filter["last_contact"] = {"$lt": thirty_days_ago}
        priority_clients_need_contact = await Database.database["clients"].count_documents(priority_clients_filter)
        
        # Listar os clientes prioritários sem contato recente (limitado a 10)
        priority_clients_list = await Database.database["clients"].find(
            priority_clients_filter,
            {"name": 1, "company": 1, "last_contact": 1, "rfm_scores": 1}
        ).sort("last_contact", 1).limit(10).to_list(length=10)
        
        return {
            "completed_tasks": completed_tasks,
            "new_tasks": new_tasks,
            "contacted_clients": len(contacted_clients),
            "upcoming_followups": upcoming_followups,
            "upcoming_followup_clients": upcoming_followup_clients,
            "new_clients": new_clients,
            "overdue_tasks": overdue_tasks,
            "overdue_tasks_list": overdue_tasks_list,
            "priority_clients_need_contact": priority_clients_need_contact,
            "priority_clients_list": priority_clients_list,
            "week_period": {
                "start": start_of_week,
                "end": end_of_week
            },
            "next_week_period": {
                "start": next_week_start,
                "end": next_week_end
            }
        } 