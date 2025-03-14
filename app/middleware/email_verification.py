import logging
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.dependencies import get_current_user_optional

logger = logging.getLogger(__name__)

class EmailVerificationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Lista de caminhos que não exigem verificação de e-mail
        exempt_paths = [
            "/login", 
            "/register", 
            "/api/auth/login", 
            "/api/auth/register", 
            "/api/auth/check",
            "/auth/verify-email",
            "/auth/verification-success",
            "/auth/verification-error",
            "/auth/verification-pending",
            "/static",
            "/favicon.ico",
            "/api/auth/resend-verification",
            "/health"
        ]
        
        # Verifica se o caminho atual está na lista de isentos
        current_path = request.url.path
        logger.info(f"Verificando acesso ao caminho: {current_path}")
        
        # Verifica se é um caminho isento
        is_exempt = False
        for exempt_path in exempt_paths:
            if current_path.startswith(exempt_path):
                logger.info(f"Caminho isento de verificação: {current_path}")
                is_exempt = True
                break
        
        if is_exempt:
            return await call_next(request)
        
        try:
            # Obter o usuário atual
            user = await get_current_user_optional(request)
            
            if user:
                logger.info(f"Usuário autenticado: {user.email}, verificado: {user.email_verified}")
                
                # Verifica se o e-mail está verificado
                if not user.email_verified:
                    logger.warning(f"BLOQUEANDO acesso para usuário não verificado: {user.email}")
                    # Redireciona para a página de verificação pendente ou retorna erro JSON para APIs
                    if current_path.startswith("/api/"):
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Seu e-mail não foi verificado. Por favor, verifique seu e-mail antes de acessar o sistema."}
                        )
                    else:
                        logger.info(f"Redirecionando para página de verificação pendente")
                        return RedirectResponse(
                            url="/auth/verification-pending",
                            status_code=302
                        )
                else:
                    logger.info(f"Usuário verificado, permitindo acesso: {user.email}")
            else:
                logger.info(f"Nenhum usuário autenticado para caminho: {current_path}")
            
            return await call_next(request)
            
        except Exception as e:
            logger.error(f"Erro no middleware de verificação de e-mail: {str(e)}")
            return await call_next(request) 