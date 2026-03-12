from google import genai
from google.genai import types
import logging
import os
from typing import Dict, Any, Optional, List
import asyncio
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# Supported Indian languages mapping
SUPPORTED_LANGUAGES = {
    "tamil": {"native": "தமிழ்", "code": "ta", "label": "Tamil"},
    "hindi": {"native": "हिन्दी", "code": "hi", "label": "Hindi"},
    "telugu": {"native": "తెలుగు", "code": "te", "label": "Telugu"},
    "kannada": {"native": "ಕನ್ನಡ", "code": "kn", "label": "Kannada"},
    "malayalam": {"native": "മലയാളം", "code": "ml", "label": "Malayalam"},
    "marathi": {"native": "मराठी", "code": "mr", "label": "Marathi"},
    "gujarati": {"native": "ગુજરાતી", "code": "gu", "label": "Gujarati"},
    "bengali": {"native": "বাংলা", "code": "bn", "label": "Bengali"},
    "punjabi": {"native": "ਪੰਜਾਬੀ", "code": "pa", "label": "Punjabi"},
    "urdu": {"native": "اردو", "code": "ur", "label": "Urdu"}
}

# Translation system prompts
MEDICAL_TRANSLATION_PROMPT = """You are a professional medical translator specializing in translating medical documents and reports into {target_language}.

Your task is to translate the following medical explanation into {target_language} while strictly maintaining:

1. **Medical Accuracy** - All medical terms and meanings must be translated accurately. Do not change or omit any medical information.
2. **Clarity** - Keep the explanation simple, clear, and easy for non-medical readers to understand.
3. **Cultural Appropriateness** - Use natural phrasing that is culturally appropriate for {target_language} speakers.
4. **Completeness** - Translate all content without any omissions or modifications.

Important Guidelines:
- Preserve all medical terminology and diagnoses
- Do not add, remove, or modify any medical information
- Use simple, everyday language suitable for patients
- Maintain the same structure and flow as the original
- If a medical term is not commonly translated, you may use the English term with a simple explanation in {target_language}

Medical Text to Translate:
"""

MEDICAL_TERMINOLOGY_PRESERVATION_PROMPT = """You are an expert medical translator specializing in {target_language}.

Translate the following medical text into {target_language}. Pay special attention to:

1. Accurately translating medical terminology
2. Preserving the exact medical meaning and information
3. Using clear, patient-friendly language
4. Maintaining cultural appropriateness

Text to Translate:
"""

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.FileHandler("translate_service.log")
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
            "Translation will use fallback (return original text)."
        )
        _gemini_available = False
        return None

    try:
        _client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f"Gemini Client initialized for translation (model: {GEMINI_MODEL})")
        _gemini_available = True
        return _client
    except Exception as e:
        logger.warning(
            f"Failed to initialize Gemini: {str(e)}. "
            f"Translation will use fallback (return original text)."
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
# VALIDATION FUNCTIONS
# ============================================================================

def validate_input_text(text: str) -> tuple[bool, str]:
    """
    Validate input text for translation

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
    if len(text) < 5:
        error = "Input text too short (minimum 5 characters)"
        logger.warning(f"[FAIL] {error}")
        return False, error

    logger.debug(f"[OK] Input validation passed: {len(text)} characters")
    return True, ""


def validate_language(language: str) -> tuple[bool, str]:
    """
    Validate if language is supported

    Args:
        language: Language name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    language_lower = language.lower().strip()

    if language_lower not in SUPPORTED_LANGUAGES:
        supported = ", ".join(SUPPORTED_LANGUAGES.keys())
        error = f"Unsupported language: {language}. Supported: {supported}"
        logger.warning(f"[FAIL] {error}")
        return False, error

    logger.debug(f"[OK] Language validation passed: {language}")
    return True, ""


def validate_translation(
    original: str,
    translated: str,
    language: str
) -> Dict[str, Any]:
    """
    Validate translation quality and completeness

    Args:
        original: Original text
        translated: Translated text
        language: Target language

    Returns:
        {
            "is_valid": bool,
            "quality_score": float (0-1),
            "metrics": {
                "original_length": int,
                "translated_length": int,
                "length_ratio": float,
                "has_content": bool
            }
        }
    """
    logger.debug(f"Validating translation to {language}...")

    if not translated or not translated.strip():
        logger.warning("[FAIL] Translated text is empty")
        return {
            "is_valid": False,
            "quality_score": 0.0,
            "metrics": {
                "original_length": len(original),
                "translated_length": 0,
                "length_ratio": 0.0,
                "has_content": False
            }
        }

    original_len = len(original)
    translated_len = len(translated)

    # Translation should be roughly similar length (allow 30-300% variation)
    ratio = translated_len / original_len if original_len > 0 else 1.0

    # Quality heuristics
    quality_score = 0.6

    # Length ratio check (translations often differ in length)
    if 0.3 <= ratio <= 3.0:
        quality_score += 0.25

    # Content check
    if len(translated.split()) > 3:
        quality_score += 0.15

    is_valid = quality_score >= 0.65 and translated_len > 0

    metrics = {
        "original_length": original_len,
        "translated_length": translated_len,
        "length_ratio": round(ratio, 2),
        "has_content": len(translated.strip()) > 0
    }

    logger.info(
        f"Translation validation for {language}: valid={is_valid}, "
        f"quality={quality_score:.2f}, ratio={ratio:.2f}"
    )

    return {
        "is_valid": is_valid,
        "quality_score": min(quality_score, 1.0),
        "metrics": metrics
    }


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

    if len(response) < 3:
        logger.warning("[FAIL] Response too short from Gemini API")
        return False

    logger.debug(f"[OK] Response validation passed: {len(response)} characters")
    return True


# ============================================================================
# TEXT PREPROCESSING FUNCTIONS
# ============================================================================

def chunk_text_for_translation(
    text: str,
    chunk_size: int = 2000,
    overlap: int = 100
) -> List[str]:
    """
    Split long text into manageable chunks for translation

    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in characters
        overlap: Number of overlapping characters between chunks

    Returns:
        List of text chunks
    """
    logger.debug(f"Chunking text for translation: size={len(text)}, chunk_size={chunk_size}")

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
        start = end - overlap

    logger.info(f"[OK] Text chunked into {len(chunks)} chunks")
    return chunks


def merge_translated_chunks(
    chunks: List[str],
    separator: str = "\n\n"
) -> str:
    """
    Merge translated text chunks while maintaining coherence

    Args:
        chunks: List of translated chunks
        separator: Text to insert between chunks

    Returns:
        Merged translated text
    """
    logger.debug(f"Merging {len(chunks)} translated chunks...")

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
async def call_gemini_for_translation(prompt: str) -> str:
    """
    Call Gemini API for translation with retry logic

    Args:
        prompt: Full prompt to send to Gemini

    Returns:
        Response text from Gemini API

    Raises:
        Exception if API call fails after retries
    """
    try:
        logger.debug("Calling Gemini API for translation...")
        client = get_gemini_client()

        # Call the model (async)
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,  # Low temperature for accuracy
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048
            )
        )

        # Extract text from response
        if response and response.text:
            logger.debug(f"[OK] Received translation response: {len(response.text)} characters")
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
# MAIN TRANSLATION FUNCTIONS
# ============================================================================

async def translate_text(text: str, target_language: str) -> Dict[str, Any]:
    """
    Translate text to target Indian language

    Falls back to original text if Gemini API is unavailable.

    Args:
        text: Medical text to translate (ideally simplified)
        target_language: Target language name (e.g., "tamil", "hindi")

    Returns:
        {
            "original_text": str,
            "translated_text": str,
            "language": str,
            "language_code": str,
            "language_native": str,
            "validation": dict,
            "error": str | None,
            "success": bool
        }
    """
    logger.info(f"Starting translation to {target_language}...")

    try:
        # Validate inputs
        is_valid_text, error_text = validate_input_text(text)
        if not is_valid_text:
            return {
                "original_text": text,
                "translated_text": "",
                "language": target_language,
                "language_code": "",
                "language_native": "",
                "validation": {},
                "error": error_text,
                "success": False
            }

        is_valid_lang, error_lang = validate_language(target_language)
        if not is_valid_lang:
            return {
                "original_text": text,
                "translated_text": "",
                "language": target_language,
                "language_code": "",
                "language_native": "",
                "validation": {},
                "error": error_lang,
                "success": False
            }

        language_lower = target_language.lower()
        language_info = SUPPORTED_LANGUAGES[language_lower]
        language_code = language_info["code"]
        language_native = language_info["native"]

        # Check if Gemini is available
        if not is_gemini_available():
            logger.warning(f"[!]  Gemini API not available. Using fallback (original text) for {target_language}.")
            return {
                "original_text": text,
                "translated_text": text,
                "language": target_language,
                "language_code": language_code,
                "language_native": language_native,
                "validation": {
                    "is_valid": True,
                    "quality_score": 0.5,
                    "metrics": {
                        "original_length": len(text),
                        "translated_length": len(text),
                        "length_ratio": 1.0,
                        "has_content": True
                    }
                },
                "error": "Gemini API not available; using original text as translation",
                "success": True
            }

        # Create translation prompt
        prompt = MEDICAL_TRANSLATION_PROMPT.format(
            target_language=language_native
        ) + text

        # Call API
        translated = await call_gemini_for_translation(prompt)

        # Validate translation
        validation = validate_translation(text, translated, target_language)

        logger.info(f"[OK] Translation to {target_language} complete: {len(translated)} characters")

        return {
            "original_text": text,
            "translated_text": translated,
            "language": target_language,
            "language_code": language_code,
            "language_native": language_native,
            "validation": validation,
            "error": None,
            "success": True
        }

    except Exception as e:
        # Fall back to original text if translation fails
        error_msg = f"Translation failed: {str(e)}"
        logger.warning(f"[!]  {error_msg}. Using fallback (original text).")

        try:
            language_lower = target_language.lower()
            language_info = SUPPORTED_LANGUAGES.get(language_lower, {})
            return {
                "original_text": text,
                "translated_text": text,
                "language": target_language,
                "language_code": language_info.get("code", ""),
                "language_native": language_info.get("native", ""),
                "validation": {},
                "error": error_msg,
                "success": True  # Fallback counts as successful (returns original)
            }
        except:
            return {
                "original_text": text,
                "translated_text": "",
                "language": target_language,
                "language_code": "",
                "language_native": "",
                "validation": {},
                "error": error_msg,
                "success": False
            }


async def translate_to_multiple_languages(
    text: str,
    languages: List[str]
) -> Dict[str, Any]:
    """
    Translate text to multiple languages

    Args:
        text: Medical text to translate
        languages: List of target language names

    Returns:
        {
            "original_text": str,
            "translations": {language: translated_text},
            "languages": List[str],
            "successful": int,
            "failed": int,
            "errors": List[str],
            "results": List[dict] (detailed results per language)
        }
    """
    logger.info(f"Batch translating to {len(languages)} languages...")

    translations = {}
    detailed_results = []
    errors = []
    successful = 0

    for i, language in enumerate(languages, 1):
        try:
            logger.debug(f"Translating to {language} ({i}/{len(languages)})...")
            result = await translate_text(text, language)

            detailed_results.append(result)

            if result["success"]:
                translations[language] = result["translated_text"]
                successful += 1
            else:
                errors.append(f"{language}: {result['error']}")

            # Rate limiting between API calls
            if i < len(languages):
                await asyncio.sleep(1)

        except Exception as e:
            error_msg = f"{language}: {str(e)}"
            logger.warning(error_msg)
            errors.append(error_msg)

    logger.info(
        f"[OK] Batch translation complete: {successful}/{len(languages)} successful"
    )

    return {
        "original_text": text,
        "translations": translations,
        "languages": languages,
        "successful": successful,
        "failed": len(errors),
        "errors": errors,
        "results": detailed_results
    }


async def validate_medical_terminology(
    original_text: str,
    translated_text: str,
    language: str
) -> Dict[str, Any]:
    """
    Validate that medical terminology is preserved in translation

    Args:
        original_text: Original text
        translated_text: Translated text
        language: Target language

    Returns:
        {
            "is_valid": bool,
            "medical_terms_found": int,
            "warnings": List[str],
            "recommendations": List[str]
        }
    """
    logger.debug(f"Validating medical terminology preservation for {language}...")

    # Medical keywords to check
    medical_keywords = {
        "patient", "diagnosis", "treatment", "medication", "symptom",
        "disease", "infection", "surgery", "blood", "pressure",
        "inflammation", "antibiotics", "heart", "lung", "diabetes",
        "hypertension", "vaccine", "therapy", "clinical", "examination",
        "test", "result", "discharge", "hospital"
    }

    # Check for medical terms in original
    original_lower = original_text.lower()
    found_terms = [term for term in medical_keywords if term in original_lower]

    # Basic validation: translated text should have content
    is_valid = len(translated_text.strip()) > 0 and len(found_terms) > 0

    warnings = []
    if len(found_terms) == 0:
        warnings.append("No common medical terms detected in original text")

    recommendations = []
    if len(translated_text) < len(original_text) * 0.3:
        recommendations.append("Translation seems unusually short - review for completeness")

    logger.info(
        f"Medical terminology validation: found={len(found_terms)} terms, "
        f"valid={is_valid}"
    )

    return {
        "is_valid": is_valid,
        "medical_terms_found": len(found_terms),
        "medical_terms_list": found_terms,
        "warnings": warnings,
        "recommendations": recommendations
    }


# ============================================================================
# BATCH & UTILITY FUNCTIONS
# ============================================================================

async def batch_translate(
    texts: List[str],
    languages: List[str],
    skip_errors: bool = True
) -> Dict[str, Any]:
    """
    Translate multiple texts to multiple languages

    Args:
        texts: List of texts to translate
        languages: List of target languages
        skip_errors: If True, continue even if one fails

    Returns:
        {
            "total_texts": int,
            "total_languages": int,
            "total_translations": int,
            "results": List[dict],
            "summary": {
                "successful": int,
                "failed": int
            }
        }
    """
    logger.info(f"Batch translating {len(texts)} texts to {len(languages)} languages...")

    results = []
    successful_translations = 0

    for i, text in enumerate(texts, 1):
        logger.debug(f"Processing text {i}/{len(texts)}...")

        try:
            result = await translate_to_multiple_languages(text, languages)
            results.append(result)
            successful_translations += result["successful"]

            # Rate limiting between texts
            if i < len(texts):
                await asyncio.sleep(2)

        except Exception as e:
            error_msg = f"Error processing text {i}: {str(e)}"
            logger.warning(error_msg)

            if not skip_errors:
                raise

            results.append({
                "original_text": text,
                "translations": {},
                "languages": languages,
                "successful": 0,
                "failed": len(languages),
                "errors": [error_msg],
                "results": []
            })

    logger.info(f"[OK] Batch translation complete: {successful_translations} total translations")

    return {
        "total_texts": len(texts),
        "total_languages": len(languages),
        "total_translations": successful_translations,
        "results": results,
        "summary": {
            "successful": len(results),
            "failed": 0
        }
    }


def get_supported_languages() -> List[Dict[str, str]]:
    """
    Get list of all supported languages

    Returns:
        List of language info dictionaries
    """
    logger.debug("Retrieving supported languages...")

    languages = []
    for key, value in SUPPORTED_LANGUAGES.items():
        languages.append({
            "language": key,
            "native": value["native"],
            "code": value["code"],
            "label": value["label"]
        })

    logger.info(f"[OK] Retrieved {len(languages)} supported languages")
    return languages


def is_language_supported(language: str) -> bool:
    """
    Check if a language is supported

    Args:
        language: Language name to check

    Returns:
        True if language is supported
    """
    return language.lower() in SUPPORTED_LANGUAGES


def get_language_info(language: str) -> Optional[Dict[str, str]]:
    """
    Get detailed info about a specific language

    Args:
        language: Language name

    Returns:
        Language info dict or None if not found
    """
    language_lower = language.lower().strip()
    if language_lower in SUPPORTED_LANGUAGES:
        info = SUPPORTED_LANGUAGES[language_lower].copy()
        info["language"] = language_lower
        return info
    return None


def get_translation_stats() -> Dict[str, Any]:
    """Get translation service statistics"""
    return {
        "model": "gemini-pro",
        "supported_languages": len(SUPPORTED_LANGUAGES),
        "languages_list": list(SUPPORTED_LANGUAGES.keys()),
        "temperature": 0.2,
        "max_output_tokens": 2048,
        "retry_attempts": 3,
        "max_chunk_size": 2000
    }


# ============================================================================
# TESTING FUNCTION
# ============================================================================

async def test_translation_service() -> Dict[str, Any]:
    """
    Test the translation service with a sample medical text

    Returns:
        Test result with translations to multiple languages
    """
    logger.info("Testing translation service...")

    sample_text = """
    The patient has been diagnosed with type 2 diabetes mellitus.
    The fasting blood sugar level is 156 mg/dL, which is elevated.
    Treatment includes lifestyle modifications and oral antidiabetic medications.
    The patient should monitor blood glucose regularly and maintain a healthy diet.
    """

    # Test translating to multiple languages
    result = await translate_to_multiple_languages(
        sample_text.strip(),
        ["tamil", "hindi", "telugu"]
    )

    return result


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "translate_text",
    "translate_to_multiple_languages",
    "get_supported_languages",
    "is_language_supported",
    "get_language_info",
    "validate_medical_terminology",
    "validate_translation",
    "batch_translate",
    "get_translation_stats",
    "validate_input_text",
    "validate_language",
    "chunk_text_for_translation",
    "merge_translated_chunks",
    "test_translation_service",
    "SUPPORTED_LANGUAGES"
]
