#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para corrigir problemas de permissão de tarefas no banco de dados.
Este script pode ser usado para:
1. Converter IDs de ObjectId para string
2. Atribuir tarefas sem dono a usuários específicos
3. Corrigir permissões inconsistentes
"""

import sys
import asyncio
import logging
import os
from bson import ObjectId

# Adicionar o diretório raiz ao path do Python para permitir a importação dos módulos da aplicação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import connect_to_mongo, close_mongo_connection

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def convert_objectid_to_string():
    """
    Converte todos os user_ids que são ObjectId para string.
    """
    try:
        db = await connect_to_mongo()
        
        # Encontrar tarefas com user_id como ObjectId
        cursor = db["tasks"].find({"user_id": {"$type": "objectId"}})
        count = 0
        
        async for task in cursor:
            # Converter ObjectId para string
            await db["tasks"].update_one(
                {"_id": task["_id"]},
                {"$set": {"user_id": str(task["user_id"])}}
            )
            count += 1
            
        logger.info(f"Convertidos {count} user_ids de ObjectId para string em tarefas")
        
        # Mesmo processo para clientes
        cursor = db["clients"].find({"user_id": {"$type": "objectId"}})
        count = 0
        
        async for client in cursor:
            await db["clients"].update_one(
                {"_id": client["_id"]},
                {"$set": {"user_id": str(client["user_id"])}}
            )
            count += 1
            
        logger.info(f"Convertidos {count} user_ids de ObjectId para string em clientes")
        
    except Exception as e:
        logger.error(f"Erro durante conversão de ObjectId para string: {str(e)}")

async def assign_orphaned_tasks_to_user(username=None, user_id=None):
    """
    Atribui tarefas sem dono a um usuário específico.
    Ou passa o username ou o user_id.
    """
    try:
        db = await connect_to_mongo()
        
        # Encontrar o usuário alvo
        target_user = None
        if username:
            target_user = await db["users"].find_one({"username": username})
        elif user_id:
            target_user = await db["users"].find_one({"_id": ObjectId(user_id)})
        else:
            # Se nenhum usuário específico for fornecido, usar o primeiro admin
            target_user = await db["users"].find_one({"role": "admin"})
            
        if not target_user:
            logger.error("Não foi possível encontrar o usuário alvo")
            return
            
        target_user_id = str(target_user["_id"])
        target_username = target_user["username"]
        logger.info(f"Atribuindo tarefas órfãs ao usuário: {target_username} (ID: {target_user_id})")
        
        # Atribuir tarefas sem user_id (campo não existe)
        result1 = await db["tasks"].update_many(
            {"user_id": {"$exists": False}},
            {"$set": {"user_id": target_user_id}}
        )
        
        logger.info(f"Atribuídas {result1.modified_count} tarefas sem campo user_id ao usuário {target_username}")
        
        # Atribuir tarefas com user_id nulo
        result2 = await db["tasks"].update_many(
            {"user_id": None},
            {"$set": {"user_id": target_user_id}}
        )
        
        logger.info(f"Atribuídas {result2.modified_count} tarefas com user_id nulo ao usuário {target_username}")
        
        total_assigned = result1.modified_count + result2.modified_count
        logger.info(f"Total de {total_assigned} tarefas órfãs atribuídas ao usuário {target_username}")
        
    except Exception as e:
        logger.error(f"Erro durante atribuição de tarefas órfãs: {str(e)}")

async def fix_task_for_specific_user(task_id, user_id):
    """
    Corrige a propriedade de uma tarefa específica, atribuindo-a a um usuário específico.
    """
    try:
        db = await connect_to_mongo()
        
        # Verificar se a tarefa existe
        task = await db["tasks"].find_one({"_id": ObjectId(task_id)})
        if not task:
            logger.error(f"Tarefa com ID {task_id} não encontrada")
            return False
            
        # Verificar se o usuário existe
        user = await db["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"Usuário com ID {user_id} não encontrado")
            return False
            
        # Atualizar a tarefa
        await db["tasks"].update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"user_id": str(user_id)}}
        )
        
        logger.info(f"Tarefa {task_id} atribuída ao usuário {user['username']} (ID: {user_id})")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao corrigir tarefa específica: {str(e)}")
        return False
        

async def main():
    """
    Função principal que executa as correções necessárias.
    """
    try:
        logger.info("Iniciando correção de permissões de tarefas")
        
        # 1. Converter ObjectId para string
        await convert_objectid_to_string()
        
        # 2. Atribuir tarefas órfãs a um admin
        await assign_orphaned_tasks_to_user()
        
        # 3. Corrigir uma tarefa específica se necessário
        # Descomente e ajuste as linhas abaixo para corrigir tarefas específicas
        # task_id = "67d073fb538407847b665a50"  # ID da tarefa que precisa ser corrigida
        # user_id = "67caded723edd88d8deee258"  # ID do usuário que deve ser o proprietário
        # await fix_task_for_specific_user(task_id, user_id)
        
        logger.info("Correção de permissões concluída")
    finally:
        # Fechar conexão com o banco
        await close_mongo_connection()

if __name__ == "__main__":
    # Se argumentos específicos forem fornecidos na linha de comando
    if len(sys.argv) > 2 and sys.argv[1] == "fix_task":
        asyncio.run(fix_task_for_specific_user(sys.argv[2], sys.argv[3]))
    else:
        # Execução normal
        asyncio.run(main()) 