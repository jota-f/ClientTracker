#!/usr/bin/env python3
"""
Script para migrar tarefas e clientes existentes para associá-los a usuários.
"""
import asyncio
import logging
import sys
import os

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Adicionar o diretório raiz ao PYTHONPATH para resolver importações
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar dependências do projeto
from app.core.database import get_db
from bson import ObjectId

async def migrate_data():
    """Migra tarefas e clientes para associá-los a usuários."""
    logger.info("Iniciando migração de dados...")
    
    try:
        # Obter conexão com o banco de dados
        db = await get_db()
        logger.info("Conexão com o banco de dados estabelecida com sucesso.")
        
        # Obter o primeiro usuário
        first_user = await db.users.find_one()
        
        if not first_user:
            logger.error("Nenhum usuário encontrado. Abortando migração.")
            return
        
        user_id = str(first_user["_id"])
        user_email = first_user.get("email", "sem email")
        logger.info(f"Usando o usuário: {user_email} (ID: {user_id}) como proprietário.")
        
        # Migrar tarefas
        task_count = 0
        async for task in db.tasks.find({"user_id": {"$exists": False}}):
            await db.tasks.update_one(
                {"_id": task["_id"]},
                {"$set": {"user_id": user_id}}
            )
            task_count += 1
        
        logger.info(f"Migradas {task_count} tarefas.")
        
        # Migrar clientes
        client_count = 0
        async for client in db.clients.find({"user_id": {"$exists": False}}):
            await db.clients.update_one(
                {"_id": client["_id"]},
                {"$set": {"user_id": user_id}}
            )
            client_count += 1
        
        logger.info(f"Migrados {client_count} clientes.")
        logger.info("Migração concluída com sucesso!")
    
    except Exception as e:
        logger.error(f"Erro durante a migração: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate_data()) 