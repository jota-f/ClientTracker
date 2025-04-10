from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    database = None
    
    def get_db_name(self) -> str:
        """Extract database name from MongoDB URL"""
        return settings.MONGODB_URL.split('/')[-1].split('?')[0]

    @classmethod
    async def connect(cls):
        cls.client = AsyncIOMotorClient(settings.MONGODB_URL)
        cls.database = cls.client["clienttracker"]

    @classmethod
    async def check_and_fix_null_ids(cls):
        """
        Verifica e corrige automaticamente documentos com _id null na coleção de clientes.
        Este método deve ser chamado na inicialização do servidor.
        """
        try:
            # Buscar clientes com _id null
            null_id_clients = await cls.database["clients"].find({"_id": None}).to_list(1000)
            
            if null_id_clients:
                logger.warning(f"Encontrados {len(null_id_clients)} clientes com _id null. Corrigindo automaticamente.")
                
                # Processar cada cliente
                for client in null_id_clients:
                    # Remover o _id null
                    client.pop("_id")
                    
                    # Verificar campos obrigatórios antes de inserir
                    required_fields = ["name", "company", "email"]
                    missing_fields = [field for field in required_fields if field not in client or not client[field]]
                    
                    if missing_fields:
                        logger.error(f"Cliente com campos obrigatórios ausentes não será migrado: {missing_fields}")
                        continue
                    
                    # Inserir o cliente com um novo ID
                    result = await cls.database["clients"].insert_one(client)
                    logger.info(f"Cliente {client.get('name')} migrado com novo ID: {result.inserted_id}")
                
                # Remover todos os clientes com _id null
                delete_result = await cls.database["clients"].delete_many({"_id": None})
                logger.info(f"Removidos {delete_result.deleted_count} clientes com _id null")
            else:
                logger.info("Nenhum cliente com _id null encontrado.")
                
        except Exception as e:
            logger.error(f"Erro ao verificar/corrigir clientes com _id null: {str(e)}")

    @classmethod
    async def close(cls):
        cls.client.close()

async def connect_to_mongo():
    """Create database connection."""
    logger.info("Connecting to MongoDB...")
    await Database.connect()
    try:
        # Verify the connection
        await Database.client.admin.command('ping')
        db_name = Database().get_db_name()
        logger.info(f"Connected to MongoDB. Database: {db_name}")
    except ConnectionFailure:
        logger.error("Server not available")
        raise

async def close_mongo_connection():
    """Close database connection."""
    logger.info("Closing MongoDB connection...")
    await Database.close()
    logger.info("MongoDB connection closed")

async def get_db():
    """Get the database instance."""
    return Database.database 