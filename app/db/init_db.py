"""
Run once to set up the PostgreSQL schema and Qdrant collection.
Usage: python -m app.db.init_db
"""
from app.db.connections import get_postgres_connection, get_qdrant_client
from app.config import QDRANT_COLLECTION
from qdrant_client.models import Distance, VectorParams


def init_postgres():
    conn = get_postgres_connection()
    cur = conn.cursor()
    with open("app/db/schema.sql", "r") as f:
        cur.execute(f.read())
    conn.commit()
    cur.close()
    conn.close()
    print("PostgreSQL schema created.")


def init_qdrant():
    client = get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        print(f"Qdrant collection '{QDRANT_COLLECTION}' created.")
    else:
        print(f"Qdrant collection '{QDRANT_COLLECTION}' already exists.")


if __name__ == "__main__":
    init_postgres()
    init_qdrant()
