"""
Configuration management for the Jira Auto-Bug Mapping AI Agent.
Loads settings from environment variables with validation.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM Configuration (Groq Only) ---
    groq_api_key: str = Field(default="", description="Groq API key")
    groq_model: str = Field(default="llama-3.3-70b-versatile", description="Groq model name")
    embedding_provider: str = Field(default="local", description="local only")
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2", description="Embedding model name"
    )

    # --- OCR Configuration ---
    tesseract_path: str = Field(
        default="C:/Program Files/Tesseract-OCR/tesseract.exe",
        description="Path to Tesseract executable",
    )

    # --- RAG Configuration ---
    faiss_index_path: str = Field(
        default=str(BASE_DIR / "data" / "faiss_index"),
        description="Path to persist FAISS index",
    )
    chunk_size: int = Field(default=500, description="Chunk size in tokens")
    chunk_overlap: int = Field(default=100, description="Chunk overlap in tokens")
    top_k: int = Field(default=5, description="Top-K chunks to retrieve")
    similarity_threshold: float = Field(
        default=0.7, description="Minimum similarity score for retrieval"
    )
    confidence_threshold: float = Field(
        default=0.7, description="Minimum confidence to auto-submit"
    )

    # --- Server Configuration ---
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")

    # --- Paths ---
    tmp_dir: str = Field(
        default=str(BASE_DIR / ".tmp"), description="Temporary file directory"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton settings instance
settings = Settings()


def ensure_directories():
    """Create required directories if they don't exist."""
    dirs = [
        settings.tmp_dir,
        settings.faiss_index_path,
        str(BASE_DIR / "data"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def mask_token(token: str) -> str:
    """Mask sensitive tokens for logging. NEVER log full tokens."""
    if not token or len(token) < 8:
        return "*****"
    return token[:4] + "*" * (len(token) - 8) + token[-4:]


def get_ocr_status() -> dict:
    """Check availability of OCR engines."""
    tesseract_exists = os.path.exists(settings.tesseract_path)
    
    easyocr_exists = False
    try:
        import easyocr
        easyocr_exists = True
    except ImportError:
        pass
        
    return {
        "tesseract": tesseract_exists,
        "easyocr": easyocr_exists,
        "any": tesseract_exists or easyocr_exists
    }
