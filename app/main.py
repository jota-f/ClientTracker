from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks, Form, Cookie, Response, Query, Header
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api.routes import clients, tasks, auth, calendar, notification, users
from app.routers import calendar_router
from app.models.client import Client
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.user import User
from app.services.client_service import ClientService
from app.services.task_service import TaskService
from app.services.dashboard_service import DashboardService
from app.services.auth_service import AuthService
from app.services.scheduler_service import SchedulerService
from app.services.notification_service import NotificationService
from app.core.dependencies import get_current_user, get_optional_user
import logging
from datetime import datetime, timezone, timedelta
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Dict, Any, Optional
from app.middleware.email_verification import EmailVerificationMiddleware
from app.jobs.contact_schedule_job import start_contact_schedule_job
from app.jobs.notification_job import start_notification_job
import asyncio
from app.services.user_service import UserService
from app.core.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Authentication middleware for templates
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            path = request.url.path
            
            # Lista de rotas públicas que não necessitam de autenticação
            public_paths = [
                "/api/auth/login",
                "/api/auth/register",
                "/api/auth/verify-email",
                "/api/auth/reset-password",
                "/api/auth/reset-password-confirm",
                "/api/auth/resend-verification",
                "/login",
                "/register",
                "/forgot-password",
                "/auth-debug",
                "/auth-test",
                "/static",
                "/health",
                "/docs",
                "/openapi.json",
                "/auth/verification-success",
                "/auth/verification-error",
                "/auth/verification-pending",
                "/auth/verify-email",
                "/calendar/google/callback",
                "/landing"
                "/scripts/fix_tasks_without_user.py"  # Adicionando landing como rota pública
            ]
            
            # Se for um caminho público, ignora completamente a verificação
            if any(path.startswith(public_path) for public_path in public_paths):
                logger.info(f"Caminho público ignorado pelo AuthMiddleware: {path}")
                return await call_next(request)
            
            # Para caminhos protegidos, verifica a autenticação
            auth_header = request.headers.get("Authorization")
            auth_cookie = request.cookies.get("Authorization")
            auth_meta = request.headers.get("x-auth-token")
            
            # Tenta obter o token de diferentes fontes e remove o prefixo 'Bearer ' se existir
            token = None
            if auth_header:
                token = auth_header.replace('Bearer ', '')
            elif auth_cookie:
                token = auth_cookie.replace('Bearer ', '')
            elif auth_meta:
                token = auth_meta.replace('Bearer ', '')
            
            # Se não encontrou token em nenhum lugar
            if not token:
                if path.startswith('/api/'):
                    return JSONResponse(status_code=401, content={"detail": "Não autorizado"})
                else:
                    return RedirectResponse(url=f"/login?next={request.url.path}", status_code=302)
            
            # Adicione no middleware antes da verificação do token
            logger.debug(f"Token antes da verificação: {token[:10]}...")  # Mostra apenas os primeiros 10 caracteres
            
            # Se encontrou token, verifica se é válido
            try:
                AuthService.decode_token(token)  # Agora passamos o token limpo
                # Adiciona o token aos headers para as próximas etapas
                request._headers = {**request.headers, "Authorization": f"Bearer {token}"}
                request.scope["headers"] = [
                    (key.lower().encode(), value.encode()) 
                    for key, value in request._headers.items()
                ]
            except Exception as e:
                logger.error(f"Token inválido: {str(e)}")
                if path.startswith('/api/'):
                    return JSONResponse(status_code=401, content={"detail": "Token inválido"})
                else:
                    response = RedirectResponse(url="/login?error=invalid_token", status_code=302)
                    response.set_cookie(key="Authorization", value="", max_age=0)
                    return response
            
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Erro no middleware de autenticação: {str(e)}")
            return await call_next(request)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configure templates
templates = Jinja2Templates(directory="app/templates")

# Events
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up...")
    
    try:
        # Inicializar conexão com o banco de dados
        await connect_to_mongo()
        
        # Verificar e corrigir clientes com _id null na inicialização
        await Database.check_and_fix_null_ids()
        logger.info("Verificação e correção de clientes com ID nulo concluída")
        
        # Inicializar configurações de notificação para usuários existentes
        await UserService.initialize_notification_settings()
        
        # Garantir que todas as datas dos clientes tenham timezone
        updated_clients = await ClientService.ensure_client_dates_have_timezone()
        logger.info(f"Timezone atualizado para {updated_clients} clientes")
        
        # Iniciar scheduler
        scheduler = SchedulerService()
        await scheduler.start()
        
        # Iniciar job de notificações
        asyncio.create_task(start_notification_job())
        
        logger.info("Aplicação iniciada com sucesso")
    except Exception as e:
        logger.error(f"Erro durante a inicialização da aplicação: {str(e)}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")
    
    # Desligar o serviço de agendamento
    scheduler = SchedulerService()
    scheduler.shutdown()
    
    await close_mongo_connection()

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}

# Include routers
app.include_router(
    clients.router,
    prefix="/api/v1/clients",
    tags=["clients"]
)

app.include_router(
    tasks.router,
    prefix="/api/v1/tasks",
    tags=["tasks"]
)

app.include_router(
    auth.router,
    prefix="/api/auth",
    tags=["auth"]
)

# Debug log para verificar se o router de users está sendo registrado
try:
    logger.info(f"Registrando router de users. Router válido: {users.router is not None}")
    logger.info(f"Rotas no router de users: {[route.path for route in users.router.routes]}")
except Exception as e:
    logger.error(f"Erro ao registrar router de users: {str(e)}")

app.include_router(
    users.router,
    prefix="/api/users",
    tags=["users"]
)

app.include_router(
    calendar.router,
    prefix="/api/v1/calendar",
    tags=["calendar"]
)

app.include_router(
    notification.router,
    prefix="/api/v1/notifications",
    tags=["notifications"]
)

# Incluir roteadores web
app.include_router(calendar_router.router)

# Add email verification middleware first
app.add_middleware(EmailVerificationMiddleware)

# Add auth middleware
app.add_middleware(AuthMiddleware)

# Root route
@app.get("/")
async def index(request: Request, current_user: User = Depends(get_current_user)):
    # Obter métricas avançadas para o usuário autenticado
    metrics = await DashboardService.get_advanced_dashboard_metrics(user_id=str(current_user.id))
    
    context = {
        "request": request,
        "metrics": metrics,
        "user": current_user
    }
    return templates.TemplateResponse("dashboard.html", context)

# Dashboard avançado
@app.get("/dashboard")
async def advanced_dashboard(request: Request, current_user: User = Depends(get_current_user)):
    # Obter métricas avançadas para o usuário autenticado
    metrics = await DashboardService.get_advanced_dashboard_metrics(user_id=str(current_user.id))
    
    context = {
        "request": request,
        "metrics": metrics,
        "user": current_user
    }
    return templates.TemplateResponse("dashboard.html", context)

# Revisão semanal
@app.get("/weekly-review")
async def weekly_review(request: Request, current_user: User = Depends(get_current_user)):
    # Obter métricas de revisão semanal para o usuário autenticado
    metrics = await DashboardService.get_weekly_review_metrics(user_id=str(current_user.id))
    
    context = {
        "request": request,
        "metrics": metrics,
        "user": current_user
    }
    return templates.TemplateResponse("weekly_review.html", context)

# Auth routes
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/landing")
async def landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/profile")
async def profile_page(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("profile.html", {"request": request, "user": current_user})

@app.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@app.get("/auth-debug")
async def auth_debug_page(request: Request):
    """
    Página de diagnóstico de autenticação.
    """
    return templates.TemplateResponse("auth_debug.html", {"request": request})

# Client routes
@app.get("/clients")
async def list_clients_page(request: Request, current_user: User = Depends(get_current_user)):
    # Obter apenas clientes do usuário autenticado
    clients = await ClientService.get_all_clients(user_id=str(current_user.id))
    return templates.TemplateResponse(
        "clients.html",
        {"request": request, "clients": clients, "user": current_user}
    )

@app.get("/clients/new")
async def new_client_page(request: Request, current_user: User = Depends(get_current_user)):
    logger.info("Acessando a página de novo cliente")
    return templates.TemplateResponse(
        "client_form.html",
        {"request": request, "client": None, "user": current_user}
    )

@app.get("/clients/{client_id}")
async def client_detail_page(request: Request, client_id: str, current_user: User = Depends(get_current_user)):
    client = await ClientService.get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    # Verificar se o cliente pertence ao usuário atual
    if client.user_id and client.user_id != str(current_user.id):
        logger.warning(f"Tentativa de acesso não autorizado ao cliente {client_id} pelo usuário {current_user.id}")
        raise HTTPException(status_code=403, detail="Você não tem permissão para acessar este cliente")
        
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        "client_detail.html",
        {"request": request, "client": client, "user": current_user, "now": now, "timedelta": timedelta}
    )

@app.get("/clients/{client_id}/edit")
async def edit_client_page(request: Request, client_id: str, current_user: User = Depends(get_current_user)):
    # Verificação explícita para valores inválidos de client_id
    if client_id.lower() in ['none', 'null', 'undefined', '']:
        logger.warning(f"Tentativa de editar cliente com ID inválido: {client_id}")
        # Redirecionar para a lista de clientes
        return RedirectResponse(url="/clients", status_code=302)
        
    client = await ClientService.get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    # Verificar se o cliente pertence ao usuário atual
    if client.user_id and client.user_id != str(current_user.id):
        logger.warning(f"Tentativa de edição não autorizada do cliente {client_id} pelo usuário {current_user.id}")
        raise HTTPException(status_code=403, detail="Você não tem permissão para editar este cliente")
        
    return templates.TemplateResponse(
        "client_form.html",
        {"request": request, "client": client, "user": current_user}
    )

# Task routes
@app.get("/tasks")
async def list_tasks_page(request: Request, current_user: User = Depends(get_current_user)):
    # Obter apenas tarefas do usuário autenticado
    tasks = await TaskService.get_all_tasks(user_id=str(current_user.id))
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        "tasks.html",
        {"request": request, "tasks": tasks, "now": now, "user": current_user}
    )

@app.get("/tasks/kanban")
async def kanban_board_page(request: Request, current_user: User = Depends(get_current_user)):
    # Obter apenas tarefas do usuário autenticado
    tasks = await TaskService.get_all_tasks(user_id=str(current_user.id))
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        "kanban.html",
        {"request": request, "tasks": tasks, "now": now, "user": current_user}
    )

@app.get("/tasks/eisenhower")
async def eisenhower_matrix_page(request: Request, current_user: User = Depends(get_current_user)):
    # Obter matriz com tarefas do usuário autenticado
    matrix = await TaskService.get_eisenhower_matrix(user_id=str(current_user.id))
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        "priority_matrix.html",
        {"request": request, "matrix": matrix, "now": now, "user": current_user}
    )

@app.get("/tasks/priority-matrix")
async def priority_matrix_page(request: Request, current_user: User = Depends(get_current_user)):
    # Obter matriz com tarefas do usuário autenticado
    matrix = await TaskService.get_eisenhower_matrix(user_id=str(current_user.id))
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        "priority_matrix.html",
        {"request": request, "matrix": matrix, "now": now, "user": current_user}
    )

@app.get("/tasks/new")
async def new_task_page(request: Request, current_user: User = Depends(get_current_user)):
    clients = await ClientService.get_all_clients(user_id=str(current_user.id))
    return templates.TemplateResponse(
        "task_form.html",
        {"request": request, "task": None, "clients": clients, "user": current_user}
    )

@app.get("/tasks/{task_id}")
async def task_detail_page(request: Request, task_id: str, current_user: User = Depends(get_current_user)):
    # Filtrar pela tarefa com verificação de usuário
    task = await TaskService.get_task_by_id(task_id, user_id=str(current_user.id))
    if not task:
        # Se não encontrou com o user_id atual, verifica se existe para outro usuário
        any_task = await TaskService.get_task_by_id(task_id)
        if any_task:
            raise HTTPException(status_code=403, detail="Você não tem permissão para acessar esta tarefa")
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        "task_detail.html",
        {"request": request, "task": task, "now": now, "user": current_user}
    )

@app.get("/tasks/{task_id}/edit")
async def edit_task_page(request: Request, task_id: str, current_user: User = Depends(get_current_user)):
    # Filtrar pela tarefa com verificação de usuário
    task = await TaskService.get_task_by_id(task_id, user_id=str(current_user.id))
    if not task:
        # Se não encontrou com o user_id atual, verifica se existe para outro usuário
        any_task = await TaskService.get_task_by_id(task_id)
        if any_task:
            raise HTTPException(status_code=403, detail="Você não tem permissão para editar esta tarefa")
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    clients = await ClientService.get_all_clients(user_id=str(current_user.id))
    return templates.TemplateResponse(
        "task_form.html",
        {"request": request, "task": task, "clients": clients, "user": current_user}
    )

@app.get("/auth-test")
async def auth_test_page(request: Request):
    """
    Página de teste de autenticação sem depender das dependências.
    """
    try:
        # Tenta extrair e validar manualmente o token
        token = None
        auth_header = request.headers.get("Authorization")
        cookies = request.cookies
        
        # Verifica headers
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
        
        # Verifica também localStorage via JavaScript no template
        
        error_message = None
        user_info = None
        
        # Se encontramos um token, tentamos validá-lo
        if token:
            try:
                payload = AuthService.decode_token(token)
                user_id = payload.get("sub")
                if user_id:
                    user = await AuthService.get_user_by_id(user_id)
                    if user:
                        user_info = {
                            "id": str(user.id),
                            "email": user.email,
                            "username": user.username
                        }
            except Exception as e:
                error_message = str(e)
        
        # Resposta com informações detalhadas
        return templates.TemplateResponse("auth_test.html", {
            "request": request,
            "token_from_header": token is not None,
            "token_value": token[:20] + "..." if token else None,
            "cookies": cookies,
            "headers": dict(request.headers),
            "error_message": error_message,
            "user_info": user_info
        })
    except Exception as e:
        # Em caso de erro, retorna uma página com a mensagem
        return templates.TemplateResponse("auth_test.html", {
            "request": request,
            "error_message": f"Erro ao verificar autenticação: {str(e)}"
        })

# A função get_optional_user já está definida em app/core/dependencies.py 

# Rotas públicas sem autenticação
@app.get("/calendar/google/callback")
async def google_callback_public(code: str, state: str, request: Request):
    """Rota pública para processar o callback do Google OAuth"""
    from app.services.calendar_service import CalendarService
    from app.services.auth_service import AuthService
    from app.services.user_service import UserService
    
    try:
        logger.info(f"[CALLBACK GOOGLE] Iniciando processamento de callback")
        logger.info(f"[CALLBACK GOOGLE] Código: {code[:10]}... (truncado para segurança)")
        logger.info(f"[CALLBACK GOOGLE] Estado: {state}")
        
        # Processar o callback para obter o ID do usuário e atualizar a integração
        result = await CalendarService.handle_google_callback(code, state)
        logger.info(f"[CALLBACK GOOGLE] Resultado do processamento: {result}")
        
        if result and result.get("success") and result.get("user_id"):
            user_id = result.get("user_id")
            logger.info(f"[CALLBACK GOOGLE] Obtendo usuário com ID: {user_id}")
            
            # Obter o usuário
            user = await UserService.get_user_by_id(user_id)
            if not user:
                logger.error(f"[CALLBACK GOOGLE] Usuário não encontrado: {user_id}")
                return RedirectResponse(url="/calendar?error=usuario_nao_encontrado", status_code=302)
            
            # Gerar token JWT com informações completas
            token_data = {
                "sub": str(user.id),
                "email": user.email,
                "username": user.username,
                "role": user.role
            }
            access_token = AuthService.create_access_token(data=token_data)
            logger.info(f"[CALLBACK GOOGLE] Token gerado com sucesso: {access_token[:10]}...")

            # Preparar redirecionamento com mensagem de sucesso
            response = RedirectResponse(url="/calendar?success=true", status_code=302)
            
            # Configurar cookie com o token JWT
            cookie_options = {
                "key": "Authorization",
                "value": f"Bearer {access_token}",
                "httponly": True,
                "secure": True,
                "samesite": "lax",
                "max_age": 604800,  # 7 dias em segundos
                "path": "/"
            }
            response.set_cookie(**cookie_options)
            logger.info(f"[CALLBACK GOOGLE] Cookie definido com opções: {cookie_options}")
            
            # Adicionar também como header para clientes JavaScript
            response.headers["X-Auth-Token"] = access_token
            
            # Log de sucesso e retorno
            logger.info(f"[CALLBACK GOOGLE] Processamento concluído com sucesso, redirecionando para /calendar")
            return response
        else:
            # Falha no processamento
            error_msg = result.get("error", "erro_desconhecido") if result else "falha_no_processamento"
            logger.error(f"[CALLBACK GOOGLE] Falha no processamento: {error_msg}")
            return RedirectResponse(url=f"/calendar?error={error_msg}", status_code=302)
            
    except Exception as e:
        # Capturar qualquer exceção para evitar falhas silenciosas
        logger.error(f"[CALLBACK GOOGLE] Erro durante processamento: {str(e)}", exc_info=True)
        return RedirectResponse(url="/calendar?error=erro_inesperado", status_code=302)

# Rotas de verificação de email
@app.get("/auth/verify-email/{token}")
async def verify_email_page(token: str, request: Request):
    """Processa o token de verificação de email"""
    from app.services.email_verification_service import EmailVerificationService
    try:
        logger.info(f"Processando token de verificação de email: {token[:10]}...")
        email_verification_service = EmailVerificationService()
        success = await email_verification_service.verify_email(token)
        
        if success:
            logger.info(f"Email verificado com sucesso para token: {token[:10]}...")
            return RedirectResponse(url="/auth/verification-success", status_code=302)
        else:
            logger.error(f"Falha ao verificar email para token: {token[:10]}...")
            return RedirectResponse(url="/auth/verification-error", status_code=302)
    except Exception as e:
        logger.error(f"Erro ao verificar e-mail: {str(e)}")
        return RedirectResponse(url="/auth/verification-error?message=error", status_code=302)

@app.get("/auth/verification-success")
async def verification_success_page(request: Request):
    """Página de sucesso após verificação de email"""
    return templates.TemplateResponse("auth/verification_success.html", {"request": request})

@app.get("/auth/verification-error")
async def verification_error_page(request: Request, message: str = None):
    """Página de erro após falha na verificação de email"""
    return templates.TemplateResponse("auth/verification_error.html", {"request": request, "message": message})

@app.get("/auth/verification-pending")
async def verification_pending_page(request: Request):
    """Página mostrada para usuários que ainda não verificaram o email"""
    return templates.TemplateResponse("auth/verification_pending.html", {"request": request})