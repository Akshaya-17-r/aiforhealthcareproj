from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
import time
import logging

import ssl
import certifi

load_dotenv()
from typing import Optional, List, Dict, Any

# Get MongoDB URI from environment variable
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "medicalreport")

logger = logging.getLogger(__name__)

class MongoDBConnection:
    _client: Optional[MongoClient] = None
    _db = None
    _max_retries = 5
    _base_wait_time = 1  # Start with 1 second

    @classmethod
    def connect(cls):
        """
        Establish MongoDB connection with exponential backoff retry logic

        Retries up to 5 times with exponential backoff:
        - Attempt 1: wait 1s
        - Attempt 2: wait 2s
        - Attempt 3: wait 4s
        - Attempt 4: wait 8s
        - Attempt 5: wait 16s
        """
        for attempt in range(1, cls._max_retries + 1):
            try:
                logger.info(f"MongoDB connection attempt {attempt}/{cls._max_retries}...")

                is_atlas = "mongodb.net" in MONGO_URI or "mongodb+srv" in MONGO_URI

                cls._client = MongoClient(
                    MONGO_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    retryWrites=True,
                    maxPoolSize=10,
                    # Use certifi CA bundle for SSL — fixes TLS handshake errors
                    # on Python 3.10+ / Windows when connecting to MongoDB Atlas
                    tlsCAFile=certifi.where() if is_atlas else None,
                )

                # Verify connection
                cls._client.admin.command("ping")
                cls._db = cls._client[DB_NAME]

                logger.info("[OK] MongoDB Connected Successfully")
                print("[OK] MongoDB Connected Successfully")
                return cls._db

            except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                if attempt < cls._max_retries:
                    wait_time = cls._base_wait_time * (2 ** (attempt - 1))
                    logger.warning(
                        f"MongoDB connection failed (attempt {attempt}/{cls._max_retries}). "
                        f"Retrying in {wait_time} seconds... Error: {e}"
                    )
                    print(f"[WAIT] Retrying MongoDB connection in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[FAIL] MongoDB Connection Failed after {cls._max_retries} attempts: {e}")
                    print(f"[FAIL] MongoDB Connection Failed after {cls._max_retries} attempts")
                    raise Exception(
                        f"Could not connect to MongoDB after {cls._max_retries} retries. "
                        f"Please check your MONGO_URI in .env file. Last error: {str(e)}"
                    )

    @classmethod
    def disconnect(cls):
        """Close MongoDB connection"""
        if cls._client:
            cls._client.close()
            cls._db = None
            logger.info("[OK] MongoDB Disconnected")
            print("[OK] MongoDB Disconnected")

    @classmethod
    def get_db(cls):
        """Get database instance"""
        if cls._db is None:
            cls.connect()
        return cls._db


# Service functions for reports
async def save_report(report_data: Dict[str, Any]) -> str:
    """Save a medical report to MongoDB"""
    db = MongoDBConnection.get_db()
    result = db.reports.insert_one(report_data)
    return str(result.inserted_id)


async def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a report by ID"""
    from bson import ObjectId
    db = MongoDBConnection.get_db()
    report = db.reports.find_one({"_id": ObjectId(report_id)})
    if report:
        report["_id"] = str(report["_id"])
    return report


async def get_user_reports(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve all reports for a user"""
    db = MongoDBConnection.get_db()
    reports = list(db.reports.find({"user_id": user_id}))
    for report in reports:
        report["_id"] = str(report["_id"])
    return reports


async def update_report(report_id: str, update_data: Dict[str, Any]) -> bool:
    """Update a report"""
    from bson import ObjectId
    db = MongoDBConnection.get_db()
    result = db.reports.update_one(
        {"_id": ObjectId(report_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0


async def delete_report(report_id: str) -> bool:
    """Delete a report"""
    from bson import ObjectId
    db = MongoDBConnection.get_db()
    result = db.reports.delete_one({"_id": ObjectId(report_id)})
    return result.deleted_count > 0


# Service functions for users
async def save_user(user_data: Dict[str, Any]) -> str:
    """Save a user to MongoDB"""
    db = MongoDBConnection.get_db()
    result = db.users.insert_one(user_data)
    return str(result.inserted_id)


async def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user by ID"""
    from bson import ObjectId
    db = MongoDBConnection.get_db()
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        user["_id"] = str(user["_id"])
    return user


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user by email"""
    db = MongoDBConnection.get_db()
    user = db.users.find_one({"email": email})
    if user:
        user["_id"] = str(user["_id"])
    return user


async def update_user(user_id: str, update_data: Dict[str, Any]) -> bool:
    """Update a user"""
    from bson import ObjectId
    db = MongoDBConnection.get_db()
    result = db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0


async def delete_user(user_id: str) -> bool:
    """Delete a user"""
    from bson import ObjectId
    db = MongoDBConnection.get_db()
    result = db.users.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0