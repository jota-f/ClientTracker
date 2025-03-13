#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de diagnóstico para verificar se tarefas estão corretamente associadas a usuários
e se podem ser acessadas pelos usuários corretos.
"""

import sys
import asyncio
import logging
import os
import json

# Adicionar o diretório raiz ao path do Python para permitir a importação dos módulos da aplicação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import connect_to_mongo, close_mongo_connection

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def diagnose_task_user_assignments():
    """
    Analisa todas as tarefas no banco de dados para verificar se estão corretamente associadas a usuários.
    """
    try:
        # Conectar ao banco de dados
        db = await connect_to_mongo()
        
        # Buscar todos os usuários e criar um mapa de ID para nome
        users = await db["users"].find().to_list(100)
        user_map = {str(user["_id"]): user["username"] for user in users}
        
        # Contar tarefas sem user_id
        tasks_without_user = await db["tasks"].count_documents({"user_id": {"$exists": False}})
        logger.info(f"Tarefas sem user_id (campo não existe): {tasks_without_user}")
        
        # Contar tarefas com user_id nulo
        tasks_with_null_user = await db["tasks"].count_documents({"user_id": None})
        logger.info(f"Tarefas com user_id nulo: {tasks_with_null_user}")
        
        # Verificar tarefas com user_id que não é string
        tasks_with_objectid = await db["tasks"].count_documents({"user_id": {"$type": "objectId"}})
        logger.info(f"Tarefas com user_id como ObjectId: {tasks_with_objectid}")
        
        # Verificar tarefas com user_id inválido (que não corresponde a nenhum usuário)
        tasks = await db["tasks"].find().to_list(1000)
        tasks_with_invalid_user = 0
        tasks_by_user = {}
        orphaned_tasks = []
        
        for task in tasks:
            task_id = str(task["_id"])
            
            # Verificar se o campo user_id existe
            if "user_id" not in task:
                orphaned_tasks.append({
                    "id": task_id,
                    "title": task.get("title", "Sem título"),
                    "status": task.get("status", "Desconhecido")
                })
                continue
            
            user_id = task.get("user_id")
            
            # Verificar se user_id é None
            if user_id is None:
                orphaned_tasks.append({
                    "id": task_id,
                    "title": task.get("title", "Sem título"),
                    "status": task.get("status", "Desconhecido")
                })
                continue
                
            # Contar tarefas por usuário
            if user_id not in tasks_by_user:
                tasks_by_user[user_id] = []
            
            tasks_by_user[user_id].append({
                "id": task_id,
                "title": task.get("title", "Sem título"),
                "status": task.get("status", "Desconhecido")
            })
                
            # Verificar se o user_id corresponde a um usuário existente
            if user_id not in user_map:
                tasks_with_invalid_user += 1
                logger.warning(f"Tarefa {task_id} tem user_id '{user_id}' que não corresponde a nenhum usuário")
        
        logger.info(f"Tarefas com user_id inválido: {tasks_with_invalid_user}")
        logger.info(f"Tarefas órfãs (sem usuário): {len(orphaned_tasks)}")
        
        # Mostrar número de tarefas por usuário
        logger.info("Distribuição de tarefas por usuário:")
        for user_id, user_tasks in tasks_by_user.items():
            username = user_map.get(user_id, "Usuário desconhecido")
            logger.info(f"  {username} (ID: {user_id}): {len(user_tasks)} tarefas")
            
        # Mostrar detalhes da primeira tarefa de cada usuário como exemplo
        logger.info("\nExemplo de tarefa por usuário:")
        for user_id, user_tasks in tasks_by_user.items():
            if user_tasks:
                username = user_map.get(user_id, "Usuário desconhecido")
                example_task = user_tasks[0]
                logger.info(f"  {username}: Tarefa '{example_task['title']}' (ID: {example_task['id']}, Status: {example_task['status']})")
        
        # Mostrar algumas tarefas órfãs
        if orphaned_tasks:
            logger.info("\nAlgumas tarefas órfãs:")
            for task in orphaned_tasks[:5]:  # Mostrar apenas as 5 primeiras
                logger.info(f"  Tarefa órfã: '{task['title']}' (ID: {task['id']}, Status: {task['status']})")
            
            if len(orphaned_tasks) > 5:
                logger.info(f"  ... e mais {len(orphaned_tasks) - 5} tarefas órfãs")
        
    except Exception as e:
        logger.error(f"Erro durante diagnóstico: {str(e)}")

async def main():
    """Função principal que executa o diagnóstico."""
    try:
        logger.info("Iniciando diagnóstico de atribuição de tarefas a usuários")
        await diagnose_task_user_assignments()
        logger.info("Diagnóstico concluído")
    finally:
        # Fechar conexão com o banco
        await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main()) 