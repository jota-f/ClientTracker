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
        try:
            db = await get_db()
            
            logger.info(f"Iniciando criação de tarefa no serviço: {task_data.get('title')}")
            logger.info(f"Dados completos: {task_data}")
            
            # Se houver um client_id, verifica se o cliente existe e atualiza o client_name
            if task_data.get("client_id"):
                try:
                    client_id = str(task_data["client_id"])
                    if client_id and client_id.strip():
                        logger.info(f"Buscando cliente com ID: {client_id}")
                        client = await ClientService.get_client_by_id(client_id)
                        if client:
                            task_data["client_name"] = client.name
                            logger.info(f"Nome do cliente atualizado: {client.name}")
                        else:
                            logger.warning(f"Cliente não encontrado: {client_id}")
                    else:
                        task_data["client_id"] = None
                        logger.info("ID do cliente vazio, definido como None")
                except Exception as e:
                    logger.error(f"Erro ao buscar cliente: {e}")
                    task_data["client_id"] = None
            
            # Define timestamps
            now = datetime.now(timezone.utc)
            task_data["created_at"] = now
            task_data["updated_at"] = now
            
            # Verifica todos os campos da tarefa
            required_fields = ["title", "priority", "status"]
            for field in required_fields:
                if field not in task_data or task_data[field] is None or task_data[field] == "":
                    logger.error(f"Campo obrigatório ausente: {field}")
                    raise ValueError(f"Campo obrigatório ausente: {field}")
            
            # Inicializa campos que podem ser nulos
            optional_fields = {
                "description": None,
                "due_date": None,
                "client_id": None,
                "client_name": None,
                "assignee": None,
                "comments": []
            }
            
            for field, default_value in optional_fields.items():
                if field not in task_data or task_data[field] == "":
                    task_data[field] = default_value
            
            # Certifica-se de que as datas estão no formato correto
            for date_field in ["due_date", "created_at", "updated_at"]:
                if date_field in task_data and task_data[date_field] is not None:
                    if isinstance(task_data[date_field], str):
                        try:
                            task_data[date_field] = datetime.fromisoformat(
                                task_data[date_field].replace('Z', '+00:00')
                            )
                        except (ValueError, TypeError) as e:
                            logger.error(f"Erro ao converter data {date_field}: {e}")
                            if date_field == "due_date":
                                task_data[date_field] = None
                    
                    # Garantir que a data tenha timezone
                    if isinstance(task_data[date_field], datetime) and task_data[date_field].tzinfo is None:
                        task_data[date_field] = task_data[date_field].replace(tzinfo=timezone.utc)
            
            logger.info(f"Dados finais da tarefa: {task_data}")
            
            # Insere a tarefa no banco de dados
            result = await db[TaskService.COLLECTION].insert_one(task_data)
            task_data["_id"] = result.inserted_id
            
            logger.info(f"Tarefa criada com sucesso. ID: {result.inserted_id}")
            
            # Tenta converter para Task ou retorna como dicionário se falhar
            try:
                return Task(**task_data)
            except Exception as e:
                logger.error(f"Erro ao converter para Task: {e}")
                # Criar manualmente um objeto Task com os campos mínimos
                return Task(
                    _id=result.inserted_id,
                    title=task_data["title"],
                    priority=task_data["priority"],
                    status=task_data["status"],
                    created_at=task_data["created_at"],
                    updated_at=task_data["updated_at"]
                )
        except Exception as e:
            logger.error(f"Erro ao criar tarefa no serviço: {e}", exc_info=True)
            raise

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