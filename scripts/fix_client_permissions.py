#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para corrigir problemas de permissão de clientes no banco de dados.
Este script pode ser usado para:
1. Converter IDs de ObjectId para string
2. Atribuir clientes sem dono a usuários específicos
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
        
        # Encontrar clientes com user_id como ObjectId
        cursor = db["clients"].find({"user_id": {"$type": "objectId"}})
        count = 0
        
        async for client in cursor:
            # Converter ObjectId para string
            await db["clients"].update_one(
                {"_id": client["_id"]},
                {"$set": {"user_id": str(client["user_id"])}}
            )
            count += 1
            
        logger.info(f"Convertidos {count} user_ids de ObjectId para string em clientes")
        
    except Exception as e:
        logger.error(f"Erro durante conversão de ObjectId para string: {str(e)}")

async def assign_orphaned_clients_to_user(username=None, user_id=None):
    """
    Atribui clientes sem dono a um usuário específico.
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
        logger.info(f"Atribuindo clientes órfãos ao usuário: {target_username} (ID: {target_user_id})")
        
        # Contar clientes sem user_id (campo não existe)
        clients_without_user = await db["clients"].count_documents({"user_id": {"$exists": False}})
        logger.info(f"Clientes sem campo user_id: {clients_without_user}")
        
        # Contar clientes com user_id nulo
        clients_with_null_user = await db["clients"].count_documents({"user_id": None})
        logger.info(f"Clientes com user_id nulo: {clients_with_null_user}")
        
        # Atribuir clientes sem user_id (campo não existe)
        result1 = await db["clients"].update_many(
            {"user_id": {"$exists": False}},
            {"$set": {"user_id": target_user_id}}
        )
        
        logger.info(f"Atribuídos {result1.modified_count} clientes sem campo user_id ao usuário {target_username}")
        
        # Atribuir clientes com user_id nulo
        result2 = await db["clients"].update_many(
            {"user_id": None},
            {"$set": {"user_id": target_user_id}}
        )
        
        logger.info(f"Atribuídos {result2.modified_count} clientes com user_id nulo ao usuário {target_username}")
        
        total_assigned = result1.modified_count + result2.modified_count
        logger.info(f"Total de {total_assigned} clientes órfãos atribuídos ao usuário {target_username}")
        
    except Exception as e:
        logger.error(f"Erro durante atribuição de clientes órfãos: {str(e)}")

async def fix_client_for_specific_user(client_id, user_id):
    """
    Corrige a propriedade de um cliente específico, atribuindo-o a um usuário específico.
    """
    try:
        db = await connect_to_mongo()
        
        # Verificar se o cliente existe
        client = await db["clients"].find_one({"_id": ObjectId(client_id)})
        if not client:
            logger.error(f"Cliente com ID {client_id} não encontrado")
            return False
            
        # Verificar se o usuário existe
        user = await db["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"Usuário com ID {user_id} não encontrado")
            return False
            
        # Atualizar o cliente
        await db["clients"].update_one(
            {"_id": ObjectId(client_id)},
            {"$set": {"user_id": str(user_id)}}
        )
        
        logger.info(f"Cliente {client_id} atribuído ao usuário {user['username']} (ID: {user_id})")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao corrigir cliente específico: {str(e)}")
        return False

async def diagnose_client_permissions():
    """
    Analisa todos os clientes no banco de dados para verificar problemas de permissão.
    """
    try:
        db = await connect_to_mongo()
        
        # Contar clientes sem user_id (campo não existe)
        clients_without_user = await db["clients"].count_documents({"user_id": {"$exists": False}})
        logger.info(f"Clientes sem campo user_id: {clients_without_user}")
        
        # Contar clientes com user_id nulo
        clients_with_null_user = await db["clients"].count_documents({"user_id": None})
        logger.info(f"Clientes com user_id nulo: {clients_with_null_user}")
        
        # Verificar clientes com user_id que não é string
        clients_with_objectid = await db["clients"].count_documents({"user_id": {"$type": "objectId"}})
        logger.info(f"Clientes com user_id como ObjectId: {clients_with_objectid}")
        
        # Obter todos os usuários
        users = await db["users"].find().to_list(100)
        user_map = {str(user["_id"]): user["username"] for user in users}
        
        # Contar clientes por usuário
        clients_by_user = {}
        async for client in db["clients"].find({"user_id": {"$exists": True, "$ne": None}}):
            user_id = client.get("user_id")
            if user_id not in clients_by_user:
                clients_by_user[user_id] = 0
            clients_by_user[user_id] += 1
            
        # Mostrar distribuição
        logger.info("Distribuição de clientes por usuário:")
        for user_id, count in clients_by_user.items():
            username = user_map.get(user_id, "Usuário desconhecido")
            logger.info(f"  {username} (ID: {user_id}): {count} clientes")
        
    except Exception as e:
        logger.error(f"Erro durante diagnóstico: {str(e)}")

async def main():
    """
    Função principal que executa as correções necessárias.
    """
    try:
        logger.info("Iniciando correção de permissões de clientes")
        
        # Diagnóstico inicial
        await diagnose_client_permissions()
        
        # 1. Converter ObjectId para string
        await convert_objectid_to_string()
        
        # 2. Atribuir clientes órfãos a um admin
        await assign_orphaned_clients_to_user()
        
        # 3. Diagnóstico final
        logger.info("Situação após correções:")
        await diagnose_client_permissions()
        
        logger.info("Correção de permissões concluída")
    finally:
        # Fechar conexão com o banco
        await close_mongo_connection()

if __name__ == "__main__":
    # Se argumentos específicos forem fornecidos na linha de comando
    if len(sys.argv) > 2 and sys.argv[1] == "fix_client":
        asyncio.run(fix_client_for_specific_user(sys.argv[2], sys.argv[3]))
    else:
        # Execução normal
        asyncio.run(main()) 