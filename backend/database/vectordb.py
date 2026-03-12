import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Any, Optional

# Vector database configuration
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./data/vector-db")
COLLECTION_NAME = "medical_knowledge"

class VectorDBConnection:
    _client = None
    _collection = None

    @classmethod
    def connect(cls):
        """Initialize ChromaDB connection"""
        try:
            os.makedirs(VECTOR_DB_PATH, exist_ok=True)
            cls._client = chromadb.Client(
                Settings(
                    persist_directory=VECTOR_DB_PATH,
                    anonymized_telemetry=False,
                    is_persistent=True
                )
            )
            cls._collection = cls._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            print("[OK] ChromaDB Initialized Successfully")
            return cls._collection
        except Exception as e:
            print(f"[FAIL] ChromaDB Initialization Failed: {e}")
            raise

    @classmethod
    def disconnect(cls):
        """Close ChromaDB connection"""
        if cls._client:
            print("[OK] ChromaDB Disconnected")
            cls._client = None

    @classmethod
    def get_collection(cls):
        """Get collection instance"""
        if cls._collection is None:
            cls.connect()
        return cls._collection


# Service functions for vector operations
async def add_embeddings(
    ids: List[str],
    embeddings: List[List[float]],
    documents: List[str],
    metadata: List[Dict[str, Any]] = None
) -> bool:
    """Add embeddings to the vector database"""
    try:
        collection = VectorDBConnection.get_collection()

        # Prepare metadata if not provided
        if metadata is None:
            metadata = [{"source": "medical_report"} for _ in ids]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadata
        )
        return True
    except Exception as e:
        print(f"Error adding embeddings: {e}")
        return False


async def query_embeddings(
    query_embedding: List[float],
    n_results: int = 5,
    where: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Query the vector database"""
    try:
        collection = VectorDBConnection.get_collection()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )

        # Format results
        if results.get("ids") and len(results["ids"]) > 0:
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "distance": results["distances"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i]
                })
            return {"results": formatted_results}
        return {"results": []}
    except Exception as e:
        print(f"Error querying embeddings: {e}")
        return {"results": [], "error": str(e)}


async def get_embedding(embedding_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a specific embedding by ID"""
    try:
        collection = VectorDBConnection.get_collection()
        results = collection.get(ids=[embedding_id])

        if results.get("ids") and len(results["ids"]) > 0:
            return {
                "id": results["ids"][0],
                "embedding": results["embeddings"][0],
                "document": results["documents"][0],
                "metadata": results["metadatas"][0]
            }
        return None
    except Exception as e:
        print(f"Error retrieving embedding: {e}")
        return None


async def update_embedding(
    embedding_id: str,
    embedding: List[float],
    document: str,
    metadata: Dict[str, Any] = None
) -> bool:
    """Update an embedding"""
    try:
        collection = VectorDBConnection.get_collection()

        if metadata is None:
            metadata = {"source": "medical_report"}

        collection.update(
            ids=[embedding_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata]
        )
        return True
    except Exception as e:
        print(f"Error updating embedding: {e}")
        return False


async def delete_embedding(embedding_id: str) -> bool:
    """Delete an embedding"""
    try:
        collection = VectorDBConnection.get_collection()
        collection.delete(ids=[embedding_id])
        return True
    except Exception as e:
        print(f"Error deleting embedding: {e}")
        return False


async def get_collection_count() -> int:
    """Get total number of embeddings in collection"""
    try:
        collection = VectorDBConnection.get_collection()
        return collection.count()
    except Exception as e:
        print(f"Error getting collection count: {e}")
        return 0