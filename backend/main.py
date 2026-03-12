from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, APIRouter, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import os
import logging

# IMPORTANT: Load environment variables FIRST before importing other modules
from config import settings
from auth import (
    create_access_token,
    get_current_user,
    get_current_user_optional
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database connections
from database.mongodb import (
    MongoDBConnection,
    save_report,
    get_report,
    get_user_reports,
    update_report,
    delete_report,
    save_user,
    get_user,
    get_user_by_email,
    update_user,
    delete_user
)

from database.vectordb import (
    VectorDBConnection,
    add_embeddings,
    query_embeddings,
    get_collection_count
)

from database.embeddings import generate_embedding, generate_embeddings_batch
from services.report_pipeline import process_medical_report
from services.rag_service import answer_medical_question

# Import models
from models import (
    UserCreate, UserResponse, ReportCreate, ReportUpdate, ReportResponse,
    EmbeddingRequest, RagQuery, RagResponse, RagResult, HealthStatus
)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("\n" + "="*50)
    print("[>>] Starting Medical Report AI Backend...")
    print("="*50)

    try:
        # Validate required environment variables
        print("\n[i] Checking required environment variables...")

        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key or gemini_key.strip() == "":
            print("\n[!]  WARNING: GEMINI_API_KEY not configured!")
            print("   AI translation and simplification will use fallback (original text).")
            print("   To enable: Set GEMINI_API_KEY in backend/.env")
            print("   Get your key from: https://makersuite.google.com/app/apikey")
        else:
            print("[OK] GEMINI_API_KEY configured")

        secret_key = os.getenv("SECRET_KEY")
        if not secret_key or secret_key == "your-secret-key-change-in-production":
            print("\n[!]  WARNING: Using default SECRET_KEY!")
            print("   For production, set SECRET_KEY to a strong random value in .env")

        print("\n[PKG] Initializing databases...")
        MongoDBConnection.connect()
        VectorDBConnection.connect()
        print("\n[OK] All systems initialized successfully!")
        print("="*50 + "\n")
    except Exception as e:
        print(f"\n[FAIL] Startup failed: {e}")
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    print("\n" + "="*50)
    print("[STOP] Shutting down Medical Report AI Backend...")
    print("="*50)
    MongoDBConnection.disconnect()
    VectorDBConnection.disconnect()
    print("="*50 + "\n")


# Create FastAPI app
app = FastAPI(
    title="Medical Report AI Backend",
    description="AI-powered medical report processing with RAG",
    version="1.0.0",
    lifespan=lifespan
)

# Create API router with /api prefix
api_router = APIRouter(prefix="/api", tags=["API"])


# Add CORS middleware
# Allowed frontend origins (supports development on multiple ports)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",  # Frontend serving from same port
    "http://127.0.0.1:8000",
    "http://localhost:5500",  # Live Server (VS Code)
    "http://localhost:5173",  # Vite dev server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@api_router.get("/health", response_model=HealthStatus)
async def health_check():
    """Check backend health status"""
    db = MongoDBConnection.get_db()

    mongodb_status = False
    try:
        db.client.admin.command("ping")
        mongodb_status = True
    except Exception:
        pass

    return HealthStatus(
        status="healthy",
        mongodb=mongodb_status,
        vectordb=VectorDBConnection.get_collection() is not None,
        embeddings=True,
        timestamp=datetime.now()
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Medical Report AI Backend Running",
        "docs": "/docs",
        "health": "/api/health"
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@api_router.post("/auth/register")
async def register(user: UserCreate):
    """
    Register a new user

    Args:
        user: User registration data (name, email, password)

    Returns:
        User data with JWT token
    """
    try:
        # Check if user already exists
        existing_user = await get_user_by_email(user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Create user record
        user_data = {
            "name": user.name,
            "email": user.email,
            "password": user.password,  # TODO: Hash password before storing in production
            "created_at": datetime.now()
        }

        user_id = await save_user(user_data)
        user_data["_id"] = user_id

        # Create JWT token
        token = create_access_token({
            "sub": user_id,
            "email": user.email,
            "name": user.name
        })

        logger.info(f"User registered: {user_id} ({user.email})")

        return {
            "success": True,
            "user_id": user_id,
            "token": token,
            "user": UserResponse(**user_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.post("/auth/login")
async def login(email: str = Form(...), password: str = Form(...)):
    """
    Login user with email and password

    Returns:
        User data with JWT token
    """
    try:
        # Find user by email
        user = await get_user_by_email(email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # TODO: Verify password hash in production
        if user.get("password") != password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Create JWT token
        token = create_access_token({
            "sub": user["_id"],
            "email": user["email"],
            "name": user.get("name", "")
        })

        logger.info(f"User logged in: {user['_id']} ({email})")

        return {
            "success": True,
            "token": token,
            "user_id": user["_id"],
            "user": UserResponse(**user)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@api_router.post("/auth/verify")
async def verify_token(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Verify JWT token and get user info

    Returns:
        Verified user information
    """
    try:
        user = await get_user(current_user["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        return {
            "success": True,
            "user": UserResponse(**user)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed"
        )


# ============================================================================
# USER ENDPOINTS
# ============================================================================

@api_router.post("/users", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    """Create a new user"""
    try:
        # Check if user already exists
        existing_user = await get_user_by_email(user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        user_data = {
            "name": user.name,
            "email": user.email,
            "password": user.password,  # TODO: Hash password in production
            "created_at": datetime.now()
        }

        user_id = await save_user(user_data)
        user_data["_id"] = user_id

        logger.info(f"User created: {user_id}")

        return {
            "success": True,
            "user_id": user_id,
            "user": UserResponse(**user_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.get("/users/{user_id}", response_model=Dict[str, Any])
async def read_user(user_id: str):
    """Get user by ID"""
    try:
        user = await get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return {
            "success": True,
            "user": UserResponse(**user)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error reading user"
        )


@api_router.get("/users/details")
async def get_user_details(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current authenticated user's details"""
    try:
        user = await get_user(current_user["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "user": UserResponse(**user)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error getting user details"
        )


@api_router.post("/users/details")
async def save_user_details(
    details: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Save current user's details"""
    try:
        user_id = current_user["user_id"]

        # Get existing user
        user = await get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Update user with new details
        update_data = {
            **details,
            "updated_at": datetime.now()
        }

        success = await update_user(user_id, update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user details"
            )

        # Get updated user
        updated_user = await get_user(user_id)

        logger.info(f"User details updated: {user_id}")

        return {
            "success": True,
            "user": UserResponse(**updated_user)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving user details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving user details"
        )


# ============================================================================
# REPORT ENDPOINTS
# ============================================================================

@api_router.post("/reports", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_report(
    report: ReportCreate,
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Create and save a medical report"""
    try:
        # Use authenticated user ID if available, otherwise use provided user_id
        user_id = current_user["user_id"] if current_user else report.user_id

        # Verify user exists
        user = await get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        report_data = {
            "user_id": user_id,
            "file_name": report.file_name,
            "original_text": report.original_text,
            "simplified_text": report.simplified_text,
            "translated_text": report.translated_text,
            "language": report.language,
            "metadata": report.metadata or {},
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        report_id = await save_report(report_data)
        report_data["_id"] = report_id

        logger.info(f"Report created: {report_id} for user {user_id}")

        return {
            "success": True,
            "report_id": report_id,
            "report": ReportResponse(**report_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.get("/reports/{report_id}", response_model=Dict[str, Any])
async def read_report(
    report_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Get a report by ID"""
    try:
        report = await get_report(report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )

        # If user is authenticated, check if this is their report
        if current_user and report.get("user_id") != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return {
            "success": True,
            "report": ReportResponse(**report)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error reading report"
        )


@api_router.get("/users/{user_id}/reports", response_model=Dict[str, Any])
async def list_user_reports(user_id: str, current_user: Dict[str, Any] = Depends(get_current_user_optional)):
    """Get all reports for a user"""
    try:
        # If user is authenticated, check if accessing own reports
        if current_user and user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Verify user exists
        user = await get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        reports = await get_user_reports(user_id)

        logger.info(f"Retrieved {len(reports)} reports for user {user_id}")

        return {
            "success": True,
            "reports": [ReportResponse(**report) for report in reports]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing reports: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing reports"
        )


@api_router.put("/reports/{report_id}", response_model=Dict[str, Any])
async def update_report_endpoint(
    report_id: str,
    report_update: ReportUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Update a report"""
    try:
        # Check if report exists
        existing_report = await get_report(report_id)
        if not existing_report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )

        # Check authorization
        if current_user and existing_report.get("user_id") != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        update_data = {
            k: v for k, v in report_update.dict().items()
            if v is not None
        }
        update_data["updated_at"] = datetime.now()

        success = await update_report(report_id, update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update report"
            )

        updated_report = await get_report(report_id)

        logger.info(f"Report updated: {report_id}")

        return {
            "success": True,
            "report": ReportResponse(**updated_report)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_endpoint(
    report_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Delete a report"""
    try:
        # Check if report exists
        existing_report = await get_report(report_id)
        if not existing_report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )

        # Check authorization
        if current_user and existing_report.get("user_id") != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        success = await delete_report(report_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete report"
            )

        logger.info(f"Report deleted: {report_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# EMBEDDING & RAG ENDPOINTS
# ============================================================================

@api_router.post("/embeddings/generate")
async def generate_embedding_endpoint(request: EmbeddingRequest):
    """Generate embedding for text"""
    try:
        embedding = await generate_embedding(request.text)
        return {
            "success": True,
            "text": request.text,
            "embedding": embedding,
            "dimension": len(embedding)
        }
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.post("/embeddings/batch")
async def generate_batch_embeddings(texts: List[str]):
    """Generate embeddings for multiple texts"""
    try:
        if not texts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No texts provided"
            )

        embeddings = await generate_embeddings_batch(texts, show_progress_bar=False)
        return {
            "success": True,
            "count": len(embeddings),
            "texts": texts,
            "embeddings": embeddings
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating batch embeddings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.post("/rag/query", response_model=Dict[str, Any])
async def rag_query(
    query: RagQuery,
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """
    Query the vector database using RAG with full medical context

    Uses semantic search and Gemini AI to answer patient questions
    about their medical reports.
    """
    try:
        # Use authenticated user ID if available, otherwise use provided filter
        user_id = current_user["user_id"] if current_user else query.filters.get("user_id") if query.filters else "demo_user"

        # Use the full RAG service for comprehensive question answering
        result = await answer_medical_question(
            question=query.query,
            user_id=user_id
        )

        return {
            "success": result.get("success", True),
            "results": [{
                "id": result.get("question", ""),
                "distance": 1 - result.get("confidence", 0),
                "document": result.get("answer", ""),
                "metadata": {
                    "sources": result.get("sources", []),
                    "medical_terms": result.get("medical_terms", [])
                }
            }],
            "query": query.query,
            "count": 1,
            "error": result.get("error")
        }

    except Exception as e:
        logger.error(f"RAG query error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.post("/rag/add")
async def add_rag_documents(
    ids: List[str],
    documents: List[str],
    metadata: List[dict] = None
):
    """Add documents to RAG database"""
    try:
        if len(ids) != len(documents):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Number of IDs must match number of documents"
            )

        # Generate embeddings
        embeddings = await generate_embeddings_batch(documents)

        # Add to vector database
        success = await add_embeddings(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadata=metadata
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add documents"
            )

        logger.info(f"Added {len(ids)} documents to RAG")

        return {
            "success": True,
            "message": "Documents added successfully",
            "count": len(ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding RAG documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.get("/rag/stats")
async def rag_stats():
    """Get RAG database statistics"""
    try:
        count = await get_collection_count()
        return {
            "success": True,
            "collection_name": "medical_knowledge",
            "document_count": count
        }
    except Exception as e:
        logger.error(f"Error getting RAG stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# REPORT SUMMARY & TRANSLATION ENDPOINTS
# ============================================================================

@api_router.get("/reports/{report_id}/summary")
async def get_report_summary(
    report_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Get simplified summary and findings for a report"""
    try:
        report = await get_report(report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )

        # Check authorization
        if current_user and report.get("user_id") != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Extract key data for summary display
        summary_data = {
            "report_id": report_id,
            "metadata": report.get("metadata", {}),
            "medical_summary": report.get("simplified_text", ""),
            "original_text": report.get("original_text", ""),
            "language": report.get("language", "English"),
            "created_at": report.get("created_at"),
            "updated_at": report.get("updated_at")
        }

        return {
            "success": True,
            "data": summary_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting report summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@api_router.get("/reports/{report_id}/translation")
async def get_report_translation(
    report_id: str,
    language: str = "English",
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Get translated content for a report"""
    try:
        report = await get_report(report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )

        # Check authorization
        if current_user and report.get("user_id") != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Extract translation data
        translation_data = {
            "report_id": report_id,
            "language": language,
            "metadata": report.get("metadata", {}),
            "translated_text": report.get("translated_text", ""),
            "simplified_text": report.get("simplified_text", ""),
            "original_text": report.get("original_text", ""),
            "created_at": report.get("created_at"),
            "updated_at": report.get("updated_at")
        }

        return {
            "success": True,
            "data": translation_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting report translation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# AI MEDICAL REPORT PROCESSING ENDPOINT
# ============================================================================

def normalize_language_code(language: str) -> str:
    """
    Normalize language input to lowercase code format

    Handles various language input formats:
    - "Tamil", "tamil", "ta" → "ta"
    - "English", "english" → "en"
    """
    language_lower = language.lower().strip()

    # Common language mappings
    language_mappings = {
        "tamil": "ta",
        "ta": "ta",
        "hindi": "hi",
        "hi": "hi",
        "telugu": "te",
        "te": "te",
        "kannada": "kn",
        "kn": "kn",
        "malayalam": "ml",
        "ml": "ml",
        "marathi": "mr",
        "mr": "mr",
        "gujarati": "gu",
        "gu": "gu",
        "bengali": "bn",
        "bn": "bn",
        "punjabi": "pa",
        "pa": "pa",
        "urdu": "ur",
        "ur": "ur",
        "english": "en",
        "en": "en"
    }

    return language_mappings.get(language_lower, language_lower)


@api_router.post("/upload-report")
async def upload_medical_report(
    file: UploadFile = File(...),
    language: str = Form("en"),
    user_id: str = Form("demo_user"),
    report_name: str = Form(default=""),
    report_type: str = Form(default=""),
    report_date: str = Form(default=""),
    patient_name: str = Form(default=""),
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """
    Upload medical report and run full AI pipeline

    Pipeline:
    Upload → OCR → Simplify → Translate → Embed → Store

    Parameters:
    - file: Medical report file (PDF, JPG, PNG, WEBP)
    - language: Target language for translation (default: en)
    - user_id: User ID for tracking reports (optional if authenticated)
    - report_name: Custom name for the report
    - report_type: Type of report (Blood Work, X-Ray, etc.)
    - report_date: Date of the report
    - patient_name: Patient name (for metadata)
    """
    try:
        # Use authenticated user ID if available
        if current_user:
            user_id = current_user["user_id"]

        # Normalize language code
        language = normalize_language_code(language)

        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        if file.size and file.size > 50 * 1024 * 1024:  # 50 MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 50MB limit"
            )

        logger.info(f"Processing report upload: {file.filename} for user {user_id}, language: {language}")

        # Process the medical report through the full pipeline
        result = await process_medical_report(
            file=file,
            user_id=user_id,
            target_language=language
        )

        # Add metadata to the result
        result["metadata"] = {
            "report_name": report_name,
            "report_type": report_type,
            "report_date": report_date,
            "patient_name": patient_name,
            "uploaded_at": datetime.now().isoformat(),
            **result.get("metadata", {})
        }

        logger.info(f"Report processing complete: {result.get('report_id')}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report upload error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# REGISTER API ROUTER
# ============================================================================

app.include_router(api_router)
