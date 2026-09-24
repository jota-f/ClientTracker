import os
import pymongo
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get MongoDB connection string from environment variables
MONGODB_URL = os.getenv("MONGODB_URL")

# Create MongoDB client
client = MongoClient(MONGODB_URL)

# Access the database
db = client.clienttracker

# Define collections
clients_collection = db.clients
tasks_collection = db.tasks
users_collection = db.users

def get_db():
    """
    Get database connection.
    Returns MongoDB database instance.
    """
    return db

def get_collection(collection_name: str):
    """
    Get MongoDB collection by name.
    Args:
        collection_name: Name of the collection
    Returns:
        MongoDB collection
    """
    return db[collection_name] 