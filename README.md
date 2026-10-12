# VISHWAS - AI-Powered Call Fraud Detection Platform

VISHWAS is an intelligent system designed to analyze authorized call recordings and help identify potential fraud, suspicious requests, impersonation attempts, threats, urgency tactics, and attempts to obtain sensitive information.

## Current Status: Phase 1 - Foundation

Phase 1 establishes the complete project infrastructure with a working end-to-end workflow using mock analysis. The architecture is designed to support future integration of advanced AI models without requiring rewrites.

**Phase 1 Features:**
- ✅ FastAPI backend with RESTful API
- ✅ SQLite database with SQLAlchemy ORM
- ✅ Audio file upload and validation
- ✅ Mock analysis service (clearly labeled)
- ✅ Streamlit web dashboard
- ✅ Android application (Kotlin + Jetpack Compose)
- ✅ Comprehensive API documentation
- ✅ Automated testing suite

## Architecture Overview

```
Recording Upload → Perception → Evidence Extraction → Content & Knowledge → 
Adversarial Reasoning → Deterministic Decision → Action → Clients
```

**Phase 1** implements the infrastructure with mock analysis clearly labeled as such.

**Future Phases** will replace the mock service with:
- Multilingual speech-to-text transcription
- Audio perception and feature extraction
- Evidence extraction agents
- Knowledge graph integration
- Adversarial reasoning models
- Deterministic decision engine

## Repository Structure

```
vishwas/
├── android-app/          # Android mobile application
├── backend/              # FastAPI backend service
├── web-dashboard/        # Streamlit web interface
├── sample_recordings/    # Demo audio files
├── docs/                 # Documentation
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- Android Studio (for Android app)
- Java 17+ (for Android development)
- Git

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Initialize database
python -m app.database.init_db

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: http://localhost:8000
API documentation: http://localhost:8000/docs

### Web Dashboard Setup

```bash
cd web-dashboard
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the dashboard
streamlit run app.py
```

Dashboard will be available at: http://localhost:8501

### Android App Setup

```bash
cd android-app

# Open in Android Studio and sync Gradle
# Update backend URL in local configuration
# Run on emulator or physical device
```

For emulator: Use `http://10.0.2.2:8000` as backend URL
For physical device: Use your computer's LAN IP address (e.g., `http://192.168.1.100:8000`)

## Testing

```bash
cd backend
pytest tests/ -v
```

## API Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/calls` - Upload recording
- `GET /api/v1/calls` - List all calls (with pagination)
- `GET /api/v1/calls/{call_id}/status` - Check analysis status
- `GET /api/v1/calls/{call_id}/transcript` - Get transcript
- `GET /api/v1/calls/{call_id}/report` - Get analysis report

Full API documentation available in `docs/api_contract.md` and at `/docs` endpoint.

## Security and Privacy

⚠️ **Important:** Call recordings may contain sensitive personal information.

- Files are validated and stored securely
- Maximum upload size enforced
- Server-generated filenames prevent path traversal
- Private storage directory
- No execution of uploaded content
- Environment-based configuration for secrets

**Phase 1 Limitations:**
- No authentication/authorization (local development only)
- No encryption at rest
- No multi-user isolation
- Not production-ready

## Mock Analysis Mode

Phase 1 uses a mock analysis service to demonstrate the complete workflow. All reports are clearly labeled with `"is_mock": true` and `"analysis_mode": "mock"`.

Mock reports provide illustrative examples of:
- Transcript segments
- Agent findings
- Risk assessments
- Recommended actions

**These are NOT real AI predictions.** Future phases will implement actual multilingual speech recognition and fraud detection models.

## Documentation

- [Architecture Overview](docs/architecture.md)
- [API Contract](docs/api_contract.md)
- [Setup Guide](docs/setup.md)

## Development Status

**Completed:**
- [x] Backend infrastructure
- [x] Database models and schemas
- [x] File upload and validation
- [x] Mock analysis service
- [x] Web dashboard
- [x] Android app structure
- [x] API contracts
- [x] Automated tests
- [x] Documentation

**Planned (Future Phases):**
- [ ] Real speech-to-text transcription
- [ ] Multilingual support
- [ ] Audio feature extraction
- [ ] Evidence detection agents
- [ ] Knowledge graph integration
- [ ] Advanced fraud detection models
- [ ] User authentication
- [ ] Production deployment

## License

Copyright © 2026 VISHWAS Team. All rights reserved.

## Contact

For questions, issues, or contributions, please refer to the project documentation.
