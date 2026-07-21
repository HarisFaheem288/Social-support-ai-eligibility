"""
Connection helpers for PostgreSQL, MongoDB, Qdrant, and Neo4j.
Each function returns a ready-to-use client/connection.
"""
import psycopg2
from pymongo import MongoClient
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

from app.config import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD,
    MONGO_URI, MONGO_DB_NAME,
    QDRANT_HOST, QDRANT_PORT,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
)


def get_postgres_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def get_mongo_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB_NAME]


def get_qdrant_client():
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def test_all_connections():
    """Quick sanity check that every database is reachable. Prints pass/fail per DB."""
    results = {}

    try:
        conn = get_postgres_connection()
        conn.close()
        results["postgres"] = "OK"
    except Exception as e:
        results["postgres"] = f"FAILED: {e}"

    try:
        db = get_mongo_db()
        db.list_collection_names()
        results["mongodb"] = "OK"
    except Exception as e:
        results["mongodb"] = f"FAILED: {e}"

    try:
        client = get_qdrant_client()
        client.get_collections()
        results["qdrant"] = "OK"
    except Exception as e:
        results["qdrant"] = f"FAILED: {e}"

    try:
        driver = get_neo4j_driver()
        driver.verify_connectivity()
        driver.close()
        results["neo4j"] = "OK"
    except Exception as e:
        results["neo4j"] = f"FAILED: {e}"

    return results


if __name__ == "__main__":
    for db, status in test_all_connections().items():
        print(f"{db}: {status}")
