import pandas as pd
import pytz
from dotenv import load_dotenv
import os
import requests
import re
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import numpy as np
import sys

# Load environment variables
load_dotenv()

# Load API credentials
Status_TELEGRAM_CHAT_ID = os.getenv("Status_TELEGRAM_CHAT_ID")

# MongoDB Credentials
MONGO_DB_USERNAME = os.getenv("MONGO_DB_USERNAME")
MONGO_DB_PASSWORD = os.getenv("MONGO_DB_PASSWORD")

# Set the timezone to UTC+5:30
ist = pytz.timezone('Asia/Kolkata')

# Check if environment variables are set
if not MONGO_DB_USERNAME or not MONGO_DB_PASSWORD:
    raise ValueError("MongoDB credentials are not set in the environment variables.")

# MongoDB connection setup
def connect_to_mongo():
    print("Connecting to MongoDB...")
    uri = f"mongodb+srv://{MONGO_DB_USERNAME}:{MONGO_DB_PASSWORD}@cluster0.ou0xiys.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
        return client
    except Exception as e:
        print("MongoDB connection error:", e)
        return None

# Connect to MongoDB
client = connect_to_mongo()

# Check if the client is connected
if client is None:
    print("Failed to connect to MongoDB. Exiting...")
    sys.exit(1)
    

# ---------------- DATABASE & COLLECTION ----------------

db = client["uspark_market_updates"]

users_collection = db["users"]

# Prevent duplicate users using Telegram's unique user ID
users_collection.create_index(
    [("user_id", 1)],
    unique=True,
    name="unique_telegram_user_id"
)

print("MongoDB database and users collection ready!")

def get_all_chat_ids():
    """Return all Telegram chat IDs from MongoDB."""
    chat_ids = users_collection.find(
        {"chat_id": {"$exists": True, "$ne": None}},
        {"_id": 0, "chat_id": 1}
    )

    return [user["chat_id"] for user in chat_ids]

