import os
from jose import jwt
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from bson import ObjectId

from app.models.user import User, UserCreate, UserResponse
from app.core.database import Database
from app.models.notification_settings import NotificationSettings, NotificationPreference

logger = logging.getLogger(__name__)

# Configuração da criptografia de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuração do JWT
# Gera uma chave secreta de 32 bytes aleatórios se não estiver definida no ambiente
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# Log para garantir que estamos usando a mesma SECRET_KEY durante toda a execução
logger.info(f"Usando SECRET_KEY: {'do ambiente' if 'SECRET_KEY' in os.environ else 'gerada automaticamente'}")

class AuthService:
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Gera o hash de uma senha."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verifica se uma senha corresponde ao hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Cria um token JWT de acesso."""
        try:
            to_encode = data.copy()
            expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
            to_encode.update({"exp": expire})
            logger.info(f"Gerando token para usuário: {data.get('email')} com expiração: {expire}")
            token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
            logger.info(f"Token gerado com sucesso: {token[:20]}...")
            return token
        except Exception as e:
            logger.error(f"Erro ao gerar token: {str(e)}")
            raise

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decodifica e valida um token JWT."""
        try:
            if not token:
                logger.error("Token vazio recebido")
                raise ValueError("Token vazio")
                
            # Verificar se token é um objeto de requisição em vez de uma string
            if hasattr(token, '__class__') and not isinstance(token, str):
                logger.error(f"Token recebido não é uma string, mas {type(token)}")
                raise ValueError(f"Token inválido: tipo inesperado {type(token)}")
                
            # Log token de forma segura (primeiros 20 caracteres)
            token_prefix = token[:20] + "..." if len(token) > 20 else "[token_protegido]"
            logger.info(f"Tentando decodificar token: {token_prefix}")
            
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            logger.info(f"Token decodificado com sucesso. Payload: {payload}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.error("Token expirado")
            raise ValueError("Token expirado")
        except jwt.JWTClaimsError:
            logger.error("Claims inválidos no token")
            raise ValueError("Token com claims inválidos")
        except jwt.JWTError as e:
            logger.error(f"Erro ao decodificar token JWT: {str(e)}")
            raise ValueError(f"Token JWT inválido: {str(e)}")
        except Exception as e:
            logger.error(f"Erro desconhecido ao decodificar token: {str(e)}")
            raise ValueError(f"Erro ao validar token: {str(e)}")

    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[User]:
        """Autentica um usuário com email e senha."""
        try:
            logger.info(f"Tentando autenticar usuário: {email}")
            user_dict = await Database.database["users"].find_one({"email": email})
            
            if not user_dict:
                logger.warning(f"Usuário não encontrado: {email}")
                return None
                
            # Verificar o formato de _id
            if "_id" in user_dict:
                if isinstance(user_dict["_id"], ObjectId):
                    user_dict["_id"] = str(user_dict["_id"])
                    logger.info(f"ObjectId convertido para string: {user_dict['_id']}")
                else:
                    logger.warning(f"_id não é um ObjectId: {type(user_dict['_id'])}, valor: {user_dict['_id']}")
            else:
                logger.warning("Campo _id não encontrado no documento do usuário")
                
            # Converte o ObjectId para string antes de passar para o parse_obj
            user = User.parse_obj(user_dict)
            logger.info(f"Usuário encontrado: {user.email}, ID: {user.id}")
            
            if not AuthService.verify_password(password, user.hashed_password):
                logger.warning(f"Senha incorreta para usuário: {email}")
                return None
                
            # Atualiza a data do último login
            now = datetime.now(timezone.utc)
            await Database.database["users"].update_one(
                {"_id": ObjectId(user.id)},
                {"$set": {"last_login": now, "updated_at": now}}
            )
            logger.info(f"Login bem-sucedido para usuário: {email}")
            
            return user
        except Exception as e:
            logger.error(f"Erro ao autenticar usuário: {str(e)}")
            raise  # Propaga o erro para poder ser tratado adequadamente

    @staticmethod
    async def create_user(user_create: UserCreate) -> Optional[UserResponse]:
        """Cria um novo usuário."""
        try:
            # Verifica se já existe um usuário com o mesmo email ou username
            existing_user = await Database.database["users"].find_one({
                "$or": [
                    {"email": user_create.email},
                    {"username": user_create.username}
                ]
            })
            
            if existing_user:
                if existing_user.get("email") == user_create.email:
                    raise ValueError("Email já registrado")
                else:
                    raise ValueError("Nome de usuário já existe")
            
            # Gerar token de verificação
            verification_token = secrets.token_urlsafe(32)
            verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)
            logger.info(f"Token de verificação gerado para {user_create.email}: {verification_token[:10]}...")
            
            now = datetime.now(timezone.utc)
            
            # Prepara o documento do usuário
            user_dict = {
                "username": user_create.username,
                "email": user_create.email,
                "hashed_password": AuthService.get_password_hash(user_create.password),
                "full_name": user_create.full_name,
                "role": "user",
                "notification_preference": "email",
                "calendar_integration": {
                    "type": "none",
                    "enabled": False
                },
                "email_verified": False,
                "verification_token": verification_token,
                "verification_token_expires": verification_expires,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            
            logger.info(f"Inserindo novo usuário no banco: {user_create.email}")
            result = await Database.database["users"].insert_one(user_dict)
            
            # Retorna o usuário criado (sem a senha)
            created_user = await Database.database["users"].find_one({"_id": result.inserted_id})
            user_response = UserResponse(
                id=str(created_user["_id"]),
                username=created_user["username"],
                email=created_user["email"],
                full_name=created_user.get("full_name"),
                role=created_user["role"],
                notification_preference=created_user["notification_preference"],
                calendar_integration=created_user["calendar_integration"],
                email_verified=created_user["email_verified"],
                is_active=created_user["is_active"],
                created_at=created_user["created_at"],
                updated_at=created_user["updated_at"],
                last_login=created_user.get("last_login")
            )
            
            # Enviar email de verificação
            from app.services.email_verification_service import EmailVerificationService
            email_service = EmailVerificationService()
            
            # Enviar o email de verificação
            sent = await email_service.send_verification_email(user_create.email, verification_token)
            
            if sent:
                logger.info(f"Email de verificação enviado com sucesso para {user_create.email}")
            else:
                logger.error(f"Falha ao enviar email de verificação para {user_create.email}")
            
            return user_response
        except Exception as e:
            logger.error(f"Erro ao criar usuário: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[User]:
        """Obtém um usuário pelo ID."""
        try:
            logger.info(f"Buscando usuário com ID (formato original): '{user_id}'")
            
            # Verificar se é um ObjectId válido
            if user_id and user_id.lower() != 'none':
                object_id = ObjectId(user_id)
                logger.info(f"ObjectId válido criado: {object_id}")
                
                user_dict = await Database.database["users"].find_one({"_id": object_id})
                if not user_dict:
                    logger.warning(f"Usuário não encontrado para ID: {user_id}")
                    return None
                    
                # Log do usuário encontrado
                logger.info(f"Usuário encontrado: {user_dict.get('email')}, ID: {user_dict.get('_id')}")
                
                # Verificar o formato de _id
                if "_id" in user_dict:
                    if isinstance(user_dict["_id"], ObjectId):
                        user_dict["_id"] = str(user_dict["_id"])
                        logger.info(f"ObjectId convertido para string: {user_dict['_id']}")
                    else:
                        logger.warning(f"_id não é um ObjectId: {type(user_dict['_id'])}, valor: {user_dict['_id']}")
                else:
                    logger.warning("Campo _id não encontrado no documento do usuário")
                
                # Converte o ObjectId para string antes de passar para o parse_obj
                return User.parse_obj(user_dict)
            else:
                logger.error(f"ID de usuário inválido: '{user_id}'")
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar usuário por ID: {str(e)}")
            return None

    @staticmethod
    async def get_user_by_email(email: str) -> Optional[User]:
        """Obtém um usuário pelo email."""
        try:
            user_dict = await Database.database["users"].find_one({"email": email})
            if not user_dict:
                return None
            return User.parse_obj(user_dict)
        except Exception as e:
            logger.error(f"Erro ao buscar usuário por email: {str(e)}")
            return None

    @staticmethod
    async def update_user(user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """Atualiza os dados de um usuário."""
        try:
            # Remove campos vazios e None
            clean_data = {k: v for k, v in update_data.items() if v is not None}
            
            if not clean_data:
                return await AuthService.get_user_by_id(user_id)
                
            # Adiciona a data de atualização
            clean_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await Database.database["users"].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": clean_data}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                return await AuthService.get_user_by_id(user_id)
            return None
        except Exception as e:
            logger.error(f"Erro ao atualizar usuário: {str(e)}")
            return None

    @staticmethod
    async def change_password(user_id: str, current_password: str, new_password: str) -> bool:
        """Altera a senha de um usuário."""
        try:
            user = await AuthService.get_user_by_id(user_id)
            
            if not user or not AuthService.verify_password(current_password, user.hashed_password):
                return False
                
            hashed_password = AuthService.get_password_hash(new_password)
            now = datetime.now(timezone.utc)
            
            result = await Database.database["users"].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "hashed_password": hashed_password,
                    "updated_at": now
                }}
            )
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao alterar senha: {str(e)}")
            return False 