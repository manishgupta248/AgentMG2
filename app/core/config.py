"""
Central configuration for the Personal AI Agent.
Loads from .env via Pydantic Settings. No secret values are ever
hardcoded here — only field declarations and safe defaults.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM providers ---
    gemini_api_key: str = ""
    groq_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


    # --- Google OAuth ---
    google_credentials_path: Path = PROJECT_ROOT / "config" / "credentials.json"
    google_token_path: Path = PROJECT_ROOT / "config" / "token.json"

    # --- Paths ---
    data_dir: Path = PROJECT_ROOT / "data"
    logs_dir: Path = PROJECT_ROOT / "logs"
    db_path: Path = PROJECT_ROOT / "data" / "agent.db"

    # ---External Tools
    tesseract_cmd_path: Path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    
    # --- Logging ---
    log_level: str = "DEBUG"
    log_rotation: str = "10 MB"
    log_retention: str = "14 days"

    # --- Runtime ---
    tier2_fuzzy_threshold: float = 88.0


settings = Settings()