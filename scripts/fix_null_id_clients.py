#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para corrigir clientes com _id nulo no banco de dados MongoDB.
Este script identifica clientes com _id null, cria novos documentos com IDs válidos 
e remove os documentos inválidos.
"""

import sys
import asyncio
import logging
import os

# Adicionar o diretório raiz ao path do Python para permitir a importação dos módulos da aplicação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar as dependências do projeto
from app.core.database import Database

# Configurar logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def fix_null_id_clients():
    """
    Corrige clientes com _id null no banco de dados utilizando o método Database.check_and_fix_null_ids()
    """
    try:
        # Conectar ao banco de dados
        await Database.connect()
        logger.info("Conectado ao banco de dados com sucesso")
        
        # Usar o método da classe Database para corrigir clientes com _id null
        await Database.check_and_fix_null_ids()
        logger.info("Processo de correção de IDs nulos finalizado")
        
    except Exception as e:
        logger.error(f"Erro ao corrigir clientes com _id null: {str(e)}")
    finally:
        # Fechar conexão com o banco
        await Database.close()
        logger.info("Conexão com o banco de dados fechada")

async def main():
    """
    Função principal para executar o script
    """
    logger.info("Iniciando script de correção de clientes com _id null")
    await fix_null_id_clients()
    logger.info("Script concluído")

if __name__ == "__main__":
    asyncio.run(main()) 