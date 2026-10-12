# VISHWAS Architecture Documentation

## Overview

VISHWAS is an AI-powered call fraud detection platform designed to analyze authorized call recordings and identify potential fraud patterns, suspicious requests, impersonation attempts, and other security threats.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         VISHWAS Platform                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐              ┌──────────────┐                 │
│  │   Android    │              │     Web      │                 │
│  │     App      │◄────────────►│  Dashboard   │                 │
│  │  (Kotlin)    │              │ (Streamlit)  │                 │
│  └──────────────┘              └──────────────┘                 │
│         │                               │                        │
│         │         HTTP/REST API         │                        │
│         └───────────────┬───────────────┘                        │
│                         │                                        │
│                  ┌──────▼────────┐                               │
│                  │   FastAPI     │                               │
│                  │   Backend     │                               │
│                  └───────┬───────┘                               │
│                          │                                       │
│           ┌──────────────┼──────────────┐                        │
│           │              │              │                        │
│    ┌──────▼────┐  ┌─────▼─────┐ ┌─────▼──────┐                 │
│    │   File    │  │  Analysis │ │  Database  │                 │
│    │  Storage  │  │  Service  │ │ (SQLite)   │                 │
│    └───────────┘  └───────────┘ └────────────┘                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 1 Architecture (Current)

Phase 1 focuses on building a solid foundation with a working end-to-end workflow using mock analysis:

**Components:**
1. **Backend (FastAPI)** - RESTful API server
2. **Web Dashboard (Streamlit)** - Web-based UI
3. **Android App (Kotlin + Jetpack Compose)** - Mobile application
4. **Database (SQLite)** - Data persistence
5. **Mock Analysis Service** - Simulated fraud detection

### Future Architecture (Phases 2-5)

```
Recording Upload
       ↓
   Perception (Speech-to-Text, Audio Features)
       ↓
   Evidence Extraction (Pattern Detection)
       ↓
   Content & Knowledge (Context Understanding)
       ↓
   Adversarial Reasoning (Threat Analysis)
       ↓
   Deterministic Decision (Risk Assessment)
       ↓
   Action (Recommendations)
       ↓
   Clients (Android, Web)
```

## Component Details

### 1. Backend (FastAPI)

**Technology Stack:**
- Framework: FastAPI 0.109+
- Server: Uvicorn
- Language: Python 3.11+
- Validation: Pydantic v2

**Responsibilities:**
- API endpoint management
- Request/response validation
- File upload handling
- Database operations
- Analysis orchestration
- Error handling

**Key Modules:**
- `app/main.py` - Application entry point
- `app/core/` - Configuration and logging
- `app/api/routes/` - API endpoints
- `app/models/` - Database models
- `app/schemas/` - Pydantic schemas
- `app/services/` - Business logic
- `app/database/` - Database session management

**API Structure:**
- Base URL: `/api/v1`
- OpenAPI docs: `/docs`
- Health check: `/api/v1/health`
- Calls: `/api/v1/calls/*`

### 2. Database (SQLite)

**Schema:**

**CallRecord Table:**
- `id` (PK): UUID
- `original_filename`: User's filename
- `stored_filename`: Server filename
- `storage_reference`: File path
- `status`: queued | processing | completed | failed
- `analysis_mode`: mock | real
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `completed_at`: Timestamp (nullable)
- `error_message`: Text (nullable)

**AnalysisReport Table:**
- `id` (PK): Auto-increment
- `call_id` (FK): References CallRecord
- `transcript_json`: JSON string
- `agent_findings_json`: JSON string
- `risk_level`: low | medium | high | critical
- `risk_score`: Float (nullable)
- `reasons_json`: JSON string
- `recommended_actions_json`: JSON string
- `warnings_json`: JSON string
- `analysis_mode`: mock | real
- `created_at`: Timestamp

**Relationships:**
- One-to-one between CallRecord and AnalysisReport
- Cascade delete on CallRecord deletion

### 3. File Storage

**Configuration:**
- Default directory: `./storage/uploads`
- Configurable via `UPLOAD_DIR` environment variable
- Max file size: 50 MB (configurable)
- Allowed extensions: .wav, .mp3, .m4a

**Security Features:**
- Server-generated filenames (UUID-based)
- Extension validation
- MIME type validation (optional, requires python-magic)
- File size limits
- No path traversal vulnerabilities
- Private storage (not publicly accessible)

**File Naming:**
```
<uuid>.<extension>
Example: 550e8400-e29b-41d4-a716-446655440000.wav
```

### 4. Mock Analysis Service (Phase 1)

**Purpose:**
Demonstrates the complete analysis workflow before real AI models are integrated.

**Features:**
- Deterministic scenario selection
- Pre-defined transcript generation
- Simulated agent findings
- Risk level assignment
- Recommended actions
- Clear mock labeling

**Scenarios:**
1. **Suspicious** - High risk (authority impersonation, OTP request, urgency)
2. **Legitimate** - Low risk (professional inquiry, no suspicious patterns)

**Selection Logic:**
- Based on call_id hash (deterministic for testing)
- Configurable delay to simulate processing

**Output:**
- Always labeled with `is_mock: true`
- Clear warnings in report
- Never claims to be real fraud detection

### 5. Web Dashboard (Streamlit)

**Technology Stack:**
- Framework: Streamlit 1.31+
- HTTP client: Requests
- Language: Python 3.11+

**Pages:**
1. **Dashboard** - Overview and statistics
2. **Upload Recording** - File upload interface
3. **Analysis History** - List of all analyses
4. **About** - Project information

**Features:**
- Real-time status polling
- Interactive report display
- File upload with progress
- Backend health monitoring
- Mock analysis indicators

### 6. Android Application

**Technology Stack:**
- Language: Kotlin
- UI Framework: Jetpack Compose
- Material Design: Material 3
- Architecture: MVVM (ViewModel + StateFlow)
- Networking: Retrofit + OkHttp
- Minimum SDK: 24 (Android 7.0)
- Target SDK: 34 (Android 14)

**Architecture Layers:**
1. **UI Layer** (`ui/`) - Composable screens
2. **ViewModel Layer** (`viewmodel/`) - UI state management
3. **Data Layer** (`data/`) - Repository pattern
4. **Network Layer** (`network/`) - API service
5. **Models** (`models/`) - Data classes

**Screens:**
1. **Home** - Status and navigation
2. **Upload** - File selection and upload
3. **Results** - Analysis report display
4. **History** - List of previous analyses

**Key Features:**
- Storage Access Framework for file picking
- Background upload with progress
- Status polling until completion
- Offline state handling
- Error recovery

## Data Flow

### Upload and Analysis Flow

```
1. User selects audio file
   ↓
2. Client validates file locally (size, extension)
   ↓
3. Client sends POST /api/v1/calls
   ↓
4. Backend validates file
   ↓
5. Backend saves file with safe name
   ↓
6. Backend creates CallRecord (status: queued)
   ↓
7. Backend queues background analysis task
   ↓
8. Backend responds 202 Accepted with call_id
   ↓
9. Client polls GET /api/v1/calls/{call_id}/status
   ↓
10. Analysis service updates status to 'processing'
    ↓
11. Analysis service generates mock report
    ↓
12. Analysis service saves AnalysisReport
    ↓
13. Analysis service updates CallRecord status to 'completed'
    ↓
14. Client detects 'completed' status
    ↓
15. Client fetches GET /api/v1/calls/{call_id}/report
    ↓
16. Client displays report to user
```

### Error Handling Flow

```
If error during upload:
  → 400/413/500 response
  → Client shows error message
  → User can retry

If error during analysis:
  → CallRecord status = 'failed'
  → error_message populated
  → Client polls and detects failure
  → Client shows error message
  → User can upload new file
```

## Security Architecture

### Phase 1 Security (Current)

**Implemented:**
- File extension validation
- File size limits
- Server-generated filenames
- Path traversal prevention
- CORS configuration
- No code execution from uploads
- Safe error messages (no stack traces to client)

**Not Implemented (Phase 1 limitations):**
- Authentication/authorization
- Encryption at rest
- Encryption in transit (uses HTTP, not HTTPS)
- Rate limiting
- Multi-user isolation
- Audit logging
- Input sanitization for SQL injection (using ORM)

**Threat Model:**
- **In scope:** File upload attacks, path traversal
- **Out of scope:** Network attacks, authentication bypass, data breaches

### Production Security Requirements

For production deployment, implement:

1. **Authentication:**
   - User registration and login
   - JWT or session-based auth
   - API key management

2. **Authorization:**
   - Per-user data isolation
   - Role-based access control
   - Resource ownership validation

3. **Encryption:**
   - HTTPS/TLS for all communication
   - Database encryption at rest
   - Encrypted backups

4. **Network Security:**
   - Firewall rules
   - DDoS protection
   - Rate limiting
   - IP whitelisting (if applicable)

5. **Application Security:**
   - Input validation
   - SQL injection prevention (verify ORM usage)
   - XSS prevention
   - CSRF protection
   - Security headers

6. **Monitoring:**
   - Audit logging
   - Intrusion detection
   - Anomaly detection
   - Security event alerts

## Scalability Considerations

### Phase 1 Limitations

- SQLite (single-file database)
- Local file storage
- Synchronous request handling (except background tasks)
- No load balancing
- No caching
- No CDN

### Scaling Strategy

**Horizontal Scaling:**
1. Replace SQLite with PostgreSQL/MySQL
2. Use object storage (S3, MinIO) for recordings
3. Implement message queue (Celery, RabbitMQ) for analysis tasks
4. Add load balancer (Nginx, HAProxy)
5. Deploy multiple backend instances

**Vertical Scaling:**
1. Increase server resources (CPU, RAM)
2. Optimize database queries
3. Add database indexes
4. Implement caching (Redis, Memcached)

**Performance Targets (Future):**
- Upload: < 5s for 50MB file
- Analysis: < 30s for 5min recording
- API response: < 200ms for status checks
- Concurrent uploads: 100+
- Daily analysis capacity: 10,000+

## Future Phases

### Phase 2: Real Transcription
- Integrate Whisper or similar STT model
- Support multiple languages
- Speaker diarization
- Timestamp alignment

### Phase 3: Evidence Detection
- Implement detection agents:
  - Impersonation detection
  - Request analysis
  - Urgency/threat detection
  - Sentiment analysis
- Multi-agent coordination

### Phase 4: Knowledge Integration
- Build knowledge graph
- Entity recognition
- Context understanding
- Historical pattern matching

### Phase 5: Advanced Detection
- Adversarial reasoning models
- Confidence scoring
- Real-time analysis
- Continuous learning

## Technology Choices Rationale

**FastAPI:**
- Modern, fast, auto-documentation
- Async support for scalability
- Type hints and validation
- Easy WebSocket support (future)

**SQLite (Phase 1):**
- Zero configuration
- File-based (easy backup)
- Sufficient for development
- Easy migration path to PostgreSQL

**Streamlit:**
- Rapid prototyping
- Python-based (shared with backend)
- Auto-updates
- Simple deployment

**Jetpack Compose:**
- Modern Android UI toolkit
- Declarative paradigm
- Better than XML layouts
- Material Design 3 support

**Retrofit:**
- Industry standard for Android
- Type-safe HTTP client
- Coroutine support
- Easy error handling

## Development Principles

1. **API-First:** Documented contracts before implementation
2. **Type Safety:** Pydantic schemas, Kotlin data classes
3. **Clear Separation:** Layers, modules, responsibilities
4. **Test Coverage:** Unit, integration, end-to-end
5. **Mock Labeling:** Clear distinction between mock and real
6. **Error Handling:** Graceful failures, user-friendly messages
7. **Documentation:** Code comments, API docs, setup guides
8. **Security:** Input validation, safe defaults, threat awareness

## Monitoring and Observability

### Current (Phase 1)

- Application logs (stdout)
- HTTP access logs (uvicorn)
- Database query logs (SQLAlchemy echo)

### Future

- Structured logging (JSON)
- Centralized log aggregation (ELK, Splunk)
- Metrics (Prometheus, Grafana)
- Distributed tracing (Jaeger, Zipkin)
- Error tracking (Sentry)
- Uptime monitoring
- Performance monitoring

## Deployment Architecture

### Phase 1 (Local Development)

```
Developer Machine:
  - Backend (port 8000)
  - Dashboard (port 8501)
  - SQLite (file)
  - Local file storage

Android Emulator:
  - Connects to 10.0.2.2:8000

Physical Device:
  - Connects to LAN IP:8000
```

### Future (Production)

```
Load Balancer
    ↓
API Servers (multiple instances)
    ↓
Message Queue
    ↓
Worker Nodes (analysis)
    ↓
Database (RDS/managed)
    ↓
Object Storage (S3)
```

## Conclusion

Phase 1 establishes a complete, working foundation that demonstrates the entire workflow with mock data. The architecture is designed for easy migration to real AI models in future phases without requiring rewrites of the client applications or API contracts.
