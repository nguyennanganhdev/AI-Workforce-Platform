import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Quản lý các biến môi trường cho Agent Coordination Service.
    Sẽ đọc từ file .env nếu có.
    """
    
    # 1. Môi trường chung
    ENV: str = Field(default="development", description="Môi trường chạy: development, production, test")
    DEBUG: bool = Field(default=True, description="Bật/Tắt chế độ Debug")
    LOG_LEVEL: str = Field(default="INFO", description="Mức độ log (INFO, DEBUG, ERROR)")
    
    # 2. Cấu hình Model (LLM)
    MODEL_PROVIDER: str = Field(default="openai", description="Nhà cung cấp LLM (openai, azure, v.v...)")
    MODEL_NAME: str = Field(default="gpt-5.6-luna", description="Tên Model cần dùng")
    MODEL_API_KEY: str = Field(default="", description="API Key cho LLM")
    MODEL_API_BASE: str | None = Field(default=None, description="URL Base nếu dùng private LLM/Azure")
    
    # 3. Xác thực (Authentication) với các service khác (Backend, Reception)
    SERVICE_API_KEY: str = Field(default="", description="Key xác thực nội bộ giữa các microservice")
    JWT_SECRET: str = Field(default="", description="Secret để giải mã JWT nếu cần")
    
    # 4. Trạng thái hoạt động (Health Check & Port)
    PORT: int = Field(default=8000, description="Cổng chạy dịch vụ")
    ENABLE_HEALTH_CHECK: bool = Field(default=True, description="Bật API /health")
    
    # Cấu hình Pydantic: Đọc file .env
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore" # Bỏ qua các biến không khai báo trong class này
    )

# Khởi tạo instance config duy nhất để dùng chung toàn app
config = Settings()

def get_settings() -> Settings:
    """Trả về cấu hình hệ thống (dành cho Dependency Injection nếu dùng FastAPI)"""
    return config
