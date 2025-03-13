import logging
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

class SchedulerService:
    """Serviço para gerenciar tarefas agendadas"""
    
    _instance = None
    _scheduler = None
    
    @classmethod
    def get_instance(cls):
        """Obtém uma instância singleton do serviço de agendamento"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Inicializa o scheduler"""
        if SchedulerService._scheduler is None:
            self._scheduler = AsyncIOScheduler()
            SchedulerService._scheduler = self._scheduler
        else:
            self._scheduler = SchedulerService._scheduler
    
    def start(self):
        """Inicia o scheduler"""
        if not self._scheduler.running:
            try:
                self._scheduler.start()
                logger.info("Scheduler iniciado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao iniciar o scheduler: {e}")
    
    def shutdown(self):
        """Para o scheduler"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler desligado")
    
    def add_interval_job(
        self, 
        func: Callable, 
        seconds: int = 0, 
        minutes: int = 0, 
        hours: int = 0, 
        days: int = 0,
        job_id: Optional[str] = None,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None
    ):
        """Adiciona um job para ser executado em intervalos regulares"""
        try:
            if not any([seconds, minutes, hours, days]):
                raise ValueError("Pelo menos um dos intervalos deve ser maior que zero")
                
            trigger = IntervalTrigger(
                seconds=seconds, 
                minutes=minutes, 
                hours=hours, 
                days=days
            )
            
            return self._scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                args=args if args else [],
                kwargs=kwargs if kwargs else {},
                replace_existing=True
            )
        except Exception as e:
            logger.error(f"Erro ao adicionar job com intervalo: {e}")
            return None
    
    def add_cron_job(
        self, 
        func: Callable, 
        hour: Optional[int] = None, 
        minute: Optional[int] = None,
        day_of_week: Optional[str] = None,
        job_id: Optional[str] = None,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None
    ):
        """Adiciona um job para ser executado em horários específicos (estilo cron)"""
        try:
            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=day_of_week
            )
            
            return self._scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                args=args if args else [],
                kwargs=kwargs if kwargs else {},
                replace_existing=True
            )
        except Exception as e:
            logger.error(f"Erro ao adicionar job cron: {e}")
            return None
    
    def add_one_time_job(
        self, 
        func: Callable, 
        run_date: datetime,
        job_id: Optional[str] = None,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None
    ):
        """Adiciona um job para ser executado uma única vez em uma data específica"""
        try:
            trigger = DateTrigger(run_date=run_date)
            
            return self._scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                args=args if args else [],
                kwargs=kwargs if kwargs else {},
                replace_existing=True
            )
        except Exception as e:
            logger.error(f"Erro ao adicionar job único: {e}")
            return None
    
    def remove_job(self, job_id: str) -> bool:
        """Remove um job agendado pelo ID"""
        try:
            self._scheduler.remove_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Erro ao remover job {job_id}: {e}")
            return False
    
    def get_jobs(self) -> list:
        """Obtém todos os jobs agendados"""
        return self._scheduler.get_jobs() 