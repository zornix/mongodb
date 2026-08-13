"""Environment + MongoDB client. The one place connection details live."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

_HERE = Path(__file__).resolve()
load_dotenv(_HERE.parents[2] / ".env")  # repo-brain/.env
load_dotenv(_HERE.parents[3] / "env")  # workspace `env` some teammates use
load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB = os.environ.get("MONGODB_DB", "repo_brain")
MONGODB_API = os.environ.get("MONGODB_API", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or GEMINI_API_KEY
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

# google-genai / langchain-google read GOOGLE_API_KEY; LangSmith reads LANGSMITH_*.
if GOOGLE_API_KEY and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
EMBEDDING_DIMS = 1536

LESSONS_COLLECTION = "lessons"
RUNS_COLLECTION = "runs"  # Person 2 writes {task, cycles} here; Person 1's stats() reads it
CHECKPOINTS_COLLECTION = "checkpoints"  # used by langgraph-checkpoint-mongodb
VECTOR_INDEX_NAME = "lessons_vector_index"


@lru_cache(maxsize=1)
def mongo_client() -> MongoClient:
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not set — copy .env.example to .env and fill it in")
    return MongoClient(MONGODB_URI, server_api=ServerApi("1"))


def db():
    return mongo_client()[MONGODB_DB]
