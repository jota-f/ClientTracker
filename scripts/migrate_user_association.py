import asyncio
from bson import ObjectId
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_data():
    from app.core.database import get_db
    
    logger.info("Iniciando migração de tarefas e clientes...")
    
    db = await get_db()
    
    # Obter primeiro usuário do sistema (ou definir um específico)
    first_user = await db.users.find_one()
    
    if not first_user:
        logger.error("Nenhum usuário encontrado no sistema. Abortando migração.")
        return
    
    user_id = str(first_user["_id"])
    logger.info(f"Associando itens ao usuário: {first_user.get('email')} (ID: {user_id})")
    
    # Migrar tarefas
    tasks_count = 0
    async for task in db.tasks.find({"user_id": {"$exists": False}}):
        await db.tasks.update_one(
            {"_id": task["_id"]},
            {"$set": {"user_id": user_id}}
        )
        tasks_count += 1
    
    logger.info(f"Migradas {tasks_count} tarefas.")
    
    # Migrar clientes
    clients_count = 0
    async for client in db.clients.find({"user_id": {"$exists": False}}):
        await db.clients.update_one(
            {"_id": client["_id"]},
            {"$set": {"user_id": user_id}}
        )
        clients_count += 1
    
    logger.info(f"Migrados {clients_count} clientes.")
    logger.info("Migração concluída com sucesso!")

if __name__ == "__main__":
    asyncio.run(migrate_data()) 