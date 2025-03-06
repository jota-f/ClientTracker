from fastapi import APIRouter, HTTPException
from app.models.client import Client
from app.core.database import Database
from bson import ObjectId

router = APIRouter()

@router.post("/clients/", response_model=Client)
async def create_client(client: Client):
    client_dict = client.dict()
    result = await Database.client["clients"].insert_one(client_dict)
    client.id = str(result.inserted_id)
    return client

@router.get("/clients/{client_id}", response_model=Client)
async def read_client(client_id: str):
    client_data = await Database.client["clients"].find_one({"_id": ObjectId(client_id)})
    if client_data is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return Client(**client_data)

@router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client: Client):
    update_result = await Database.client["clients"].update_one(
        {"_id": ObjectId(client_id)},
        {"$set": client.dict(exclude_unset=True)}
    )
    if update_result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.delete("/clients/{client_id}", response_model=dict)
async def delete_client(client_id: str):
    delete_result = await Database.client["clients"].delete_one({"_id": ObjectId(client_id)})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"} 