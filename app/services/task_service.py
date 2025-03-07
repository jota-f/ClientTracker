from app.core.database import get_db
from app.models.task import Task, TaskStatus, TaskPriority, TaskComment
from app.services.client_service import ClientService
from datetime import datetime, timezone
from bson import ObjectId
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TaskService:
    COLLECTION = "tasks"

    @staticmethod
    async def create_task(task_data: Dict[str, Any]) -> Task:
        """Cria uma nova tarefa."""
        db = await get_db()
        
        # Se houver um client_id, verifica se o cliente existe e atualiza o client_name
        if task_data.get("client_id"):
            client = await ClientService.get_client_by_id(task_data["client_id"])
            if client:
                task_data["client_name"] = client.name
        
        # Define timestamps
        now = datetime.now(timezone.utc)
        task_data["created_at"] = now
        task_data["updated_at"] = now
        
        # Insere a tarefa no banco de dados
        result = await db[TaskService.COLLECTION].insert_one(task_data)
        task_data["_id"] = result.inserted_id
        
        logger.info(f"Tarefa criada com ID: {result.inserted_id}")
        return Task(**task_data)

    @staticmethod
    async def get_task_by_id(task_id: str) -> Optional[Task]:
        """Recupera uma tarefa pelo ID."""
        try:
            db = await get_db()
            task_data = await db[TaskService.COLLECTION].find_one({"_id": ObjectId(task_id)})
            if task_data:
                return Task(**task_data)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar tarefa: {e}")
            return None

    @staticmethod
    async def update_task(task_id: str, update_data: Dict[str, Any]) -> Optional[Task]:
        """Atualiza uma tarefa existente."""
        try:
            db = await get_db()
            
            # Se houver um client_id, verifica se o cliente existe e atualiza o client_name
            if update_data.get("client_id"):
                client = await ClientService.get_client_by_id(update_data["client_id"])
                if client:
                    update_data["client_name"] = client.name
            
            # Atualiza o timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            # Atualiza a tarefa no banco de dados
            await db[TaskService.COLLECTION].update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_data}
            )
            
            # Retorna a tarefa atualizada
            return await TaskService.get_task_by_id(task_id)
        except Exception as e:
            logger.error(f"Erro ao atualizar tarefa: {e}")
            return None

    @staticmethod
    async def delete_task(task_id: str) -> bool:
        """Exclui uma tarefa pelo ID."""
        try:
            db = await get_db()
            result = await db[TaskService.COLLECTION].delete_one({"_id": ObjectId(task_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Erro ao excluir tarefa: {e}")
            return False

    @staticmethod
    async def get_all_tasks() -> List[Task]:
        """Recupera todas as tarefas."""
        try:
            db = await get_db()
            tasks_data = await db[TaskService.COLLECTION].find().to_list(length=None)
            return [Task(**task) for task in tasks_data]
        except Exception as e:
            logger.error(f"Erro ao buscar tarefas: {e}")
            return []

    @staticmethod
    async def get_tasks_by_client(client_id: str) -> List[Task]:
        """Recupera todas as tarefas de um cliente específico."""
        try:
            db = await get_db()
            tasks_data = await db[TaskService.COLLECTION].find({"client_id": client_id}).to_list(length=None)
            return [Task(**task) for task in tasks_data]
        except Exception as e:
            logger.error(f"Erro ao buscar tarefas do cliente: {e}")
            return []

    @staticmethod
    async def get_tasks_by_status(status: TaskStatus) -> List[Task]:
        """Recupera tarefas por status."""
        try:
            db = await get_db()
            tasks_data = await db[TaskService.COLLECTION].find({"status": status}).to_list(length=None)
            return [Task(**task) for task in tasks_data]
        except Exception as e:
            logger.error(f"Erro ao buscar tarefas por status: {e}")
            return []

    @staticmethod
    async def get_tasks_by_priority(priority: TaskPriority) -> List[Task]:
        """Recupera tarefas por prioridade (quadrante da Matriz Eisenhower)."""
        try:
            db = await get_db()
            tasks_data = await db[TaskService.COLLECTION].find({"priority": priority}).to_list(length=None)
            return [Task(**task) for task in tasks_data]
        except Exception as e:
            logger.error(f"Erro ao buscar tarefas por prioridade: {e}")
            return []

    @staticmethod
    async def add_comment_to_task(task_id: str, comment_text: str) -> Optional[Task]:
        """Adiciona um comentário a uma tarefa."""
        try:
            db = await get_db()
            
            # Cria o comentário
            comment = TaskComment(
                text=comment_text,
                created_at=datetime.now(timezone.utc)
            )
            
            # Adiciona o comentário à tarefa
            await db[TaskService.COLLECTION].update_one(
                {"_id": ObjectId(task_id)},
                {
                    "$push": {"comments": comment.dict()},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            
            # Retorna a tarefa atualizada
            return await TaskService.get_task_by_id(task_id)
        except Exception as e:
            logger.error(f"Erro ao adicionar comentário: {e}")
            return None

    @staticmethod
    async def get_eisenhower_matrix() -> Dict[str, List[Task]]:
        """Recupera tarefas organizadas pela Matriz Eisenhower."""
        try:
            db = await get_db()
            
            # Busca tarefas que não estão concluídas ou arquivadas
            active_tasks = await db[TaskService.COLLECTION].find({
                "status": {"$nin": [TaskStatus.DONE, TaskStatus.ARCHIVED]}
            }).to_list(length=None)
            
            # Organiza por quadrantes
            matrix = {
                "quadrant1": [],  # Urgente e Importante
                "quadrant2": [],  # Não Urgente e Importante
                "quadrant3": [],  # Urgente e Não Importante
                "quadrant4": []   # Não Urgente e Não Importante
            }
            
            for task in active_tasks:
                task_obj = Task(**task)
                
                if task_obj.priority == TaskPriority.URGENT_IMPORTANT:
                    matrix["quadrant1"].append(task_obj)
                elif task_obj.priority == TaskPriority.NOT_URGENT_IMPORTANT:
                    matrix["quadrant2"].append(task_obj)
                elif task_obj.priority == TaskPriority.URGENT_NOT_IMPORTANT:
                    matrix["quadrant3"].append(task_obj)
                elif task_obj.priority == TaskPriority.NOT_URGENT_NOT_IMPORTANT:
                    matrix["quadrant4"].append(task_obj)
            
            return matrix
        except Exception as e:
            logger.error(f"Erro ao buscar matriz Eisenhower: {e}")
            return {
                "quadrant1": [],
                "quadrant2": [],
                "quadrant3": [],
                "quadrant4": []
            }

    @staticmethod
    async def update_task_status(task_id: str, new_status: TaskStatus) -> Optional[Task]:
        """Atualiza o status de uma tarefa (para funcionalidade drag-and-drop)."""
        try:
            db = await get_db()
            
            # Atualiza o status e o timestamp
            await db[TaskService.COLLECTION].update_one(
                {"_id": ObjectId(task_id)},
                {
                    "$set": {
                        "status": new_status,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            # Retorna a tarefa atualizada
            return await TaskService.get_task_by_id(task_id)
        except Exception as e:
            logger.error(f"Erro ao atualizar status da tarefa: {e}")
            return None 