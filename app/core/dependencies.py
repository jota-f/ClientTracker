import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.models.user import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Define o esquema OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Obtém o usuário atual a partir do token JWT.
    Raises:
        HTTPException: Se o token for inválido ou o usuário não for encontrado.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Log da requisição
    logger.info("Verificando autenticação (sem contexto de requisição)")
    
    if not token:
        logger.warning("Token não fornecido")
        raise credentials_exception
        
    try:
        # Decodifica o token
        logger.info("Tentando decodificar token...")
        payload = AuthService.decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.error("Token não contém ID do usuário")
            raise credentials_exception
            
        logger.info(f"Token decodificado com sucesso para usuário ID: {user_id}")
    except (JWTError, ValueError) as e:
        logger.error(f"Erro ao decodificar token: {str(e)}")
        raise credentials_exception
        
    # Busca o usuário no banco de dados
    logger.info(f"Buscando usuário com ID: {user_id}")
    user = await AuthService.get_user_by_id(user_id)
    if user is None:
        logger.error(f"Usuário não encontrado com ID: {user_id}")
        raise credentials_exception
        
    if not user.is_active:
        logger.warning(f"Tentativa de acesso com usuário inativo: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )
        
    logger.info(f"Usuário autenticado com sucesso: {user.email}")
    return user

async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Verifica se o usuário atual é um administrador.
    Raises:
        HTTPException: Se o usuário não for um administrador.
    """
    if current_user.role != "admin":
        logger.warning(f"Tentativa de acesso admin por usuário não autorizado: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso não autorizado. Privilégios de administrador necessários."
        )
    logger.info(f"Acesso admin autorizado para: {current_user.email}")
    return current_user

async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[User]:
    """
    Tenta obter o usuário atual, mas não falha se não houver token ou o token for inválido.
    Returns:
        User ou None
    """
    logger.info("Tentando obter usuário opcional (sem contexto de requisição)")
    
    if not token:
        logger.info("Nenhum token fornecido para autenticação opcional")
        return None
        
    try:
        logger.info("Tentando decodificar token para usuário opcional...")
        payload = AuthService.decode_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            logger.warning("Token não contém ID do usuário")
            return None
            
        user = await AuthService.get_user_by_id(user_id)
        if not user:
            logger.warning(f"Usuário não encontrado com ID: {user_id}")
            return None
            
        if not user.is_active:
            logger.warning(f"Usuário inativo encontrado: {user_id}")
            return None
            
        logger.info(f"Usuário opcional autenticado: {user.email}")
        return user
    except Exception as e:
        logger.warning(f"Erro ao obter usuário opcional: {str(e)}")
        return None 