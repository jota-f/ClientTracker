#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("fix-tasks-without-user")

# Adicionar o diretório pai ao path para importar módulos da aplicação
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def connect_to_mongo():
    """Conecta ao MongoDB usando a string de conexão do ambiente."""
    from app.core.config import settings
    
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = mongo_client.get_default_database()
    logger.info(f"Conectado ao MongoDB: {settings.MONGODB_URL}")
    return db

async def identify_tasks_without_user():
    """Identifica tarefas sem usuário atribuído."""
    db = await connect_to_mongo()
    
    # Encontrar tarefas sem user_id ou com user_id vazio
    query = {"$or": [
        {"user_id": None},
        {"user_id": ""},
        {"user_id": {"$exists": False}}
    ]}
    
    tasks = await db["tasks"].find(query).to_list(length=None)
    
    logger.info(f"Encontradas {len(tasks)} tarefas sem usuário atribuído")
    return tasks

async def list_all_users():
    """Lista todos os usuários disponíveis."""
    db = await connect_to_mongo()
    
    users = await db["users"].find().to_list(length=None)
    logger.info(f"Encontrados {len(users)} usuários no sistema")
    
    return users

async def assign_user_to_task(task_id, user_id):
    """Atribui um usuário a uma tarefa específica."""
    db = await connect_to_mongo()
    
    try:
        # Atualizar a tarefa
        result = await db["tasks"].update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {
                "user_id": user_id,
                "updated_at": datetime.now()
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"Tarefa {task_id} atribuída ao usuário {user_id}")
            return True
        else:
            logger.warning(f"Nenhuma modificação na tarefa {task_id}")
            return False
    except Exception as e:
        logger.error(f"Erro ao atribuir usuário {user_id} à tarefa {task_id}: {e}")
        return False

async def main():
    """Função principal que executa o script."""
    try:
        # Listar tarefas sem usuário
        tasks_without_user = await identify_tasks_without_user()
        
        if not tasks_without_user:
            logger.info("Não há tarefas sem usuário atribuído. Nada a fazer.")
            return
        
        # Listar usuários disponíveis
        users = await list_all_users()
        
        if not users:
            logger.error("Não foram encontrados usuários no sistema. Não é possível atribuir tarefas.")
            return
        
        # Exibir menu de opções
        print("\n--- CORREÇÃO DE TAREFAS SEM USUÁRIO ---\n")
        print("Escolha uma opção:")
        print("1. Deixar as tarefas sem usuário (permite que qualquer usuário edite)")
        print("2. Atribuir todas as tarefas sem usuário a um usuário específico")
        print("3. Revisar cada tarefa individualmente")
        
        option = input("\nOpção: ").strip()
        
        if option == "1":
            logger.info("As tarefas serão mantidas sem usuário atribuído, permitindo acesso a todos")
            return
        
        elif option == "2":
            # Mostrar lista de usuários
            print("\nUsuários disponíveis:")
            for i, user in enumerate(users, 1):
                print(f"{i}. {user.get('email')} - {user.get('username')} (ID: {user['_id']})")
            
            user_index = int(input("\nSelecione o número do usuário: ")) - 1
            
            if 0 <= user_index < len(users):
                selected_user = users[user_index]
                user_id = str(selected_user["_id"])
                
                # Confirmar ação
                confirm = input(f"\nAtribuir TODAS as {len(tasks_without_user)} tarefas ao usuário {selected_user.get('email')}? (s/n): ").lower()
                
                if confirm == "s":
                    success_count = 0
                    for task in tasks_without_user:
                        if await assign_user_to_task(str(task["_id"]), user_id):
                            success_count += 1
                    
                    logger.info(f"Processo concluído. {success_count} de {len(tasks_without_user)} tarefas atribuídas ao usuário {selected_user.get('email')}")
                else:
                    logger.info("Operação cancelada pelo usuário")
            else:
                logger.error("Índice de usuário inválido")
        
        elif option == "3":
            # Mostrar lista de usuários para referência
            print("\nUsuários disponíveis:")
            for i, user in enumerate(users, 1):
                print(f"{i}. {user.get('email')} - {user.get('username')} (ID: {user['_id']})")
            
            # Processar cada tarefa individualmente
            for task in tasks_without_user:
                task_id = str(task["_id"])
                task_title = task.get("title", "Sem título")
                
                print(f"\n--- Tarefa: {task_title} (ID: {task_id}) ---")
                print("Opções:")
                print("0. Deixar esta tarefa sem usuário")
                print("1-N. Selecionar usuário pelo número")
                print("s. Pular esta tarefa")
                print("q. Sair do processamento")
                
                choice = input("\nEscolha uma opção: ").lower()
                
                if choice == "q":
                    logger.info("Processamento interrompido pelo usuário")
                    break
                
                if choice == "s":
                    logger.info(f"Tarefa {task_id} pulada")
                    continue
                
                if choice == "0":
                    logger.info(f"Tarefa {task_id} mantida sem usuário")
                    continue
                
                try:
                    user_index = int(choice) - 1
                    if 0 <= user_index < len(users):
                        selected_user = users[user_index]
                        user_id = str(selected_user["_id"])
                        
                        if await assign_user_to_task(task_id, user_id):
                            logger.info(f"Tarefa {task_id} atribuída ao usuário {selected_user.get('email')}")
                        else:
                            logger.error(f"Falha ao atribuir tarefa {task_id}")
                    else:
                        logger.error("Índice de usuário inválido")
                except ValueError:
                    logger.error("Entrada inválida. Pulando esta tarefa.")
        
        else:
            logger.error("Opção inválida")
    
    except Exception as e:
        logger.error(f"Erro durante a execução: {e}")
    
    logger.info("Script concluído")

if __name__ == "__main__":
    asyncio.run(main()) 