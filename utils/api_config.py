import os

from dotenv import load_dotenv


DEFAULT_GOOGLE_GENERATIVE_LANGUAGE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def get_google_generative_language_base_url() -> str:
    load_dotenv()
    return os.getenv(
        "GOOGLE_GENERATIVE_LANGUAGE_BASE_URL",
        DEFAULT_GOOGLE_GENERATIVE_LANGUAGE_BASE_URL,
    ).rstrip("/")


def get_openai_base_url() -> str:
    load_dotenv()
    return os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).rstrip("/")
