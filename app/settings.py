import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-not-secure")
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    CHALLENGE_COOKIE_NAME: str = os.getenv("CHALLENGE_COOKIE_NAME", "ai_human_sig")
    CHALLENGE_COOKIE_TTL_SECONDS: int = int(os.getenv("CHALLENGE_COOKIE_TTL_SECONDS", "1800"))
    ALLOW_TEST_DEBUG: bool = os.getenv("ALLOW_TEST_DEBUG", "true").lower() == "true"
    ALLOW_SEARCH_BOTS: bool = os.getenv("ALLOW_SEARCH_BOTS", "true").lower() == "true"
    ENV: str = os.getenv("ENV", "dev")

settings = Settings()
