"""
VISHWAS FastAPI Application
AI-Powered Call Fraud Detection Platform
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.database.session import init_db
from app.api.routes import health, calls
from app.api.routes import analyze

# Setup logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting VISHWAS backend...")
    logger.info(f"Environment: {'DEBUG' if settings.debug else 'PRODUCTION'}")
    logger.info(f"Analysis mode: {settings.analysis_mode}")
    logger.info(f"Whisper model: {settings.whisper_model_size} ({settings.whisper_compute_type} on {settings.whisper_device})")
    logger.info(f"Voice layer: {'enabled' if settings.enable_voice_layer else 'disabled'}")
    
    # Health checks for real mode
    if settings.analysis_mode == "real":
        from app.audio.preprocessor import FFMPEG_AVAILABLE, AV_AVAILABLE
        if not FFMPEG_AVAILABLE and not AV_AVAILABLE:
            logger.error(
                "⚠️  CRITICAL: No audio converter available. "
                "Audio conversion will fail. Install ffmpeg or PyAV (pip install av)"
            )
        elif FFMPEG_AVAILABLE:
            logger.info("✓ ffmpeg available for audio conversion")
        elif AV_AVAILABLE:
            logger.info("✓ PyAV available for audio conversion")
        
        # Check if faster-whisper can be imported
        try:
            import faster_whisper  # noqa: F401
            logger.info("✓ faster-whisper installed for ASR")
        except ImportError:
            logger.warning(
                "⚠️  faster-whisper not installed. "
                "Install with: pip install faster-whisper"
            )
        
        # Check voice layer dependencies
        if settings.enable_voice_layer:
            try:
                import torch  # noqa: F401
                logger.info("✓ torch available for voice layer")
            except ImportError:
                logger.warning("⚠️  torch not installed - voice layer will be unavailable")
            
            try:
                import speechbrain  # noqa: F401
                logger.info("✓ speechbrain available for voiceprint matching")
            except ImportError:
                logger.warning("⚠️  speechbrain not installed - voiceprint matching unavailable")
    
    # Initialize database
    init_db()
    
    logger.info("VISHWAS backend started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down VISHWAS backend...")


# Create FastAPI application
app = FastAPI(
    title="VISHWAS API",
    description="AI-Powered Call Fraud Detection Platform",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(analyze.router, prefix="/api/v1", tags=["Analysis"])  # M2 routes
app.include_router(calls.router, prefix="/api/v1", tags=["Calls (legacy)"])  # backward compat


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": "INTERNAL_ERROR"
        }
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "VISHWAS API",
        "version": settings.app_version,
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
