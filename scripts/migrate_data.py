"""
Script para migrar tarefas e clientes existentes para o novo modelo com user_id
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração do MongoDB
MONGODB_URL = "mongodb://localhost:27017"
DB_NAME = "clienttracker"

async def migrate_data():
    try:
        # Conectar ao MongoDB
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client[DB_NAME]
        logger.info("Conectado ao MongoDB")

        # Encontrar o primeiro usuário
        first_user = await db.users.find_one()
        if not first_user:
            logger.error("Nenhum usuário encontrado!")
            return

        user_id = str(first_user["_id"])
        logger.info(f"Usando usuário ID: {user_id}")

        # Atualizar tarefas
        update_result = await db.tasks.update_many(
            {"user_id": {"$exists": False}},
            {"$set": {"user_id": user_id}}
        )
        logger.info(f"Atualizadas {update_result.modified_count} tarefas")

        # Atualizar clientes
        update_result = await db.clients.update_many(
            {"user_id": {"$exists": False}},
            {"$set": {"user_id": user_id}}
        )
        logger.info(f"Atualizados {update_result.modified_count} clientes")

        logger.info("Migração concluída com sucesso!")

    except Exception as e:
        logger.error(f"Erro durante a migração: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(migrate_data()) 