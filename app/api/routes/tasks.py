from fastapi import APIRouter, HTTPException, status, Body, Depends
from app.models.task import Task, TaskStatus, TaskPriority, TaskComment
from app.services.task_service import TaskService
from app.models.user import User
from app.core.dependencies import get_current_user
from typing import List, Optional
import logging
from datetime import timezone, datetime
from pydantic import ValidationError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(task_data: dict = Body(...), current_user: User = Depends(get_current_user)):
    """Cria uma nova tarefa."""
    try:
        logger.info(f"Recebendo dados para criar tarefa: {task_data}")
        
        # Adicionar o user_id do usuário autenticado
        task_data["user_id"] = str(current_user.id)
        logger.info(f"Adicionando user_id do usuário autenticado: {task_data['user_id']}")
        
        # Verificar e tratar os dados necessários
        if "priority" not in task_data or not task_data["priority"]:
            logger.error("Erro: Prioridade não informada")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Prioridade é obrigatória"
            )
            
        # Verificar e tratar datas
        if "due_date" in task_data and task_data["due_date"]:
            try:
                # Converter string de data para objeto datetime
                due_date = datetime.fromisoformat(task_data["due_date"].replace('Z', '+00:00'))
                task_data["due_date"] = due_date
                logger.info(f"Data de vencimento convertida: {due_date}")
            except (ValueError, TypeError) as e:
                logger.error(f"Erro ao converter data de vencimento: {e}")
                task_data["due_date"] = None
        
        # Garantir que os campos obrigatórios estão presentes
        task_data["status"] = task_data.get("status", "TODO")
        
        # Remover campos vazios opcionais
        for key in list(task_data.keys()):
            if task_data[key] == "" and key not in ["title", "priority", "status", "user_id"]:
                task_data[key] = None
        
        logger.info(f"Dados processados: {task_data}")
        
        # Criar a tarefa usando o serviço
        created_task = await TaskService.create_task(task_data)
        logger.info(f"Tarefa criada com sucesso: {created_task.id}")
        return created_task
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar tarefa: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar tarefa: {str(e)}"
        )

@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    """Recupera uma tarefa pelo ID."""
    task = await TaskService.get_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada"
        )
    return task

@router.put("/{task_id}", response_model=Task)
async def update_task(task_id: str, update_data: dict = Body(...)):
    """Atualiza uma tarefa."""
    logger.info(f"Atualizando tarefa {task_id}")
    updated_task = await TaskService.update_task(task_id, update_data)
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada ou erro ao atualizar"
        )
    return updated_task

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str):
    """Exclui uma tarefa."""
    success = await TaskService.delete_task(task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada ou erro ao excluir"
        )
    return None

@router.get("/", response_model=List[Task])
async def get_all_tasks(current_user: User = Depends(get_current_user)):
    """Recupera todas as tarefas do usuário autenticado."""
    return await TaskService.get_all_tasks(user_id=str(current_user.id))

@router.get("/client/{client_id}", response_model=List[Task])
async def get_client_tasks(client_id: str):
    """Recupera todas as tarefas de um cliente específico."""
    return await TaskService.get_tasks_by_client(client_id)

@router.get("/status/{status}", response_model=List[Task])
async def get_tasks_by_status(status: TaskStatus):
    """Recupera tarefas por status."""
    return await TaskService.get_tasks_by_status(status)

@router.get("/priority/{priority}", response_model=List[Task])
async def get_tasks_by_priority(priority: TaskPriority):
    """Recupera tarefas por prioridade (quadrante da Matriz Eisenhower)."""
    return await TaskService.get_tasks_by_priority(priority)

@router.post("/{task_id}/comments", response_model=Task)
async def add_comment(task_id: str, comment_text: str = Body(..., embed=True)):
    """Adiciona um comentário a uma tarefa."""
    updated_task = await TaskService.add_comment_to_task(task_id, comment_text)
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada ou erro ao adicionar comentário"
        )
    return updated_task

@router.patch("/{task_id}/status", response_model=Task)
async def update_status(task_id: str, new_status: TaskStatus = Body(..., embed=True)):
    """Atualiza o status de uma tarefa (para funcionalidade drag-and-drop)."""
    updated_task = await TaskService.update_task_status(task_id, new_status)
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada ou erro ao atualizar status"
        )
    return updated_task

@router.get("/eisenhower", response_model=dict)
async def get_eisenhower_matrix(current_user: User = Depends(get_current_user)):
    """Recupera tarefas organizadas pela Matriz Eisenhower para o usuário autenticado."""
    return await TaskService.get_eisenhower_matrix(user_id=str(current_user.id))

@router.patch("/{task_id}/priority", response_model=Task)
async def update_priority(task_id: str, new_priority: TaskPriority = Body(..., embed=True)):
    """Atualiza a prioridade de uma tarefa (para funcionalidade de mudança de prioridade)."""
    try:
        logger.info(f"Atualizando prioridade da tarefa {task_id} para {new_priority}")
        updated_task = await TaskService.update_task(task_id, {"priority": new_priority})
        if not updated_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarefa não encontrada ou erro ao atualizar prioridade"
            )
        return updated_task
    except Exception as e:
        logger.error(f"Erro ao atualizar prioridade: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar prioridade da tarefa: {str(e)}"
        ) 