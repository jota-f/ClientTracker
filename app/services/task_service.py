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
            
            # Verifica se o user_id está presente
            if "user_id" not in task_data or not task_data["user_id"]:
                logger.warning("Atenção: task_data não contém user_id. A tarefa será criada sem proprietário.")
            
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
                "user_id": None,
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
            
            # Certifica-se de que user_id seja string se estiver presente e não for None
            if "user_id" in task_data and task_data["user_id"] is not None:
                task_data["user_id"] = str(task_data["user_id"])
                
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
    async def get_task_by_id(task_id: str, user_id: str = None) -> Optional[Task]:
        """
        Recupera uma tarefa pelo ID.
        
        Args:
            task_id: O ID da tarefa a ser recuperada
            user_id: Se fornecido, verifica se a tarefa pertence a este usuário
        """
        try:
            db = await get_db()
            
            # Primeiro, busca a tarefa apenas pelo ID
            any_task = await db[TaskService.COLLECTION].find_one({"_id": ObjectId(task_id)})
            if not any_task:
                logger.warning(f"Tarefa não encontrada: {task_id}")
                return None
            
            # Se a tarefa não tem proprietário (user_id é None ou vazio), qualquer usuário pode acessá-la
            if any_task.get("user_id") is None or any_task.get("user_id") == "":
                logger.info(f"Tarefa {task_id} não tem proprietário, permitindo acesso pelo usuário {user_id}")
                task_data = any_task
            else:
                # Criar consulta para verificar propriedade
                query = {"_id": ObjectId(task_id)}
                
                # Se user_id for fornecido, verificar propriedade
                if user_id:
                    query["user_id"] = user_id
                    logger.info(f"Buscando tarefa {task_id} com verificação de usuário {user_id}")
                else:
                    logger.info(f"Buscando tarefa {task_id} sem verificação de usuário")
                    
                task_data = await db[TaskService.COLLECTION].find_one(query)
                if not task_data and user_id:
                    logger.warning(f"Tarefa {task_id} existe mas pertence ao usuário {any_task.get('user_id')}, não ao usuário {user_id}")
                    return None
            
            if task_data:
                # Verificar se tem client_id mas não tem client_name
                if task_data.get("client_id") and (not task_data.get("client_name") or task_data.get("client_name") is None):
                    try:
                        client = await ClientService.get_client_by_id(task_data["client_id"])
                        if client:
                            task_data["client_name"] = client.name
                            logger.info(f"Nome do cliente atualizado para tarefa {task_id}: {client.name}")
                            
                            # Atualizar o registro no banco
                            await db[TaskService.COLLECTION].update_one(
                                {"_id": ObjectId(task_id)},
                                {"$set": {"client_name": client.name}}
                            )
                    except Exception as e:
                        logger.error(f"Erro ao buscar nome do cliente para tarefa {task_id}: {e}")
                
                return Task.parse_obj(task_data)
            
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar tarefa: {e}")
            return None

    @staticmethod
    async def update_task(task_id: str, update_data: Dict[str, Any], user_id: str = None, allow_status_update: bool = True) -> Optional[Task]:
        """
        Atualiza uma tarefa existente.
        
        Args:
            task_id: ID da tarefa a ser atualizada
            update_data: Dados para atualizar
            user_id: Se fornecido, verifica se a tarefa pertence a este usuário
            allow_status_update: Se True, permite atualizar o status mesmo que a tarefa pertença a outro usuário
        """
        try:
            db = await get_db()
            
            # Log detalhado para diagnóstico
            logger.info(f"Tentativa de atualização da tarefa {task_id}")
            logger.info(f"User ID fornecido: {user_id}")
            logger.info(f"Dados para atualização: {update_data}")
            
            # Primeiro, verifica se a tarefa existe
            any_task = await db[TaskService.COLLECTION].find_one({"_id": ObjectId(task_id)})
            if not any_task:
                logger.warning(f"Tarefa {task_id} não existe no banco de dados")
                return None
            
            # Verificar se esta é apenas uma atualização de status para DONE
            is_status_update_only = (
                len(update_data) == 1 and 
                "status" in update_data and 
                update_data["status"] == TaskStatus.DONE and
                allow_status_update
            )
            
            # Verificar se a tarefa já está com status DONE
            is_task_already_done = any_task.get("status") == TaskStatus.DONE
                
            # Se a tarefa já está DONE ou se for apenas atualização de status, não verifica propriedade
            if is_status_update_only or (is_task_already_done and allow_status_update):
                if is_task_already_done:
                    logger.info(f"Permitindo edição da tarefa {task_id} que já está concluída, mesmo que não seja o proprietário")
                else:
                    logger.info(f"Permitindo atualização de status para DONE na tarefa {task_id}, mesmo que não seja o proprietário")
                    
                existing_task = any_task
            # Verificar se a tarefa não tem proprietário (user_id é None ou vazio)
            elif any_task.get("user_id") is None or any_task.get("user_id") == "":
                logger.info(f"Tarefa {task_id} não tem proprietário, permitindo edição pelo usuário {user_id}")
                existing_task = any_task
            else:
                # Criar consulta para verificar propriedade
                query = {"_id": ObjectId(task_id)}
                if user_id:
                    query["user_id"] = user_id
                    logger.info(f"Verificando propriedade da tarefa {task_id} para usuário {user_id}")
                
                # Verifica se a tarefa existe e pertence ao usuário
                existing_task = await db[TaskService.COLLECTION].find_one(query)
                
                if not existing_task:
                    if user_id:
                        owner_id = any_task.get("user_id")
                        logger.warning(f"Tentativa de atualizar tarefa {task_id} de outro usuário. Proprietário: {owner_id}, Solicitante: {user_id}")
                        logger.warning(f"Tarefa encontrada: {any_task}")
                        return None
                    else:
                        logger.warning(f"Tarefa {task_id} não encontrada e nenhum user_id fornecido")
                    
                    logger.warning(f"Tarefa {task_id} não encontrada para atualização")
                    return None
                else:
                    logger.info(f"Tarefa {task_id} encontrada para o usuário {user_id}")
            
            # Verificar se o status está sendo alterado para "DONE" e a tarefa tem client_id
            creating_interaction = (
                "status" in update_data and 
                update_data["status"] == TaskStatus.DONE and 
                existing_task.get("status") != TaskStatus.DONE and
                existing_task.get("client_id")
            )
            
            # Se houver um client_id, verifica se o cliente existe e atualiza o client_name
            if update_data.get("client_id"):
                try:
                    # Importando aqui para evitar o erro de escopo da variável
                    from app.services.client_service import ClientService
                    client = await ClientService.get_client_by_id(update_data["client_id"])
                    if client:
                        update_data["client_name"] = client.name
                except Exception as e:
                    logger.error(f"Erro ao obter informações do cliente: {e}")
                    # Continua o fluxo mesmo com erro no cliente
            
            # Atualiza o timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            # Se a tarefa não tinha user_id e agora estamos atualizando, definir o user_id
            if (any_task.get("user_id") is None or any_task.get("user_id") == "") and user_id and "user_id" not in update_data:
                update_data["user_id"] = user_id
                logger.info(f"Definindo user_id da tarefa {task_id} para {user_id}")
            
            # Atualiza a tarefa no banco de dados
            await db[TaskService.COLLECTION].update_one(
                {"_id": ObjectId(task_id)},  # Usa apenas o ID, não verifica propriedade aqui
                {"$set": update_data}
            )
            
            # Obter a tarefa atualizada
            updated_task = await TaskService.get_task_by_id(task_id) if is_status_update_only else await TaskService.get_task_by_id(task_id, user_id)
            
            # Se a tarefa foi atualizada para DONE e tem um cliente associado, adicionar interação
            if updated_task and creating_interaction:
                try:
                    from app.models.client import Interaction
                    from app.services.client_service import ClientService
                    
                    # Criar interação baseada na tarefa concluída
                    interaction = Interaction(
                        type="TAREFA_CONCLUÍDA",
                        notes=f"Tarefa concluída: {existing_task.get('title', 'Sem título')}",
                        outcome="Tarefa marcada como concluída no sistema"
                    )
                    
                    # Adicionar interação ao cliente
                    await ClientService.add_interaction(existing_task.get("client_id"), interaction)
                    logger.info(f"Interação adicionada automaticamente ao cliente {existing_task.get('client_id')} pela conclusão da tarefa {task_id}")
                except Exception as e:
                    logger.error(f"Erro ao adicionar interação automática: {e}")
                    # Não retornar erro para não interromper o fluxo principal
            
            return updated_task
        except Exception as e:
            logger.error(f"Erro ao atualizar tarefa: {e}")
            return None

    @staticmethod
    async def delete_task(task_id: str, user_id: str = None) -> bool:
        """
        Exclui uma tarefa pelo ID.
        
        Args:
            task_id: ID da tarefa a ser excluída
            user_id: Se fornecido, verifica se a tarefa pertence a este usuário
        """
        try:
            db = await get_db()
            
            # Primeiro verifica se a tarefa existe
            any_task = await db[TaskService.COLLECTION].find_one({"_id": ObjectId(task_id)})
            if not any_task:
                logger.warning(f"Tarefa {task_id} não existe no banco de dados")
                return False
                
            # Verificar se a tarefa não tem proprietário (user_id é None ou vazio)
            if any_task.get("user_id") is None or any_task.get("user_id") == "":
                logger.info(f"Tarefa {task_id} não tem proprietário, permitindo exclusão pelo usuário {user_id}")
                
                # Excluir tarefa diretamente
                result = await db[TaskService.COLLECTION].delete_one({"_id": ObjectId(task_id)})
                return result.deleted_count > 0
            
            # Criar consulta para verificar propriedade
            query = {"_id": ObjectId(task_id)}
            if user_id:
                query["user_id"] = user_id
                logger.info(f"Verificando propriedade da tarefa {task_id} para exclusão pelo usuário {user_id}")
            
            # Tenta excluir a tarefa
            result = await db[TaskService.COLLECTION].delete_one(query)
            
            # Se nenhuma tarefa foi excluída e temos user_id, verifica se ela existe mas é de outro usuário
            if result.deleted_count == 0 and user_id:
                any_task = await db[TaskService.COLLECTION].find_one({"_id": ObjectId(task_id)})
                if any_task:
                    logger.warning(f"Tentativa de excluir tarefa {task_id} de outro usuário. Proprietário: {any_task.get('user_id')}, Solicitante: {user_id}")
            
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Erro ao excluir tarefa: {e}")
            return False

    @staticmethod
    async def get_all_tasks(user_id: str = None, include_all: bool = False) -> List[Task]:
        """
        Recupera todas as tarefas, filtradas por usuário por padrão.
        
        Args:
            user_id: ID do usuário para filtrar as tarefas
            include_all: Se True e user_id for None, retorna todas as tarefas (apenas para admin)
        """
        try:
            db = await get_db()
            
            # Criar filtro baseado no user_id
            query = {}
            
            # Garantir filtragem por usuário a menos que explicitamente solicitado para mostrar todas
            if user_id:
                query["user_id"] = user_id
                logger.info(f"Filtrando tarefas por user_id: {user_id}")
            elif not include_all:
                # Caso não haja user_id e não foi solicitado para incluir todas,
                # retornar lista vazia por segurança
                logger.warning("Tentativa de acessar todas as tarefas sem user_id e sem permissão para incluir todas")
                return []
            else:
                logger.info("Retornando todas as tarefas (modo admin)")
            
            # Buscar tarefas com o filtro aplicado
            logger.info(f"Executando consulta de tarefas com filtro: {query}")
            tasks_data = await db[TaskService.COLLECTION].find(query).to_list(length=None)
            logger.info(f"Recuperadas {len(tasks_data)} tarefas do MongoDB")
            
            tasks = []
            for task_data in tasks_data:
                try:
                    # Converter _id para id
                    task_data["id"] = str(task_data.pop("_id"))
                    tasks.append(Task.parse_obj(task_data))
                except Exception as e:
                    logger.error(f"Erro ao converter tarefa {task_data.get('_id')}: {e}")
            
            return tasks
        except Exception as e:
            logger.error(f"Erro ao recuperar tarefas: {str(e)}")
            return []

    @staticmethod
    async def get_tasks_by_client(client_id: str, user_id: str = None) -> List[Task]:
        """Recupera todas as tarefas associadas a um cliente."""
        try:
            db = await get_db()
            
            # Criar filtro
            query = {"client_id": client_id}
            
            # Adicionar filtro de usuário se fornecido
            if user_id:
                query["user_id"] = user_id
                logger.info(f"Filtrando tarefas do cliente {client_id} para usuário {user_id}")
            
            tasks_data = await db[TaskService.COLLECTION].find(query).to_list(length=None)
            
            tasks = []
            for task_data in tasks_data:
                task_data["id"] = str(task_data.pop("_id"))
                tasks.append(Task.parse_obj(task_data))
            
            return tasks
        except Exception as e:
            logger.error(f"Erro ao recuperar tarefas por cliente: {e}")
            return []

    @staticmethod
    async def get_tasks_by_status(status: TaskStatus, user_id: str = None) -> List[Task]:
        """Recupera todas as tarefas com um determinado status."""
        try:
            db = await get_db()
            
            # Criar filtro
            query = {"status": status}
            
            # Adicionar filtro de usuário se fornecido
            if user_id:
                query["user_id"] = user_id
                logger.info(f"Filtrando tarefas com status {status} para usuário {user_id}")
            
            tasks_data = await db[TaskService.COLLECTION].find(query).to_list(length=None)
            
            tasks = []
            for task_data in tasks_data:
                task_data["id"] = str(task_data.pop("_id"))
                tasks.append(Task.parse_obj(task_data))
            
            return tasks
        except Exception as e:
            logger.error(f"Erro ao recuperar tarefas por status: {e}")
            return []

    @staticmethod
    async def get_tasks_by_priority(priority: TaskPriority, user_id: str = None) -> List[Task]:
        """Recupera todas as tarefas com uma determinada prioridade."""
        try:
            db = await get_db()
            
            # Criar filtro
            query = {"priority": priority}
            
            # Adicionar filtro de usuário se fornecido
            if user_id:
                query["user_id"] = user_id
                logger.info(f"Filtrando tarefas com prioridade {priority} para usuário {user_id}")
            
            tasks_data = await db[TaskService.COLLECTION].find(query).to_list(length=None)
            
            tasks = []
            for task_data in tasks_data:
                task_data["id"] = str(task_data.pop("_id"))
                tasks.append(Task.parse_obj(task_data))
            
            return tasks
        except Exception as e:
            logger.error(f"Erro ao recuperar tarefas por prioridade: {e}")
            return []

    @staticmethod
    async def add_comment_to_task(task_id: str, comment_text: str, user_id: str = None) -> Optional[Task]:
        """Adiciona um comentário a uma tarefa."""
        try:
            db = await get_db()
            
            # Verificar se a tarefa existe e pertence ao usuário
            query = {"_id": ObjectId(task_id)}
            if user_id:
                query["user_id"] = user_id
                logger.info(f"Verificando propriedade da tarefa {task_id} para adicionar comentário")
            
            task_data = await db[TaskService.COLLECTION].find_one(query)
            if not task_data:
                # Se user_id foi fornecido e não encontrou, verificar se a tarefa existe para outro usuário
                if user_id:
                    any_task = await db[TaskService.COLLECTION].find_one({"_id": ObjectId(task_id)})
                    if any_task:
                        logger.warning(f"Tentativa de adicionar comentário à tarefa {task_id} de outro usuário. Proprietário: {any_task.get('user_id')}")
                        return None
                
                logger.warning(f"Tarefa {task_id} não encontrada para adicionar comentário")
                return None
            
            # Criar comentário
            comment = {
                "text": comment_text,
                "created_at": datetime.now(timezone.utc)
            }
            
            # Atualizar a tarefa com o novo comentário
            await db[TaskService.COLLECTION].update_one(
                query,
                {
                    "$push": {"comments": comment},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            
            # Retornar a tarefa atualizada
            return await TaskService.get_task_by_id(task_id, user_id)
        except Exception as e:
            logger.error(f"Erro ao adicionar comentário: {e}")
            return None

    @staticmethod
    async def get_eisenhower_matrix(user_id: str = None) -> Dict[str, List[Task]]:
        """Recupera tarefas organizadas pela Matriz Eisenhower, opcionalmente filtradas por usuário."""
        try:
            # Buscar todas as tarefas, filtradas por usuário se fornecido
            tasks = await TaskService.get_all_tasks(user_id)
            
            # Inicializar a matriz Eisenhower
            matrix = {
                "urgent_important": [],       # Quadrante 1
                "not_urgent_important": [],   # Quadrante 2
                "urgent_not_important": [],   # Quadrante 3
                "not_urgent_not_important": [] # Quadrante 4
            }
            
            # Distribuir tarefas pelos quadrantes
            for task in tasks:
                if task.priority == TaskPriority.URGENT_IMPORTANT:
                    matrix["urgent_important"].append(task)
                elif task.priority == TaskPriority.NOT_URGENT_IMPORTANT:
                    matrix["not_urgent_important"].append(task)
                elif task.priority == TaskPriority.URGENT_NOT_IMPORTANT:
                    matrix["urgent_not_important"].append(task)
                elif task.priority == TaskPriority.NOT_URGENT_NOT_IMPORTANT:
                    matrix["not_urgent_not_important"].append(task)
            
            # Ordenar tarefas por data de vencimento, se disponível
            for quadrant in matrix:
                matrix[quadrant].sort(
                    key=lambda x: (x.due_date is None, x.due_date)
                )
            
            total_tasks = sum(len(tasks) for tasks in matrix.values())
            logger.info(f"Matriz Eisenhower montada com {total_tasks} tarefas")
            
            return matrix
        except Exception as e:
            logger.error(f"Erro ao montar matriz Eisenhower: {str(e)}")
            return {
                "urgent_important": [],
                "not_urgent_important": [],
                "urgent_not_important": [],
                "not_urgent_not_important": []
            }

    @staticmethod
    async def update_task_status(task_id: str, new_status: TaskStatus, user_id: str = None) -> Optional[Task]:
        """
        Atualiza o status de uma tarefa.
        
        Args:
            task_id: ID da tarefa a atualizar
            new_status: Novo status da tarefa
            user_id: Se fornecido, verifica se a tarefa pertence a este usuário
        """
        try:
            # Usar o método update_task com verificação de usuário
            # Isso já vai cuidar de adicionar a interação se necessário
            # Permitir atualização de status mesmo se não for o proprietário da tarefa
            return await TaskService.update_task(
                task_id, 
                {"status": new_status}, 
                user_id=user_id,
                allow_status_update=True
            )
        except Exception as e:
            logger.error(f"Erro ao atualizar status da tarefa: {e}")
            return None

    @staticmethod
    async def get_eisenhower_matrix_for_user(user_id: str) -> Dict[str, List[Task]]:
        """
        Recupera tarefas organizadas pela Matriz Eisenhower para um usuário específico.
        """
        if not user_id:
            logger.error("user_id não fornecido para get_eisenhower_matrix_for_user")
            return {
                "urgent_important": [],
                "not_urgent_important": [],
                "urgent_not_important": [],
                "not_urgent_not_important": []
            }
            
        # Simplesmente delega para o método get_eisenhower_matrix com o user_id
        return await TaskService.get_eisenhower_matrix(user_id) 