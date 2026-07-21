"""
Central configuration for the Social Support AI system.
Reads from environment variables where possible, with sane local defaults
matching the docker-compose.yml setup.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "social_support")
POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin123")

# MongoDB
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://admin:admin123@localhost:27017/?authSource=admin"
)
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "social_support_docs")

# Qdrant
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "applicant_embeddings")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "admin12345")

# Ollama / LLM
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Paths
DATA_DIR = os.getenv("DATA_DIR", "./data")
