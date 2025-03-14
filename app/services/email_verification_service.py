import logging
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.core.config import settings
from app.core.database import Database
from bson import ObjectId
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Configuração do email
conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_TLS,
    MAIL_SSL_TLS=settings.MAIL_SSL,
    USE_CREDENTIALS=settings.USE_CREDENTIALS
)

class EmailVerificationService:
    def __init__(self):
        self.fastmail = FastMail(conf)
        self.db = Database.database

    async def send_verification_email(self, email: str, token: str) -> bool:
        """Envia email de verificação para o usuário."""
        try:
            logger.info(f"Enviando email de verificação para {email} com token {token[:10]}...")
            verification_link = f"{settings.APP_URL}/auth/verify-email/{token}"
            logger.info(f"Link de verificação: {verification_link}")

            # Criar o corpo do email
            html_content = f"""
            <h3>Bem-vindo ao Client Tracker!</h3>
            <p>Por favor, clique no link abaixo para verificar seu email:</p>
            <p><a href="{verification_link}">Verificar Email</a></p>
            <p>Se você não solicitou este email, por favor ignore.</p>
            """

            message = MessageSchema(
                subject="Verificação de Email - Client Tracker",
                recipients=[email],
                body=html_content,
                subtype="html"
            )

            # Enviar o email
            await self.fastmail.send_message(message)
            logger.info(f"Email de verificação enviado com sucesso para {email}")
            return True

        except Exception as e:
            logger.error(f"Erro ao enviar email de verificação para {email}")
            logger.error(f"Erro: {str(e)}")
            return False

    async def verify_email(self, token: str) -> bool:
        """Verifica o email do usuário usando o token."""
        try:
            # Buscar usuário com o token
            user = await self.db["users"].find_one({"verification_token": token})
            
            if not user:
                logger.warning(f"Token de verificação não encontrado: {token[:10]}...")
                return False
                
            # Verificar se o token expirou
            if user.get("verification_token_expires"):
                expires = user["verification_token_expires"]
                # Garantir que a data de expiração tenha timezone (se não tiver)
                if not hasattr(expires, 'tzinfo') or expires.tzinfo is None:
                    logger.debug(f"Convertendo data sem timezone para UTC: {expires}")
                    expires = expires.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                logger.debug(f"Comparando datas - Expiração: {expires}, Agora: {now}")
                
                if expires < now:
                    logger.warning(f"Token de verificação expirado para usuário: {user['email']}")
                    return False
            
            # Atualizar usuário como verificado
            logger.info(f"Atualizando usuário {user['email']} como verificado")
            result = await self.db["users"].update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "email_verified": True,
                        "verification_token": None,
                        "verification_token_expires": None,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Email verificado com sucesso para usuário: {user['email']}")
            else:
                logger.error(f"Falha ao atualizar status de verificação para usuário: {user['email']} (modified_count={result.modified_count})")
                # Verificar se o usuário já estava verificado
                current_user = await self.db["users"].find_one({"_id": user["_id"]})
                if current_user and current_user.get("email_verified"):
                    logger.info(f"O usuário {user['email']} já estava verificado")
                    return True
            
            return success
            
        except Exception as e:
            logger.error(f"Erro ao verificar email: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False 