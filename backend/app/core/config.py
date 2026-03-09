import os


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


DATABASE_URL = _get_env("DATABASE_URL")
OPENAI_API_KEY = _get_env("OPENAI_API_KEY")
NEWSAPI_KEY = _get_env("NEWSAPI_KEY")
NEWS_FETCH_MAX_ARTICLES_PER_COMPANY = int(_get_env("NEWS_FETCH_MAX_ARTICLES_PER_COMPANY", "5") or "5")
NEWS_RECENCY_DAYS_PRIMARY = int(_get_env("NEWS_RECENCY_DAYS_PRIMARY", "30") or "30")
NEWS_RECENCY_DAYS_EXPANDED = int(_get_env("NEWS_RECENCY_DAYS_EXPANDED", "90") or "90")

# Comma-separated list of allowed origins for CORS (Netlify site URL will go here)
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in (_get_env("CORS_ALLOW_ORIGINS", "") or "").split(",")
    if origin.strip()
]
