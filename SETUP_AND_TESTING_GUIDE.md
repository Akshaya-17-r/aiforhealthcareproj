# Medical Report AI - Setup & Testing Guide

## Overview
This guide provides step-by-step instructions to set up, configure, and test the complete medical report AI system with all fixes implemented.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Backend Configuration](#backend-configuration)
4. [Running the Backend](#running-the-backend)
5. [Frontend Setup](#frontend-setup)
6. [Testing the Pipeline](#testing-the-pipeline)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- Python 3.9+ (for backend)
- Node.js 16+ (for frontend)
- MongoDB Atlas account (or local MongoDB)
- Google Gemini API key (free tier available)
- Git

### System Requirements
- Minimum 4GB RAM (8GB recommended due to ML models)
- 10GB free disk space (for models and vector database)
- Internet connection (for APIs and database)

### Check Your Installation
```bash
python --version          # Should be 3.9+
node --version            # Should be 16+
npm --version             # Should be 8+
```

---

## Environment Setup

### 1. Create .env File from Template

```bash
cd /d/medicalreport/backend

# Copy the example configuration
cp .env.example .env

# Edit .env with your credentials
# Choose your editor (nano, vim, code, etc.)
nano .env
```

### 2. Configure .env File

#### MongoDB Atlas Setup
```ini
# Go to MongoDB Atlas console and get your connection string
# https://account.mongodb.com/account/login

# Connection String Format:
# mongodb+srv://username:password@cluster0.mongodb.net/medicalreport?retryWrites=true&w=majority

MONGO_URI=mongodb+srv://your_username:your_password@cluster0.mongodb.net/medicalreport?retryWrites=true&w=majority
DB_NAME=medicalreport
```

**Steps to Get MongoDB Connection String:**
1. Go to https://account.mongodb.com/
2. Click "Build a Database"
3. Select "Free" plan (M0)
4. Create cluster (takes ~3 minutes)
5. Click "Connect" → "Drivers" → "Python" → copy connection string
6. Replace `<password>` with your database password
7. Add database name at the end (e.g., `/medicalreport`)

#### Gemini API Key Setup (Optional but Recommended)
```ini
# Get free API key from: https://makersuite.google.com/app/apikey

GEMINI_API_KEY=your_actual_gemini_api_key_here
```

**Why Gemini API?**
- ✅ Text simplification (medical jargon → patient-friendly language)
- ✅ Translation (to 10 Indian languages)
- ✅ RAG question answering
- ✅ Free tier available (with limits)

**If GEMINI_API_KEY is NOT set:**
- System will work fine
- But will use fallback (original text instead of simplified)
- You'll see warnings in logs
- No errors will occur

#### JWT Authentication Setup
```ini
# Generate secure random key:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Copy output to .env
SECRET_KEY=generated-random-key-here

# Token expiration (hours)
ACCESS_TOKEN_EXPIRE_HOURS=24
```

#### FastAPI Server Configuration
```ini
HOST=0.0.0.0
PORT=8000
DEBUG=False              # Set to True for development
VECTOR_DB_PATH=./data/vector-db
```

### 3. Complete Example .env

```ini
# Database
MONGO_URI=mongodb+srv://user123:SecurePass@cluster0.mongodb.net/medicalreport?retryWrites=true&w=majority
DB_NAME=medicalreport

# Vector Database
VECTOR_DB_PATH=./data/vector-db

# AI Services
GEMINI_API_KEY=AIzaSyC3_chav1JuPP2mzgkBiFata_78I9Ub__A

# Authentication
SECRET_KEY=your-generated-random-key-here
ACCESS_TOKEN_EXPIRE_HOURS=24

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=False
```

---

## Backend Configuration

### 1. Install Dependencies

```bash
cd /d/medicalreport/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# Download ML models (for EasyOCR and embeddings)
# This may take a few minutes
python -c "import easyocr; easyocr.Reader(['en'])"
```

### 2. Verify Environment

```bash
# Test MongoDB connection
python -c "from database.mongodb import MongoDBConnection; MongoDBConnection.connect()"

# Test ChromaDB
python -c "from database.vectordb import VectorDBConnection; VectorDBConnection.connect()"

# Test Embeddings Model
python -c "from database.embeddings import generate_embedding; print('✓ Embeddings model loaded')"
```

### What These Do

| Component | Purpose |
|-----------|---------|
| **MongoDB** | Stores medical reports, user data, processing logs |
| **ChromaDB** | Vector database for semantic search (RAG) |
| **EasyOCR** | Extracts text from medical report images/PDFs |
| **SentenceTransformers** | Generates embeddings for semantic search |
| **Gemini API** | Simplifies medical text, translates, answers questions |

---

## Running the Backend

### Start the Backend Server

```bash
cd /d/medicalreport/backend

# Ensure venv is activated
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Expected output:
# ✓ MongoDB Connected Successfully
# ✓ ChromaDB Initialized Successfully
# ✓ Embeddings Model Loaded: all-MiniLM-L6-v2
# Uvicorn running on http://127.0.0.1:8000
```

### Access the Backend

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health

### Understanding the Startup Output

```
🚀 Starting Medical Report AI Backend...
📋 Checking required environment variables...
✓ GEMINI_API_KEY configured        # ← Good! API enabled
✓ MongoDB Connected Successfully   # ← Database connected
✓ ChromaDB Initialized Successfully # ← Vector DB ready
✓ Embeddings Model Loaded          # ← ML model loaded
✓ All systems initialized successfully!
```

---

## Frontend Setup

### 1. Install Dependencies

```bash
cd /d/medicalreport/frontend-react

# Install Node packages
npm install

# Expected: "added XXX packages"
```

### 2. Configure Frontend API Endpoint

```bash
# Create .env file (if it doesn't exist)
# Windows PowerShell:
New-Item -Path .env -Value "VITE_API_BASE_URL=http://localhost:8000/api" -Force

# macOS/Linux:
echo "VITE_API_BASE_URL=http://localhost:8000/api" > .env
```

### 3. Start the Frontend

```bash
cd /d/medicalreport/frontend-react

# Development server (with hot reload)
npm run dev

# Expected output:
# VITE v4.x.x  ready in 234 ms
# ➜  Local:   http://localhost:5173/
# ➜  press h to show help
```

### Access the Frontend
- Navigate to: **http://localhost:5173**

---

## Testing the Pipeline

### ✅ Test 1: Health Check

```bash
# Via curl
curl http://localhost:8000/api/health

# Expected response:
{
  "status": "healthy",
  "mongodb": true,
  "vectordb": true,
  "embeddings": true,
  "timestamp": "2026-03-11T12:00:00"
}
```

### ✅ Test 2: User Registration & Login

```bash
# 1. Register new user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "password": "SecurePassword123"
  }'

# Response will include JWT token:
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "507f1f77bcf86cd799439011"
}

# 2. Save the token (you'll need it for authenticated requests)
TOKEN="your_token_here"
```

### ✅ Test 3: Upload Medical Report (End-to-End Pipeline)

```bash
# Important: Replace TOKEN with actual token from registration

# Using a sample medical report image (create test file first)
# Or download a sample from: https://example.com/sample-report.jpg

curl -X POST http://localhost:8000/api/upload-report \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/medical_report.pdf" \
  -F "language=English" \
  -F "report_type=Blood Work" \
  -F "report_date=2026-03-11"

# Expected response:
{
  "success": true,
  "report_id": "507f1f77bcf86cd799439012",
  "status": "complete",
  "data": {
    "original_text": "extracted text from image...",
    "simplified_text": "patient-friendly version...",
    "translated_text": "translated version...",
    "summary": "overall summary...",
    "key_findings": ["Finding 1", "Finding 2"]
  }
}
```

### ✅ Test 4: RAG Question Answering

```bash
# Ask a question about the uploaded report
curl -X POST http://localhost:8000/api/rag/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What does my hemoglobin level mean?",
    "filters": {"user_id": "your_user_id"}
  }'

# Response:
{
  "success": true,
  "results": [{
    "document": "Based on your reports: Your hemoglobin level...",
    "similarity": 0.87,
    "sources": [...]
  }]
}
```

### ✅ Test 5: Frontend Complete Workflow

1. **Open Frontend**: http://localhost:5173
2. **Register/Login**: Create account
3. **Upload Report**: Click "Upload Medical Report"
   - Select a test PDF or image
   - Choose language (English, Tamil, Hindi, etc.)
   - Click Upload
4. **View Results**:
   - See original extracted text
   - View simplified explanation
   - Check translation
   - Ask questions about the report

### 📝 Test Files to Use

Create sample test files or use real medical report images:

```bash
# Create a simple test text file
cat > test_report.txt << 'EOF'
Patient Name: John Doe
Date: 2026-03-11
Test Results:
- Hemoglobin: 14.5 g/dL (Normal range: 13.5-17.5)
- Blood Glucose: 110 mg/dL (Normal: <100 fasting)
- Cholesterol: 220 mg/dL (High, recommended <200)
Conclusion: Patient has slightly elevated cholesterol levels
EOF

# Note: For actual medical reports,  use PDF or image files
```

---

## Troubleshooting

### ❌ Backend Won't Start

**Problem**: `Error: Cannot connect to MongoDB`

**Solutions**:
```bash
# 1. Check if .env file exists and has MONGO_URI
cat backend/.env | grep MONGO_URI

# 2. Test MongoDB connection string
python -c "from pymongo import MongoClient; MongoClient('YOUR_MONGO_URI').admin.command('ping'); print('✓ Connected')"

# 3. Verify MongoDB Atlas:
#    - Is cluster running? Check at https://account.mongodb.com/
#    - Is IP address whitelisted? Add 0.0.0.0/0 for development
#    - Is password correct? Try resetting at MongoDB console

# 4. Retry logic will automatically attempt 5 times with exponential backoff
#    Wait 1-30 seconds depending on attempt
```

### ❌ Gemini API Not Working

**Problem**: `GEMINI_API_KEY not configured` warning

**This is NOT a critical error.** System works with fallback:

```bash
# To enable Gemini:
# 1. Get free API key from: https://makersuite.google.com/app/apikey
# 2. Add to .env: GEMINI_API_KEY=your_key_here
# 3. Restart backend

# To verify:
curl http://localhost:8000/api/health
# Look for any warnings in console output
```

### ❌ Frontend Can't Reach Backend

**Problem**: `API request failed` errors in browser

**Solutions**:
```bash
# 1. Check if backend is running
curl http://localhost:8000/api/health

# 2. Check VITE_API_BASE_URL in frontend/.env
cat frontend-react/.env

# 3. Verify CORS is enabled (it should be by default)

# 4. Check browser console for actual error
#    Open: http://localhost:5173 → F12 → Console → look for error message
```

### ❌ OCR Not Extracting Text

**Problem**: `No text detected in image` or empty text

**Reasons & Solutions**:
```bash
# 1. Image quality too low
#    → Try clearer, higher resolution image

# 2. Text in image is rotated or tilted
#    → Rotate image first (EasyOCR handles most, but not all)

# 3. Handwritten text
#    → EasyOCR is trained on printed text, may not work well

# 4. Check logs:
#    → Look for "OCR complete" message with confidence score
#    → If confidence < 0.4, text extraction was weak
```

### ❌ Memory Issues / Slow Processing

**Problem**: System becomes slow or crashes during processing

**Reasons**:
- Large medical reports (multi-page PDFs)
- Limited RAM (<4GB)
- Multiple concurrent uploads

**Solutions**:
```bash
# 1. Limit file size
#    Backend automatically rejects files >50MB

# 2. Process one report at a time

# 3. Monitor resources:
#    Windows: Task Manager
#    macOS: Activity Monitor
#    Linux: top, htop

# 4. Increase system resources or add more RAM
```

### ⚠️ Useful Logs to Check

```bash
# Backend logs (real-time):
# Watch the terminal where backend is running
# Look for: ERROR, WARNING, ✓ indicators

# Log files:
ls -la backend/*.log          # Log files created

# Database logs:
# Check MongoDB Atlas console for connection history
```

---

## Understanding the Complete Pipeline

### Data Flow: User Upload → AI Processing → Result

```
1. USER UPLOADS FILE
   ↓
   [Frontend] Upload form with language selection
   ↓

2. BACKEND RECEIVES REQUEST
   ↓
   Check: File valid, size OK, authentication OK
   ↓

3. REPORT PROCESSING PIPELINE (All 6 Steps)
   ↓
   Step 1: OCR (EasyOCR)
   - Input: PDF/Image file
   - Output: Extracted text
   - Fallback: Error message
   ↓
   Step 2: Simplification (Gemini API)
   - Input: Medical text
   - Output: Patient-friendly version
   - Fallback: Original text (if Gemini unavailable)
   ↓
   Step 3: Translation (Gemini API)
   - Input: Simplified text
   - Output: Translated to selected language
   - Fallback: Original text (if Gemini unavailable)
   ↓
   Step 4: Embedding Generation (SentenceTransformers)
   - Input: Simplified text
   - Output: 384-dimensional vector
   - Fallback: None (always works)
   ↓
   Step 5: Vector Storage (ChromaDB)
   - Input: Embedding + metadata
   - Output: Stored in vector DB
   - Fallback: Warning logged
   ↓
   Step 6: MongoDB Storage
   - Input: Report data
   - Output: Stored in MongoDB
   - Fallback: CRITICAL ERROR (pipeline fails)
   ↓

4. RESPONSE SENT TO FRONTEND
   ↓
   {
     "success": true/false,
     "report_id": "...",
     "data": {
       "original_text": "...",
       "simplified_text": "...",
       "translated_text": "...",
       "summary": "...",
       "key_findings": [...]
     }
   }
   ↓

5. FRONTEND DISPLAYS RESULTS
   ↓
   Show: Extracted text, simplified explanation, translations
         Key findings, health score, doctor notes
         Ask questions about the report (RAG)
```

### Error Handling Strategy

| Component | Failure | Behavior | User Impact |
|-----------|---------|----------|------------|
| **OCR** | File reading fails | Pipeline STOPS | Error message |
| **Gemini (Simplify)** | API key missing | Uses ORIGINAL text | No simplification |
| **Gemini (Translate)** | API key missing | Uses ORIGINAL text | No translation |
| **Embeddings** | Model fails | LogsWARNING, continues | Can't ask questions later |
| **ChromaDB** | Storage fails | Logs WARNING, continues | Report saved but not searchable |
| **MongoDB** | Connection fails | Pipeline STOPS + RETRY | Error, then retry with backoff |

---

## Performance & Limits

### Processing Times (Approximate)

| Step | Time | Notes |
|------|------|-------|
| **OCR** | 10-30s | Single page, depends on image quality |
| **Simplification** | 20-60s | Requires Gemini API call |
| **Translation** | 20-60s | Requires Gemini API call |
| **Embeddings** | 2-5s | Local SentenceTransformers |
| **Storage** | 1-2s | MongoDB write |
| **TOTAL** | 1-3 min | End-to-end |

### Limits

- **File Size**: Max 50MB per report
- **Text Length**: Max 100,000 characters (auto-chunked)
- **Concurrent Uploads**: Recommended max 5 simultaneous
- **Embeddings**: 384 dimensions - optimized for speed/accuracy tradeoff
- **Vector DB**: Can store unlimited embeddings (limited by disk space)
- **MongoDB**: Depends on Atlas tier (free: 5GB storage)

---

## Next Steps

1. ✅ Setup complete
2. ✅ Backend running
3. ✅ Frontend running
4. ✅ Tests passing
5. **→ Production Deployment**
   - Add HTTPS/SSL
   - Set `DEBUG=False`
   - Use strong `SECRET_KEY`
   - Configure backups for databases
   - Add monitoring & alerting

---

## Support & Resources

| Resource | Link |
|----------|------|
| **API Docs** | http://localhost:8000/docs |
| **MongoDB Setup** | https://www.mongodb.com/docs/guides/ |
| **Gemini API** | https://makersuite.google.com/ |
| **FastAPI Docs** | https://fastapi.tiangolo.com/ |
| **React Docs** | https://react.dev/ |

---

## Quick Command Reference

```bash
# Terminal 1: Backend
cd /d/medicalreport/backend
source venv/bin/activate  # or: venv\Scripts\activate on Windows
uvicorn main:app --reload

# Terminal 2: Frontend
cd /d/medicalreport/frontend-react
npm run dev

# Terminal 3: Testing
curl http://localhost:8000/api/health
```

---

**All 10 Critical Issues Fixed! ✅**

The system now:
- ✅ Has JWT authentication
- ✅ Handles MongoDB with retry logic
- ✅ Uses async properly (no event loop blocking)
- ✅ Gracefully falls back when Gemini API unavailable
- ✅ Integrates configuration properly
- ✅ Maps language codes correctly
- ✅ Has comprehensive error handling
- ✅ Works end-to-end with real AI pipeline

Good luck! 🚀
