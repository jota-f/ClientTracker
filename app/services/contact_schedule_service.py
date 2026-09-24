from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from app.core.database import Database
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class ContactScheduleService:
    @staticmethod
    def get_contact_frequency(rfm_total: int) -> int:
        """
        Determina a frequência de contato em dias baseada no score RFM total
        """
        if rfm_total >= 9:  # Clientes VIP
            return 7  # Contato semanal
        elif rfm_total >= 7:  # Clientes importantes
            return 14  # Contato quinzenal
        elif rfm_total >= 5:  # Clientes regulares
            return 30  # Contato mensal
        else:  # Clientes ocasionais
            return 60  # Contato bimestral

    @staticmethod
    def calculate_next_contact_date(last_contact: datetime, rfm_total: int) -> datetime:
        """
        Calcula a próxima data de contato baseada no último contato e score RFM
        """
        frequency_days = ContactScheduleService.get_contact_frequency(rfm_total)
        if last_contact.tzinfo is None:
            last_contact = last_contact.replace(tzinfo=timezone.utc)
        return last_contact + timedelta(days=frequency_days)

    @staticmethod
    async def update_next_followup(client_id: str) -> bool:
        """
        Atualiza a data do próximo followup baseado no RFM
        """
        try:
            client = await Database.database["clients"].find_one({"_id": ObjectId(client_id)})
            if not client:
                return False

            rfm_scores = client.get("rfm_scores", {})
            if not rfm_scores:
                return False

            last_contact = client.get("last_contact")
            if not last_contact:
                return False

            next_followup = ContactScheduleService.calculate_next_contact_date(
                last_contact,
                rfm_scores.get("total", 0)
            )

            await Database.database["clients"].update_one(
                {"_id": ObjectId(client_id)},
                {"$set": {"next_followup": next_followup}}
            )

            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar próximo followup: {str(e)}")
            return False

    @staticmethod
    async def process_all_clients() -> Dict[str, int]:
        """
        Processa todos os clientes e atualiza suas datas de próximo contato
        """
        results = {
            "total": 0,
            "updated": 0,
            "failed": 0
        }

        try:
            async for client in Database.database["clients"].find({}):
                results["total"] += 1
                client_id = str(client["_id"])
                
                if await ContactScheduleService.update_next_followup(client_id):
                    results["updated"] += 1
                else:
                    results["failed"] += 1

            return results
        except Exception as e:
            logger.error(f"Erro ao processar todos os clientes: {str(e)}")
            return results 