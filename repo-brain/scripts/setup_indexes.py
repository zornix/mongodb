"""Create the Atlas Vector Search index for the lessons collection.

Run once before the event (index builds can take a few minutes):
    uv run python scripts/setup_indexes.py
"""

import time

from pymongo.operations import SearchIndexModel

from repo_brain.config import EMBEDDING_DIMS, LESSONS_COLLECTION, VECTOR_INDEX_NAME, db


def main() -> None:
    coll = db()[LESSONS_COLLECTION]
    # Collection must exist before a search index can be attached.
    if LESSONS_COLLECTION not in coll.database.list_collection_names():
        coll.database.create_collection(LESSONS_COLLECTION)

    existing = [ix["name"] for ix in coll.list_search_indexes()]
    if VECTOR_INDEX_NAME in existing:
        print(f"index '{VECTOR_INDEX_NAME}' already exists")
        return

    model = SearchIndexModel(
        name=VECTOR_INDEX_NAME,
        type="vectorSearch",
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": EMBEDDING_DIMS,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "type"},
            ]
        },
    )
    coll.create_search_index(model=model)
    print(f"creating '{VECTOR_INDEX_NAME}' ", end="", flush=True)
    while True:
        ix = next((i for i in coll.list_search_indexes() if i["name"] == VECTOR_INDEX_NAME), None)
        if ix and ix.get("queryable"):
            print("\nindex is queryable — ready.")
            return
        print(".", end="", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
