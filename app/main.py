from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api.routes import clients, tasks
from app.models.client import Client
from app.models.task import Task, TaskStatus, TaskPriority
from app.services.client_service import ClientService
from app.services.task_service import TaskService
from app.services.dashboard_service import DashboardService
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Root route
@app.get("/")
async def index(request: Request):
    metrics = await DashboardService.get_dashboard_metrics()
    followups = await ClientService.get_upcoming_followups()
    
    context = {
        "request": request,
        "metrics": metrics,
        "followups": followups
    }
    return templates.TemplateResponse("index.html", context)

# Client routes
@app.get("/clients")
async def list_clients_page(request: Request):
    clients = await ClientService.get_all_clients()
    return templates.TemplateResponse(
        "clients.html",
        {"request": request, "clients": clients}
    )

@app.get("/clients/new")
async def new_client_page(request: Request):
    logger.info("Acessando a página de novo cliente")
    return templates.TemplateResponse(
        "client_form.html",
        {"request": request, "client": None}
    )

@app.get("/clients/{client_id}")
async def client_detail_page(request: Request, client_id: str):
    client = await ClientService.get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return templates.TemplateResponse(
        "client_detail.html",
        {"request": request, "client": client}
    )

@app.get("/clients/{client_id}/edit")
async def edit_client_page(request: Request, client_id: str):
    client = await ClientService.get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return templates.TemplateResponse(
        "client_form.html",
        {"request": request, "client": client}
    )

# Task routes
@app.get("/tasks")
async def list_tasks_page(request: Request):
    tasks = await TaskService.get_all_tasks()
    return templates.TemplateResponse(
        "tasks.html",
        {"request": request, "tasks": tasks}
    )

@app.get("/tasks/kanban")
async def kanban_board_page(request: Request):
    tasks = await TaskService.get_all_tasks()
    return templates.TemplateResponse(
        "kanban.html",
        {"request": request, "tasks": tasks}
    )

@app.get("/tasks/eisenhower")
async def eisenhower_matrix_page(request: Request):
    matrix = await TaskService.get_eisenhower_matrix()
    return templates.TemplateResponse(
        "eisenhower.html",
        {"request": request, "matrix": matrix}
    )

@app.get("/tasks/new")
async def new_task_page(request: Request):
    clients = await ClientService.get_all_clients()
    return templates.TemplateResponse(
        "task_form.html",
        {"request": request, "task": None, "clients": clients}
    )

@app.get("/tasks/{task_id}")
async def task_detail_page(request: Request, task_id: str):
    task = await TaskService.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return templates.TemplateResponse(
        "task_detail.html",
        {"request": request, "task": task}
    )

@app.get("/tasks/{task_id}/edit")
async def edit_task_page(request: Request, task_id: str):
    task = await TaskService.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    clients = await ClientService.get_all_clients()
    return templates.TemplateResponse(
        "task_form.html",
        {"request": request, "task": task, "clients": clients}
    ) 