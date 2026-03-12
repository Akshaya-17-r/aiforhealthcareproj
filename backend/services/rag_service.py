from google import genai
from google.genai import types
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# Import existing modules
from database.embeddings import generate_embedding
from database.vectordb import query_embeddings
from database.mongodb import get_user_reports, get_user

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.FileHandler("rag_service.log")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Get Gemini API key from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash-lite"

# Initialize Gemini API
_client = None
_gemini_available = False

def initialize_gemini():
    """Initialize Gemini API with key (graceful fallback if unavailable)"""
    global _client, _gemini_available

    if GEMINI_API_KEY is None or GEMINI_API_KEY.strip() == "":
        logger.warning(
            "[!] GEMINI_API_KEY not configured. "
            "RAG question answering will use fallback responses. "
            "To enable: Set GEMINI_API_KEY in .env file."
        )
        _gemini_available = False
        return None

    try:
        _client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f"[OK] Gemini Client initialized for RAG (model: {GEMINI_MODEL})")
        _gemini_available = True
        return _client
    except Exception as e:
        logger.warning(
            f"[!] Failed to initialize Gemini: {str(e)}. "
            f"RAG question answering will use fallback responses."
        )
        _gemini_available = False
        return None


def get_gemini_client():
    """Lazy load Gemini client"""
    global _client, _gemini_available
    if _client is None and not _gemini_available:
        initialize_gemini()
    return _client


def is_gemini_available():
    """Check if Gemini API is available"""
    return _gemini_available


# ============================================================================
# RAG PROMPTS
# ============================================================================

PATIENT_QUESTION_PROMPT = """You are a helpful medical assistant designed to help patients understand their medical reports.

A patient has asked you a question about their medical report. You have been provided with relevant excerpts from their medical reports to help answer the question.

Important guidelines:
1. ONLY use information from the provided medical report excerpts below
2. Do NOT invent or assume medical information not explicitly stated in the excerpts
3. Do NOT provide medical advice or treatment recommendations
4. Explain medical terms in simple, patient-friendly language
5. Be clear and concise
6. If the answer cannot be found in the provided excerpts, clearly say so
7. Encourage the patient to consult their doctor for detailed medical advice

Patient Question: {question}

---

Relevant Medical Report Information:
{context}

---

Please provide a clear, helpful answer based only on the information provided above."""

CONTEXT_IRRELEVANT_PROMPT = """You are a helpful medical assistant designed to help patients understand their medical reports.

A patient has asked you a question about their medical report. However, the available report excerpts do not contain relevant information to answer this question.

Important guidelines:
1. Explain that the specific information is not available in their current stored reports
2. Suggest the patient review their full medical report or contact their healthcare provider
3. Offer to help with other aspects of their medical reports that might be stored in the system
4. Be empathetic and helpful

Patient Question: {question}

---

Please provide a helpful response acknowledging the limitation."""

MEDICAL_TERMINOLOGY_LOOKUP = """Based on the question and context provided, here is medical terminology that might be related:

Question: {question}

Medical Terms in Context: {medical_terms}

Please explain what these terms mean in simple language."""


# ============================================================================
# CONTEXT CONSTRUCTION
# ============================================================================

def construct_context_from_results(
    search_results: List[Dict[str, Any]],
    max_context_length: int = 3000
) -> str:
    """
    Construct context block from vector search results

    Args:
        search_results: List of results from vector database query
        max_context_length: Maximum length of context in characters

    Returns:
        Formatted context string for Gemini
    """
    logger.debug(f"Constructing context from {len(search_results)} results...")

    if not search_results:
        logger.warning("No search results to construct context from")
        return ""

    context_parts = []
    total_length = 0

    for i, result in enumerate(search_results, 1):
        # Extract document content
        document = result.get("document", "")
        metadata = result.get("metadata", {})
        distance = result.get("distance", 0)

        # Add source information
        source_info = ""
        if metadata.get("report_id"):
            source_info = f"[Source: Report {metadata['report_id'][:8]}]"

        # Format the result
        formatted_result = f"{i}. {document}"
        if source_info:
            formatted_result += f" {source_info}"

        # Check length constraints
        part_length = len(formatted_result)
        if total_length + part_length > max_context_length:
            logger.debug(f"Context length limit reached after {i-1} results")
            break

        context_parts.append(formatted_result)
        total_length += part_length

        logger.debug(f"Added result {i}: {len(document)} chars (distance: {distance:.4f})")

    context = "\n\n".join(context_parts)

    logger.info(
        f"[OK] Context constructed: {len(context_parts)} documents, "
        f"total length: {len(context)} characters"
    )

    return context


def extract_medical_terms_from_query(query: str) -> List[str]:
    """
    Extract potential medical terms from question

    Args:
        query: User question

    Returns:
        List of potential medical terms
    """
    logger.debug("Extracting medical terms from query...")

    # Common medical terms and conditions
    medical_keywords = {
        "cholesterol", "hemoglobin", "glucose", "blood", "pressure",
        "diabetes", "hypertension", "infection", "inflammation",
        "antibiotics", "virus", "bacteria", "enzyme", "protein",
        "carbohydrate", "fat", "cholesterol", "triglyceride",
        "calcium", "sodium", "potassium", "magnesium", "iron",
        "vitamin", "mineral", "hormone", "thyroid", "cortisol",
        "insulin", "metabolism", "bmi", "weight", "height",
        "heart", "lung", "liver", "kidney", "pancreas", "stomach",
        "allergy", "asthma", "arthritis", "cancer", "tumor",
        "syndrome", "disease", "disorder", "condition", "symptom",
        "diagnosis", "treatment", "therapy", "medication", "vaccine",
        "surgery", "procedure", "test", "examination", "result",
        "normal", "abnormal", "high", "low", "elevated", "deficiency"
    }

    query_lower = query.lower()
    found_terms = []

    for term in medical_keywords:
        if term in query_lower:
            found_terms.append(term)

    logger.debug(f"Found {len(found_terms)} medical terms in query")
    return found_terms


# ============================================================================
# VECTOR SEARCH & RETRIEVAL
# ============================================================================

async def search_user_reports(
    query_embedding: List[float],
    user_id: str,
    top_k: int = 5,
    min_similarity: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Search vector database for relevant user reports

    Args:
        query_embedding: Embedding vector of the question
        user_id: User ID to filter results
        top_k: Number of top results to retrieve
        min_similarity: Minimum similarity threshold (0-1)

    Returns:
        List of relevant documents with metadata
    """
    logger.info(f"Searching vector database for user {user_id}...")

    try:
        # Query vector database with higher k to account for filtering
        search_k = top_k * 3  # Request more to filter by user_id later

        results_data = await query_embeddings(
            query_embedding=query_embedding,
            n_results=search_k,
            where=None  # MongoDB filtering will happen next
        )

        raw_results = results_data.get("results", [])
        logger.debug(f"Vector search returned {len(raw_results)} raw results")

        if not raw_results:
            logger.warning(f"No results found in vector database for query")
            return []

        # Filter results by user_id and similarity
        filtered_results = []

        for result in raw_results:
            metadata = result.get("metadata", {})
            distance = result.get("distance", 0)

            # Convert distance to similarity (ChromaDB uses cosine, lower is better)
            # Similarity = 1 - distance for cosine distance
            similarity = 1 - distance if distance is not None else 0

            # Skip if below minimum similarity threshold
            if similarity < min_similarity:
                logger.debug(f"Skipping result: similarity {similarity:.4f} < {min_similarity}")
                continue

            # Filter by user_id if present in metadata
            if metadata.get("user_id") and metadata.get("user_id") != user_id:
                logger.debug(f"Skipping result: wrong user_id")
                continue

            result["similarity"] = similarity
            filtered_results.append(result)

            if len(filtered_results) >= top_k:
                break

        logger.info(
            f"[OK] Retrieved {len(filtered_results)} relevant documents "
            f"for user {user_id} (min similarity: {min_similarity})"
        )

        return filtered_results

    except Exception as e:
        logger.error(f"[FAIL] Error searching vector database: {str(e)}", exc_info=True)
        return []


# ============================================================================
# GEMINI API CALLS
# ============================================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True
)
async def call_gemini_for_answer(prompt: str) -> str:
    """
    Call Gemini API to generate answer

    Args:
        prompt: Full prompt for Gemini

    Returns:
        Generated answer text

    Raises:
        Exception if API call fails
    """
    try:
        logger.debug("Calling Gemini API for answer generation...")
        client = get_gemini_client()

        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,  # Low temperature for factuality
                top_p=0.8,
                top_k=40,
                max_output_tokens=1024
            )
        )

        if response and response.text:
            logger.debug(f"[OK] Received Gemini response: {len(response.text)} characters")
            return response.text.strip()
        else:
            error = "Empty response from Gemini API"
            logger.warning(f"[FAIL] {error}")
            raise Exception(error)

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"[FAIL] Gemini API call failed: {error_msg}")
        raise


# ============================================================================
# MAIN RAG FUNCTIONS
# ============================================================================

async def answer_medical_question(
    question: str,
    user_id: str,
    top_k: int = 5,
    min_similarity: float = 0.3
) -> Dict[str, Any]:
    """
    Main RAG function: Answer medical question using patient's reports

    Args:
        question: User's medical question
        user_id: Patient/user ID
        top_k: Number of top documents to retrieve
        min_similarity: Minimum similarity threshold (0-1)

    Returns:
        {
            "answer": str,
            "question": str,
            "sources": List[sources],
            "confidence": float (0-1),
            "context_used": bool,
            "medical_terms": List[str],
            "retrieval_count": int,
            "error": str | None,
            "success": bool
        }
    """
    logger.info("="*70)
    logger.info(f"Medical question received from user {user_id}")
    logger.info(f"Question: {question}")
    logger.info("="*70)

    import time
    start_time = time.time()

    try:
        # Validate inputs
        if not question or len(question.strip()) < 3:
            error_msg = "Question too short (minimum 3 characters)"
            logger.warning(f"[FAIL] {error_msg}")
            return {
                "answer": "",
                "question": question,
                "sources": [],
                "confidence": 0.0,
                "context_used": False,
                "medical_terms": [],
                "retrieval_count": 0,
                "error": error_msg,
                "success": False
            }

        if not user_id or len(user_id.strip()) == 0:
            error_msg = "Invalid user ID"
            logger.warning(f"[FAIL] {error_msg}")
            return {
                "answer": "",
                "question": question,
                "sources": [],
                "confidence": 0.0,
                "context_used": False,
                "medical_terms": [],
                "retrieval_count": 0,
                "error": error_msg,
                "success": False
            }

        # ==================== STEP 1: Generate Question Embedding ====================
        logger.info("Step 1: Generating question embedding...")
        try:
            question_embedding = await generate_embedding(question)
            logger.info(f"[OK] Question embedding generated: {len(question_embedding)} dimensions")
        except Exception as e:
            error_msg = f"Failed to generate question embedding: {str(e)}"
            logger.error(f"[FAIL] {error_msg}")
            return {
                "answer": "",
                "question": question,
                "sources": [],
                "confidence": 0.0,
                "context_used": False,
                "medical_terms": [],
                "retrieval_count": 0,
                "error": error_msg,
                "success": False
            }

        # ==================== STEP 2: Vector Search ====================
        logger.info("Step 2: Searching vector database...")
        search_results = await search_user_reports(
            query_embedding=question_embedding,
            user_id=user_id,
            top_k=top_k,
            min_similarity=min_similarity
        )

        retrieval_count = len(search_results)
        logger.info(f"[OK] Retrieved {retrieval_count} relevant documents")

        # ==================== STEP 3: Extract Medical Terms ====================
        logger.info("Step 3: Extracting medical terms from question...")
        medical_terms = extract_medical_terms_from_query(question)
        logger.info(f"[OK] Found {len(medical_terms)} medical terms in question")

        # ==================== STEP 4 & 5: Context Construction & Answer Generation ====================
        context_used = False
        answer = ""
        confidence = 0.0
        sources = []

        if search_results:
            # Build context
            logger.info("Step 4: Constructing context from search results...")
            context = construct_context_from_results(search_results)

            if context and len(context.strip()) > 0:
                context_used = True

                # Calculate confidence based on similarity scores
                similarities = [r.get("similarity", 0) for r in search_results]
                confidence = sum(similarities) / len(similarities) if similarities else 0.0
                confidence = min(confidence, 1.0)

                # Extract sources
                sources = [
                    {
                        "id": result.get("id", "unknown"),
                        "document": result.get("document", "")[:200],  # First 200 chars
                        "similarity": round(result.get("similarity", 0), 4),
                        "metadata": result.get("metadata", {})
                    }
                    for result in search_results
                ]

                # ==================== STEP 5: Generate Answer with Gemini ====================
                # Check if Gemini is available
                if is_gemini_available():
                    logger.info("Step 5: Generating answer with Gemini...")

                    prompt = PATIENT_QUESTION_PROMPT.format(
                        question=question,
                        context=context
                    )

                    try:
                        answer = await call_gemini_for_answer(prompt)
                        logger.info(f"[OK] Answer generated: {len(answer)} characters")
                    except Exception as e:
                        error_msg = f"Failed to generate answer: {str(e)}"
                        logger.warning(f"[!]  {error_msg}. Using fallback response.")
                        # Use context directly as fallback answer
                        answer = f"Based on your medical reports: {context[:300]}..."
                else:
                    logger.warning("[!]  Gemini API not available. Using context as fallback answer.")
                    # Use context directly as fallback answer
                    answer = f"Based on your medical reports: {context[:300]}..."
            else:
                logger.warning("No meaningful context could be constructed from search results")

        if not context_used or not answer:
            # No relevant context found - generate fallback response
            logger.warning("No relevant context found - generating fallback response...")

            if is_gemini_available():
                prompt = CONTEXT_IRRELEVANT_PROMPT.format(question=question)

                try:
                    answer = await call_gemini_for_answer(prompt)
                    confidence = 0.0
                    context_used = False
                except Exception as e:
                    logger.error(f"Failed to generate fallback response: {str(e)}")
                    answer = "I couldn't find relevant information in your medical reports to answer this question. Please consult your healthcare provider for more details."
            else:
                # No Gemini available and no context - use generic fallback
                answer = "I couldn't find relevant information in your medical reports to answer this question. Please consult your healthcare provider for more details."
                logger.warning("[!]  Using generic fallback response (Gemini API not available).")

        processing_time = time.time() - start_time

        logger.info("="*70)
        logger.info("[OK] Medical question answered successfully")
        logger.info(f"Confidence: {confidence:.2f}, Sources: {len(sources)}, Time: {processing_time:.2f}s")
        logger.info("="*70)

        return {
            "answer": answer,
            "question": question,
            "sources": sources,
            "confidence": round(confidence, 4),
            "context_used": context_used,
            "medical_terms": medical_terms,
            "retrieval_count": retrieval_count,
            "processing_time": processing_time,
            "error": None,
            "success": True
        }

    except Exception as e:
        error_msg = f"Unexpected error in RAG pipeline: {str(e)}"
        logger.error(f"[FAIL] {error_msg}", exc_info=True)
        return {
            "answer": "",
            "question": question,
            "sources": [],
            "confidence": 0.0,
            "context_used": False,
            "medical_terms": [],
            "retrieval_count": 0,
            "error": error_msg,
            "success": False
        }


async def answer_followup_question(
    original_question: str,
    followup_question: str,
    user_id: str,
    previous_context: List[Dict[str, Any]] = None,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Answer a follow-up question, optionally using previous context

    Args:
        original_question: Original question for context
        followup_question: Follow-up question
        user_id: User ID
        previous_context: Optional context from previous answer
        top_k: Number of documents to retrieve

    Returns:
        Answer structured response
    """
    logger.info(f"Processing follow-up question for user {user_id}...")
    logger.info(f"Original: {original_question}")
    logger.info(f"Follow-up: {followup_question}")

    # Combine questions for better context
    combined_question = f"{original_question} {followup_question}"

    result = await answer_medical_question(
        question=combined_question,
        user_id=user_id,
        top_k=top_k
    )

    return result


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def batch_medical_questions(
    questions: List[Dict[str, str]],
    skip_errors: bool = True
) -> Dict[str, Any]:
    """
    Answer multiple questions for potentially multiple users

    Args:
        questions: List of {"question": str, "user_id": str}
        skip_errors: Continue processing if one fails

    Returns:
        Batch results
    """
    logger.info(f"Batch processing {len(questions)} medical questions...")

    results = []
    successful = 0
    failed = 0

    for i, item in enumerate(questions, 1):
        logger.debug(f"Processing question {i}/{len(questions)}...")

        try:
            question = item.get("question", "")
            user_id = item.get("user_id", "")

            if not question or not user_id:
                logger.warning(f"Skipping question {i}: missing question or user_id")
                failed += 1
                continue

            result = await answer_medical_question(question, user_id)
            results.append(result)

            if result.get("success"):
                successful += 1
            else:
                failed += 1

            # Rate limiting
            if i < len(questions):
                await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"Error processing question {i}: {str(e)}")
            failed += 1

            if not skip_errors:
                raise

    logger.info(f"[OK] Batch processing complete: {successful} successful, {failed} failed")

    return {
        "total": len(questions),
        "successful": successful,
        "failed": failed,
        "results": results
    }


def get_rag_stats() -> Dict[str, Any]:
    """Get RAG service statistics"""
    return {
        "service": "RAG",
        "model": GEMINI_MODEL,
        "embedding_dimension": 384,
        "vector_db": "ChromaDB",
        "min_similarity_default": 0.3,
        "top_k_default": 5,
        "context_max_length": 3000,
        "gemini_temperature": 0.3
    }


async def test_rag_service(user_id: str = "test_user") -> Dict[str, Any]:
    """
    Test RAG service with sample question

    Args:
        user_id: User ID for testing

    Returns:
        Test result
    """
    logger.info("Testing RAG service...")

    sample_question = "What does hemoglobin level mean and is mine normal?"

    result = await answer_medical_question(sample_question, user_id)

    return result


# ============================================================================
# SEMANTIC SEARCH ENHANCEMENT
# ============================================================================

async def semantic_search_reports(
    query: str,
    user_id: str,
    top_k: int = 10
) -> Dict[str, Any]:
    """
    Perform semantic search on user's medical reports without generating answer

    Args:
        query: Search query
        user_id: User ID
        top_k: Number of results

    Returns:
        List of relevant documents
    """
    logger.info(f"Semantic search for user {user_id}: {query}")

    try:
        # Generate embedding for query
        query_embedding = await generate_embedding(query)

        # Search vector database
        results = await search_user_reports(
            query_embedding=query_embedding,
            user_id=user_id,
            top_k=top_k,
            min_similarity=0.2
        )

        logger.info(f"[OK] Semantic search returned {len(results)} results")

        return {
            "query": query,
            "user_id": user_id,
            "results_count": len(results),
            "results": [
                {
                    "id": r.get("id"),
                    "document": r.get("document"),
                    "similarity": r.get("similarity"),
                    "metadata": r.get("metadata")
                }
                for r in results
            ]
        }

    except Exception as e:
        logger.error(f"Semantic search error: {str(e)}")
        return {
            "query": query,
            "user_id": user_id,
            "results_count": 0,
            "results": [],
            "error": str(e)
        }


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "answer_medical_question",
    "answer_followup_question",
    "batch_medical_questions",
    "semantic_search_reports",
    "get_rag_stats",
    "test_rag_service",
    "search_user_reports",
    "construct_context_from_results",
    "extract_medical_terms_from_query"
]
