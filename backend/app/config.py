import os
from pydantic_settings import BaseSettings
from functools import lru_cache

# Find .env in project root or current directory
root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./payguard.db"
    
    # NOVA API (Server-side only)
    nova_api_key: str = ""
    nova_api_url: str = "https://www.aczen.in/nova-api/v1"
    
    # Application
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 10
    
    # Control Configuration
    po_price_tolerance: float = 0.05
    po_quantity_tolerance: float = 0.05
    
    # Approval Thresholds
    approval_threshold_low: float = 5000.0
    approval_threshold_medium: float = 25000.0
    
    class Config:
        env_file = [root_env, backend_env, ".env"]
        extra = "ignore"
        case_sensitive = False

@lru_cache()
def get_settings():
    return Settings()
