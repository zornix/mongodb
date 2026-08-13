"""Environment + MongoDB client. The one place connection details live."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB = os.environ.get("MONGODB_DB", "repo_brain")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMS = 1536

LESSONS_COLLECTION = "lessons"
CHECKPOINTS_COLLECTION = "checkpoints"  # used by langgraph-checkpoint-mongodb
VECTOR_INDEX_NAME = "lessons_vector_index"


@lru_cache(maxsize=1)
def mongo_client() -> MongoClient:
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not set — copy .env.example to .env and fill it in")
    return MongoClient(MONGODB_URI)


def db():
    return mongo_client()[MONGODB_DB]
