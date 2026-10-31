from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Shop Support Agent"
    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    api_prefix: str = "/api"

    database_url: str = (
        "mysql+pymysql://shop_support_app:CHANGE_ME@127.0.0.1:3306/"
        "shop_support_dev?charset=utf8mb4"
    )
    test_database_url: str = (
        "mysql+pymysql://shop_support_app:CHANGE_ME@127.0.0.1:3306/"
        "shop_support_test?charset=utf8mb4"
    )

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    session_cookie_name: str = "shop_support_session"
    session_cookie_secure: bool = False
    session_ttl_hours: int = 8

    seed_admin_email: str = "admin@qinghe.local"
    seed_admin_password: str = "ChangeMe123!"
    seed_admin_name: str = "店铺运营"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = 90.0
    deepseek_temperature: float = 0.2
    deepseek_max_tokens: int = 1000
    deepseek_input_price_cny_per_million: float = 1.0
    deepseek_output_price_cny_per_million: float = 4.0

    rag_top_k: int = 5
    rag_min_similarity: float = 0.40
    rag_use_rerank: bool = False
    rag_rerank_candidates: int = 12
    chat_prompt_version: str = "v2"
    chat_history_limit: int = 6
    chat_history_message_chars: int = 1200
    chat_max_message_chars: int = 1000
    tool_timeout_ms: int = 5000
    max_tool_calls_per_turn: int = 3

    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    embedding_batch_size: int = 8
    embedding_timeout_seconds: float = 60.0

    chroma_path: str = "./data/chroma_dev"
    chroma_collection: str = "knowledge_chunks"
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 10

    rate_limit_enabled: bool = True
    rate_limit_chat_per_minute: int = 20
    rate_limit_chat_per_hour: int = 120
    rate_limit_read_per_minute: int = 60
    rate_limit_feedback_per_minute: int = 30
    rate_limit_login_per_minute: int = 10
    trust_proxy_headers: bool = False
    security_headers_enabled: bool = True
    max_api_body_bytes: int = 262144
    pii_redaction_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_chroma_dir(self) -> Path:
        return (PROJECT_ROOT / self.chroma_path).resolve()

    @property
    def resolved_upload_dir(self) -> Path:
        return (PROJECT_ROOT / self.upload_dir).resolve()

    @property
    def has_deepseek_key(self) -> bool:
        return bool(self.deepseek_api_key.strip())

    @property
    def has_siliconflow_key(self) -> bool:
        return bool(self.siliconflow_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
