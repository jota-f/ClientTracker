from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api.routes import clients, tasks, auth, calendar
from app.models.client import Client
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.user import User
from app.services.client_service import ClientService
from app.services.task_service import TaskService
from app.services.dashboard_service import DashboardService
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user, get_optional_user
import logging
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional

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
            # Lógica para verificar se há token em cookies e convertê-lo para cabeçalho
            auth_header = request.headers.get("Authorization")
            auth_cookie = request.cookies.get("Authorization")
            auth_meta = request.headers.get("x-auth-token")
            
            logger.info(f"Processando requisição para: {request.url.path}")
            logger.debug(f"Headers originais: {dict(request.headers)}")
            logger.debug(f"Cookies: {request.cookies}")
            
            # Se não há cabeçalho, mas há um cookie ou meta tag de autorização, use-o como cabeçalho
            if not auth_header:
                if auth_cookie:
                    logger.info("Usando token do cookie como cabeçalho")
                    auth_header = auth_cookie
                elif auth_meta:
                    logger.info("Usando token da meta tag como cabeçalho")
                    auth_header = f"Bearer {auth_meta}"
                    
                if auth_header:
                    # Criar um header mutable para adicionar o Authorization
                    request._headers = {**request.headers, "Authorization": auth_header}
                    # Também atualize o cabeçalho na scope
                    request.scope["headers"] = [
                        (key.lower().encode(), value.encode()) 
                        for key, value in request._headers.items()
                    ]
                    logger.debug(f"Headers atualizados: {dict(request._headers)}")
            
            # Verifica se é uma requisição para páginas protegidas
            path = request.url.path
            if not path.startswith(('/static/', '/api/auth/login', '/api/auth/register', '/login', '/register', '/forgot-password', '/auth-debug', '/auth-test')):
                logger.info(f"Verificando autenticação para página protegida: {path}")
                if not auth_header:
                    logger.warning(f"Acesso negado a {path} - Token não encontrado")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Não autorizado"}
                    )
            
            # Continua com a requisição
            response = await call_next(request)
            
            # Se a resposta for 401 ou 403, adiciona informações de debug nos headers
            if response.status_code in (401, 403):
                logger.warning(f"Resposta {response.status_code} para {path}")
                logger.debug(f"Headers finais: {dict(request.headers)}")
            
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

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")
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
        {"request": request, "client": client, "user": current_user, "now": now}
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
    clients = await ClientService.get_all_clients()
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
    clients = await ClientService.get_all_clients()
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