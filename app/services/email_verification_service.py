import logging
from app.core.config import settings
from app.core.database import Database
from app.services.notification_service import NotificationService
from bson import ObjectId
from datetime import datetime, timezone
import traceback

logger = logging.getLogger(__name__)


class EmailVerificationService:
    def __init__(self):
        self.notification_service = NotificationService()
        self.db = Database.database

    async def send_verification_email(self, email: str, token: str) -> bool:
        """Envia email de verificação para o usuário usando o NotificationService nativo."""
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

            subject = "Verificação de Email - Client Tracker"
            success = await self.notification_service.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content
            )

            if success:
                logger.info(f"Email de verificação enviado com sucesso para {email}")
            else:
                logger.warning(f"Falha ao despachar email de verificação para {email}")
            return success

        except Exception as e:
            logger.error(f"Erro ao enviar email de verificação para {email}")
            logger.error(f"Erro: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def verify_email(self, token: str) -> bool:
        """Verifica o email do usuário usando o token."""
        try:
            logger.info(f"Iniciando verificação de email com token: {token[:10]}...")

            # Buscar usuário com o token
            user = await self.db["users"].find_one({"verification_token": token})

            if not user:
                logger.warning("Token de verificação não encontrado ou inválido")
                return False

            logger.info(f"Usuário encontrado: {user.get('email')} para token: {token[:10]}...")

            # Verificar se o token expirou
            if user.get("verification_token_expires"):
                expires = user["verification_token_expires"]
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
                current_user = await self.db["users"].find_one({"_id": user["_id"]})
                if current_user and current_user.get("email_verified"):
                    logger.info(f"O usuário {user['email']} já estava verificado")
                    return True

            return success

        except Exception as e:
            logger.error(f"Erro ao verificar email: {str(e)}")
            logger.error(traceback.format_exc())
            return False