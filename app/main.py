from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api.routes import clients, tasks, auth, calendar, notification
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
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from fastapi.responses import JSONResponse, RedirectResponse

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
            
            # Lista de caminhos públicos (incluindo assets estáticos)
            public_paths = ['/static/', '/api/auth/login', '/api/auth/register', '/login', '/register', 
                          '/forgot-password', '/auth-debug', '/auth-test', '/favicon.ico',
                          '/auth/verify-email/', '/auth/verification-success', '/auth/verification-error',
                          '/auth/verification-pending', '/google/callback', '/health']
            
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
    await connect_to_mongo()
    
    # Iniciar o serviço de agendamento
    scheduler = SchedulerService()
    scheduler.start()
    
    # Agendar tarefas periódicas
    try:
        # Agendar envio de lembretes de tarefas diariamente às 8h
        scheduler.add_cron_job(
            func=NotificationService.send_task_reminders,
            hour=8,
            minute=0,
            job_id="task_reminders"
        )
        
        # Agendar envio de lembretes de contato com clientes diariamente às 9h
        scheduler.add_cron_job(
            func=NotificationService.schedule_client_reminders,
            hour=9,
            minute=0,
            job_id="client_reminders"
        )
        
        logger.info("Tarefas agendadas com sucesso")
    except Exception as e:
        logger.error(f"Erro ao agendar tarefas: {str(e)}")

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

# Add auth middleware
app.add_middleware(AuthMiddleware)

# Root route
@app.get("/")
async def index(request: Request, current_user: User = Depends(get_current_user)):
    # Obter métricas apenas do usuário autenticado
    metrics = await DashboardService.get_dashboard_metrics(user_id=str(current_user.id))
    # Obter apenas follow-ups do usuário autenticado
    followups = await ClientService.get_upcoming_followups(user_id=str(current_user.id))
    
    context = {
        "request": request,
        "metrics": metrics,
        "followups": followups,
        "user": current_user
    }
    return templates.TemplateResponse("index.html", context)

# Auth routes
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

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
    return templates.TemplateResponse(
        "eisenhower.html",
        {"request": request, "matrix": matrix, "user": current_user}
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
    task = await TaskService.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        "task_detail.html",
        {"request": request, "task": task, "now": now, "user": current_user}
    )

@app.get("/tasks/{task_id}/edit")
async def edit_task_page(request: Request, task_id: str, current_user: User = Depends(get_current_user)):
    task = await TaskService.get_task_by_id(task_id)
    if not task:
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
@app.get("/google/callback")
async def google_callback_public(code: str, state: str, request: Request):
    """Rota pública para processar o callback do Google OAuth"""
    from app.services.calendar_service import CalendarService
    try:
        logger.info(f"[ROTA PÚBLICA] Callback do Google recebido na rota pública /google/callback")
        logger.info(f"[ROTA PÚBLICA] Código: {code[:15]}...")
        logger.info(f"[ROTA PÚBLICA] Estado: {state}")
        logger.info(f"[ROTA PÚBLICA] Headers: {dict(request.headers)}")
        
        # Adicionar path /google/callback à lista de caminhos públicos no middleware AuthMiddleware
        # para garantir que o callback possa ser processado sem autenticação
        
        result = await CalendarService.handle_google_callback(code, state)
        logger.info(f"[ROTA PÚBLICA] Resultado do callback do Google: {result}")
        
        if result and result.get("success"):
            # Redirecionar para a página de calendário com uma mensagem de sucesso
            logger.info(f"[ROTA PÚBLICA] Redirecionando para /calendar após sucesso")
            redirect_url = "/calendar?success=true"
        else:
            # Redirecionar com mensagem de erro
            logger.warning(f"[ROTA PÚBLICA] Redirecionando para /calendar após falha")
            redirect_url = "/calendar?error=true"
            
        return RedirectResponse(url=redirect_url, status_code=302)
    except Exception as e:
        logger.error(f"[ROTA PÚBLICA] Erro no callback do Google: {str(e)}")
        # Em caso de erro, redirecionar para uma página de erro
        return RedirectResponse(url="/calendar?error=true", status_code=302)