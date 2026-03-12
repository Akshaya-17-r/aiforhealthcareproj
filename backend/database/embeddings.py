from sentence_transformers import SentenceTransformer
from typing import List, Union
import asyncio
import logging

logger = logging.getLogger(__name__)

# Initialize the embedding model
MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(MODEL_NAME)

logger.info(f"Embeddings Model Loaded: {MODEL_NAME}")
print(f"[OK] Embeddings Model Loaded: {MODEL_NAME}")


async def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text (CPU-bound, runs in thread pool)

    Args:
        text: Text to encode

    Returns:
        Embedding vector as list of floats
    """
    try:
        # Run CPU-intensive operation in thread pool to avoid blocking event loop
        embedding = await asyncio.to_thread(
            model.encode,
            text,
            convert_to_tensor=False
        )
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating embedding: {e}", exc_info=True)
        raise


async def generate_embeddings_batch(
    texts: List[str],
    show_progress_bar: bool = False
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts (CPU-bound, runs in thread pool)

    Args:
        texts: List of texts to encode
        show_progress_bar: Whether to show progress bar

    Returns:
        List of embedding vectors
    """
    try:
        # Run CPU-intensive operation in thread pool to avoid blocking event loop
        embeddings = await asyncio.to_thread(
            model.encode,
            texts,
            convert_to_tensor=False,
            show_progress_bar=show_progress_bar
        )
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}", exc_info=True)
        raise


def get_embedding_dimension() -> int:
    """Get the dimension of embeddings"""
    return model.get_sentence_embedding_dimension()