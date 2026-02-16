"""Configuration management for JustInsurance Student Dashboard."""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Base configuration class."""

    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # Session
    SESSION_TYPE = os.getenv('SESSION_TYPE', 'filesystem')
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.getenv('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)  # Match Absorb token lifetime

    # Absorb LMS API
    ABSORB_BASE_URL = os.getenv('ABSORB_BASE_URL', 'https://rest.myabsorb.com')
    ABSORB_TENANT_URL = os.getenv('ABSORB_TENANT_URL', 'https://yourinsurancelicense.myabsorb.com')
    ABSORB_API_KEY = os.getenv('ABSORB_API_KEY')
    ABSORB_PRIVATE_KEY = os.getenv('ABSORB_PRIVATE_KEY')
    ABSORB_CLIENT_ID = os.getenv('ABSORB_CLIENT_ID')
    ABSORB_CLIENT_SECRET = os.getenv('ABSORB_CLIENT_SECRET')

    GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '1Hc7IUA8bZceLFlLdOPuGckDuV0MtqRcb5DPLeMhncbo')
    GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv('GOOGLE_SHEETS_CREDENTIALS_JSON', '')

    # SQLite snapshot database
    SNAPSHOT_DB_PATH = os.getenv('SNAPSHOT_DB_PATH', os.path.join(os.path.dirname(__file__), 'data', 'snapshots.db'))

    # Background sync scheduler (auto-sync on timer, no admin login required)
    SYNC_ABSORB_USERNAME = os.getenv('SYNC_ABSORB_USERNAME', '')
    SYNC_ABSORB_PASSWORD = os.getenv('SYNC_ABSORB_PASSWORD', '')
    SYNC_INTERVAL_HOURS = float(os.getenv('SYNC_INTERVAL_HOURS', '6'))

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', '10'))

    # CORS
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        required = ['ABSORB_API_KEY', 'ABSORB_PRIVATE_KEY']
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True


def get_config():
    """Get configuration based on environment."""
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig
    return DevelopmentConfig
