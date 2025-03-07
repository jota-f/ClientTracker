from fastapi import APIRouter, HTTPException, status, Body
from app.models.task import Task, TaskStatus, TaskPriority, TaskComment
from app.services.task_service import TaskService
from typing import List, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(task: Task = Body(...)):
    """Cria uma nova tarefa."""
    try:
        logger.info(f"Criando tarefa: {task.title}")
        created_task = await TaskService.create_task(task.dict(by_alias=True, exclude_unset=True))
        return created_task
    except Exception as e:
        logger.error(f"Erro ao criar tarefa: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar tarefa: {e}"
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
async def get_all_tasks():
    """Recupera todas as tarefas."""
    return await TaskService.get_all_tasks()

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
async def get_eisenhower_matrix():
    """Recupera tarefas organizadas pela Matriz Eisenhower."""
    return await TaskService.get_eisenhower_matrix() 