from google import genai
from google.genai import types
import logging
import os
from typing import Dict, Any, Optional, List
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Setup file handler
if not logger.handlers:
    handler = logging.FileHandler("simplify_service.log")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Get Gemini API key from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash-lite"

# Initialize Gemini client
_client = None
_gemini_available = False

def initialize_gemini():
    """Initialize Gemini API with key (graceful fallback if unavailable)"""
    global _client, _gemini_available

    if GEMINI_API_KEY is None or GEMINI_API_KEY.strip() == "":
        logger.warning(
            "GEMINI_API_KEY not configured. "
            "Text simplification will use fallback (original text). "
            "To enable: Set GEMINI_API_KEY in .env file."
        )
        _gemini_available = False
        return None

    try:
        _client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f"Gemini Client initialized (model: {GEMINI_MODEL})")
        _gemini_available = True
        return _client
    except Exception as e:
        logger.warning(
            f"Failed to initialize Gemini: {str(e)}. "
            f"Simplification will use fallback (original text)."
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
# SYSTEM PROMPTS
# ============================================================================

MEDICAL_SIMPLIFICATION_PROMPT = """You are a helpful medical assistant whose job is to help patients understand their medical reports.

A patient has received a medical report and needs help understanding it. Rewrite the following medical text in simple, easy-to-understand language that a non-medical person can understand.

Guidelines:
1. Use simple everyday language instead of medical jargon
2. Explain medical terms in brackets when necessary
3. Be clear and concise
4. Maintain medical accuracy - do not invent or change medical information
5. Focus on what the findings mean for the patient
6. Do not provide medical advice or treatment recommendations
7. If something is unclear, say so - do not guess

Medical Text to Simplify:
"""

KEY_FINDINGS_PROMPT = """Based on the medical report text below, extract the key findings and important medical information in simple language.

For each finding, provide:
1. What was found
2. What it means in simple terms
3. Severity (if mentioned): Normal, Mild, Moderate, or Severe

Format your response as a numbered list.

Medical Text:
"""

SUMMARY_PROMPT = """Based on the medical report text below, provide a very brief summary (2-3 sentences) of the main findings.

Keep it simple and patient-friendly. Do not use complex medical jargon.

Medical Text:
"""


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_input_text(text: str) -> tuple[bool, str]:
    """
    Validate input text for simplification

    Args:
        text: Text to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text:
        error = "Input text is empty"
        logger.warning(f"[FAIL] {error}")
        return False, error

    if not isinstance(text, str):
        error = "Input must be a string"
        logger.warning(f"[FAIL] {error}")
        return False, error

    text = text.strip()
    if len(text) < 10:
        error = "Input text too short (minimum 10 characters)"
        logger.warning(f"[FAIL] {error}")
        return False, error

    logger.debug(f"[OK] Input validation passed: {len(text)} characters")
    return True, ""


def validate_response(response: str) -> bool:
    """
    Validate Gemini API response

    Args:
        response: Response text from Gemini API

    Returns:
        True if response is valid
    """
    if not response or not response.strip():
        logger.warning("[FAIL] Empty response from Gemini API")
        return False

    if len(response) < 5:
        logger.warning("[FAIL] Response too short from Gemini API")
        return False

    logger.debug(f"[OK] Response validation passed: {len(response)} characters")
    return True


# ============================================================================
# TEXT CHUNKING FUNCTIONS
# ============================================================================

def chunk_text_for_processing(
    text: str,
    chunk_size: int = 3000,
    overlap: int = 100
) -> List[str]:
    """
    Split long text into manageable chunks for API processing

    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in characters
        overlap: Number of overlapping characters between chunks

    Returns:
        List of text chunks
    """
    logger.debug(f"Chunking text: size={len(text)}, chunk_size={chunk_size}")

    if len(text) <= chunk_size:
        logger.debug("Text fits in single chunk")
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Find a good break point (end of sentence)
        if end < len(text):
            last_period = text.rfind(".", start, end)
            if last_period > start + chunk_size // 2:
                end = last_period + 1

        chunks.append(text[start:end])

        # Move start position with overlap
        start = end - overlap

    logger.info(f"[OK] Text chunked into {len(chunks)} chunks")
    return chunks


def merge_simplified_chunks(
    chunks: List[str],
    separator: str = "\n\n"
) -> str:
    """
    Merge simplified text chunks while maintaining coherence

    Args:
        chunks: List of simplified chunks
        separator: Text to insert between chunks

    Returns:
        Merged simplified text
    """
    logger.debug(f"Merging {len(chunks)} simplified chunks...")

    merged = separator.join(chunk.strip() for chunk in chunks if chunk.strip())
    merged = merged.strip()

    logger.info(f"[OK] Chunks merged: {len(merged)} characters")
    return merged


# ============================================================================
# API CALL FUNCTIONS (WITH RETRY LOGIC)
# ============================================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True
)
async def call_gemini_api(prompt: str) -> str:
    """Call Gemini API with retry logic"""
    try:
        logger.debug("Calling Gemini API...")
        client = get_gemini_client()

        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048
            )
        )

        if response and response.text:
            logger.debug(f"Received Gemini response: {len(response.text)} characters")
            return response.text

        raise Exception("Empty response from Gemini API")

    except Exception as e:
        logger.warning(f"Gemini API call failed: {str(e)}")
        raise


# ============================================================================
# MAIN SIMPLIFICATION FUNCTIONS
# ============================================================================

async def simplify_medical_text(text: str) -> Dict[str, Any]:
    """
    Simplify complex medical text into patient-friendly language

    Falls back to original text if Gemini API is unavailable.

    Args:
        text: Raw medical text from OCR or other source

    Returns:
        {
            "simplified_text": str,
            "summary": str,
            "key_findings": List[str],
            "original_length": int,
            "simplified_length": int,
            "chunks_processed": int,
            "error": str | None
        }
    """
    logger.info("Starting medical text simplification...")

    try:
        # Validate input
        is_valid, error = validate_input_text(text)
        if not is_valid:
            return {
                "simplified_text": "",
                "summary": "",
                "key_findings": [],
                "original_length": len(text),
                "simplified_length": 0,
                "chunks_processed": 0,
                "error": error
            }

        original_length = len(text)
        logger.info(f"Input text length: {original_length} characters")

        # Check if Gemini is available
        if not is_gemini_available():
            logger.warning("[!]  Gemini API not available. Using fallback (original text).")
            return {
                "simplified_text": text,
                "summary": text[:200] + "..." if len(text) > 200 else text,
                "key_findings": [],
                "original_length": original_length,
                "simplified_length": len(text),
                "chunks_processed": 1,
                "error": "Gemini API not available; using original text as simplified text"
            }

        # Chunk text if too long
        chunks = chunk_text_for_processing(text)

        # Simplify each chunk
        simplified_chunks = []
        logger.debug(f"Processing {len(chunks)} chunks...")

        for i, chunk in enumerate(chunks, 1):
            logger.debug(f"Simplifying chunk {i}/{len(chunks)}...")

            prompt = MEDICAL_SIMPLIFICATION_PROMPT + chunk
            simplified = await call_gemini_api(prompt)

            if validate_response(simplified):
                simplified_chunks.append(simplified)
            else:
                logger.warning(f"Invalid response for chunk {i}, using original")
                simplified_chunks.append(chunk)

            # Rate limiting: small delay between API calls
            if i < len(chunks):
                await asyncio.sleep(1)

        # Merge simplified chunks
        simplified_text = merge_simplified_chunks(simplified_chunks)

        # Extract key findings
        logger.debug("Extracting key findings...")
        key_findings = await extract_key_findings(text)

        # Generate summary
        logger.debug("Generating summary...")
        summary = await generate_summary(simplified_text)

        logger.info(
            f"[OK] Simplification complete: "
            f"{original_length} → {len(simplified_text)} characters"
        )

        return {
            "simplified_text": simplified_text,
            "summary": summary,
            "key_findings": key_findings,
            "original_length": original_length,
            "simplified_length": len(simplified_text),
            "chunks_processed": len(chunks),
            "error": None
        }

    except Exception as e:
        # Fall back to original text if simplification fails
        error_msg = f"Simplification failed: {str(e)}"
        logger.warning(f"[!]  {error_msg}. Using fallback (original text).")
        return {
            "simplified_text": text,
            "summary": text[:200] + "..." if len(text) > 200 else text,
            "key_findings": [],
            "original_length": len(text),
            "simplified_length": len(text),
            "chunks_processed": 0,
            "error": error_msg
        }


async def extract_key_medical_findings(text: str) -> List[Dict[str, str]]:
    """
    Extract key medical findings from text

    Args:
        text: Medical text to analyze

    Returns:
        List of findings with structure:
        [
            {
                "finding": str,
                "severity": str,
                "importance": float
            }
        ]
    """
    logger.debug("Extracting key medical findings...")

    try:
        is_valid, error = validate_input_text(text)
        if not is_valid:
            logger.warning(f"Cannot extract findings: {error}")
            return []

        prompt = KEY_FINDINGS_PROMPT + text

        response = await call_gemini_api(prompt)

        if not validate_response(response):
            logger.warning("Invalid response for key findings extraction")
            return []

        # Parse response into structured format
        findings = []
        lines = response.split('\n')

        for line in lines:
            line = line.strip()
            if not line or not line[0].isdigit():
                continue

            # Simple parsing - in production you might want more sophisticated parsing
            findings.append({
                "finding": line,
                "severity": "Unknown",
                "importance": 0.5
            })

        logger.info(f"[OK] Extracted {len(findings)} key findings")
        return findings

    except Exception as e:
        logger.error(f"[FAIL] Error extracting findings: {str(e)}", exc_info=True)
        return []


async def extract_key_findings(text: str) -> List[str]:
    """
    Extract and format key findings as simple list

    Args:
        text: Medical text to analyze

    Returns:
        List of key findings as strings
    """
    logger.debug("Extracting key findings...")

    try:
        findings_with_severity = await extract_key_medical_findings(text)
        findings = [f["finding"] for f in findings_with_severity]

        logger.info(f"[OK] Extracted {len(findings)} key findings")
        return findings

    except Exception as e:
        logger.error(f"[FAIL] Error extracting findings: {str(e)}")
        return []


async def generate_summary(text: str) -> str:
    """
    Generate a brief summary of the medical text

    Args:
        text: Medical or simplified text to summarize

    Returns:
        Brief summary (2-3 sentences)
    """
    logger.debug("Generating summary...")

    try:
        is_valid, error = validate_input_text(text)
        if not is_valid:
            logger.warning(f"Cannot generate summary: {error}")
            return ""

        # Use only first chunk for summary to keep it concise
        text_for_summary = text[:2000] if len(text) > 2000 else text

        prompt = SUMMARY_PROMPT + text_for_summary

        summary = await call_gemini_api(prompt)

        if validate_response(summary):
            logger.info(f"[OK] Summary generated: {len(summary)} characters")
            return summary.strip()

        logger.warning("Invalid summary response")
        return ""

    except Exception as e:
        logger.error(f"[FAIL] Error generating summary: {str(e)}", exc_info=True)
        return ""


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def simplify_batch(texts: List[str]) -> List[Dict[str, Any]]:
    """
    Simplify multiple texts at once

    Args:
        texts: List of medical texts to simplify

    Returns:
        List of simplification results
    """
    logger.info(f"Batch simplifying {len(texts)} texts...")

    results = []

    for i, text in enumerate(texts, 1):
        logger.debug(f"Processing text {i}/{len(texts)}...")

        result = await simplify_medical_text(text)
        results.append(result)

        # Rate limiting between requests
        if i < len(texts):
            await asyncio.sleep(2)

    logger.info(f"[OK] Batch simplification complete")
    return results


def get_simplification_stats() -> Dict[str, Any]:
    """Get statistics about simplification capabilities"""
    return {
        "model": "gemini-pro",
        "max_chunk_size": 3000,
        "temperature": 0.3,
        "max_output_tokens": 2048,
        "retry_attempts": 3,
        "supported_languages": ["en"]
    }


async def test_simplification_service() -> Dict[str, Any]:
    """
    Test the simplification service with a sample medical text

    Args:
        None

    Returns:
        Test result with simplified output
    """
    logger.info("Testing simplification service...")

    sample_text = """
    The patient presents with acute myocardial infarction (AMI) characterized by elevated
    cardiac biomarkers (troponin I: 2.5 ng/mL) and ST-segment elevation in leads II, III,
    and aVF on the 12-lead electrocardiogram (ECG). The ejection fraction (EF) is reduced to
    38% as measured by transthoracic echocardiography. Clinical presentation includes acute
    chest pain, diaphoresis, and dyspnea. The patient was administered dual antiplatelet
    therapy (DAPT) with aspirin and clopidogrel, along with unfractionated heparin (UFH).
    Percutaneous coronary intervention (PCI) of the right coronary artery (RCA) revealed
    a thrombus-containing lesion which was successfully revascularized.
    """

    result = await simplify_medical_text(sample_text)
    return result


# ============================================================================
# ASYNC IMPORT (Handle if asyncio is needed)
# ============================================================================

import asyncio

__all__ = [
    "simplify_medical_text",
    "extract_key_findings",
    "extract_key_medical_findings",
    "generate_summary",
    "simplify_batch",
    "get_simplification_stats",
    "test_simplification_service",
    "validate_input_text",
    "validate_response",
    "chunk_text_for_processing",
    "merge_simplified_chunks"
]
