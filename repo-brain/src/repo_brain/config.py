"""Environment + MongoDB client. The one place connection details live."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

_HERE = Path(__file__).resolve()
ENV_PATH = _HERE.parents[2] / ".env"  # repo-brain/.env — what `crew model <name>` rewrites
load_dotenv(ENV_PATH)
load_dotenv(_HERE.parents[3] / "env")  # workspace `env` some teammates use
load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB = os.environ.get("MONGODB_DB", "repo_brain")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

# The free tier caps requests per day *per model*, and one cold run is ~8 requests — so
# switching model is how you buy a fresh budget mid-rehearsal. These are the models
# confirmed available on the hackathon key; `crew model --list` asks the API for the
# current truth. Short aliases so a switch is `crew model 3.5`.
# (`gemini-2.5-flash-lite` is listed by the API but 404s on this key — "no longer
# available to new users" — so it is deliberately not an option here.)
MODEL_ALIASES = {
    "3.1": "gemini-3.1-flash-lite",
    "3.5": "gemini-3.5-flash-lite",
    "preview": "gemini-3.1-flash-lite-preview",
    "3.6": "gemini-3.6-flash",
    "flash": "gemini-3.5-flash",
}
# Verified callable on the hackathon key, cheapest first. Each has its own daily budget.
DEMO_MODELS = (
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite-preview",
)


# GOOGLE_API_KEY is what langchain-google-genai reads; accept GEMINI_API_KEY as an alias.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
if GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "voyage-3.5-lite")
EMBEDDING_DIMS = 1024  # baked into the Atlas vector index — change only before setup_indexes.py

LESSONS_COLLECTION = "lessons"
RUNS_COLLECTION = "runs"  # Person 2 writes {task, cycles} here; Person 1's stats() reads it
CHECKPOINTS_COLLECTION = "checkpoints"  # used by langgraph-checkpoint-mongodb
VECTOR_INDEX_NAME = "lessons_vector_index"


def resolve_model(name: str) -> str:
    """Expand a short alias ('3.5') to a full model id; pass anything else through."""
    return MODEL_ALIASES.get(name.strip(), name.strip())


def set_gemini_model(name: str, persist: bool = False) -> str:
    """Point the crew and the distiller at another Gemini model for this process.

    Callers must read `config.GEMINI_MODEL` at call time (not `from ... import`) for this
    to take effect. `persist=True` also rewrites GEMINI_MODEL in repo-brain/.env, so a
    later command — or a resumed run in a new process — picks the same model up.
    """
    global GEMINI_MODEL
    GEMINI_MODEL = resolve_model(name)
    os.environ["GEMINI_MODEL"] = GEMINI_MODEL
    if persist:
        _write_env_var("GEMINI_MODEL", GEMINI_MODEL)
    return GEMINI_MODEL


def _write_env_var(key: str, value: str) -> None:
    """Replace (or append) one KEY=value line in .env, leaving the rest of the file alone."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def available_models() -> list[str]:
    """Model ids this key can call generateContent on — the API's answer, not a guess.

    Being listed is necessary but not sufficient: some ids here still 404 as
    "no longer available to new users" (see MODEL_ALIASES).
    """
    from google import genai  # bundled with langchain-google-genai

    client = genai.Client(api_key=GOOGLE_API_KEY)
    return sorted(
        m.name.removeprefix("models/")
        for m in client.models.list()
        if "generateContent" in (m.supported_actions or [])
    )


@lru_cache(maxsize=1)
def mongo_client() -> MongoClient:
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not set — copy .env.example to .env and fill it in")
    return MongoClient(MONGODB_URI, server_api=ServerApi("1"))


def db():
    return mongo_client()[MONGODB_DB]
