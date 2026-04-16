import json
import os

import requests
from dotenv import load_dotenv

from utils.api_config import get_google_generative_language_base_url, get_openai_base_url


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"


def get_openai_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY in environment")
    return api_key


def get_embedding_model() -> str:
    load_dotenv()
    provider = get_embedding_provider()
    if provider == "gemini":
        return os.getenv("GEMINI_EMBEDDING_MODEL", DEFAULT_GEMINI_EMBEDDING_MODEL).strip() or DEFAULT_GEMINI_EMBEDDING_MODEL
    return os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL


def get_gemini_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY in environment")
    return api_key


def get_embedding_provider() -> str:
    load_dotenv()
    return os.getenv("EMBEDDING_PROVIDER", "gemini").strip().lower()


def embed_texts(texts: list[str], model: str | None = None, task_type: str | None = None) -> list[list[float]]:
    if not texts:
        return []

    provider = get_embedding_provider()
    if provider == "gemini":
        return embed_texts_with_gemini(texts, model=model, task_type=task_type)
    if provider == "openai":
        return embed_texts_with_openai(texts, model=model)
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")


def embed_texts_with_openai(texts: list[str], model: str | None = None) -> list[list[float]]:
    if not texts:
        return []

    response = requests.post(
        f"{get_openai_base_url()}/embeddings",
        headers={
            "Authorization": f"Bearer {get_openai_api_key()}",
            "Content-Type": "application/json",
        },
        json={
            "model": model or get_embedding_model(),
            "input": texts,
        },
        timeout=120,
    )
    if not response.ok:
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        raise ValueError(f"OpenAI embeddings API error ({response.status_code}): {payload}")
    payload = response.json()
    return [item["embedding"] for item in payload["data"]]


def embed_texts_with_gemini(
    texts: list[str],
    model: str | None = None,
    task_type: str | None = None,
) -> list[list[float]]:
    if not texts:
        return []

    embedding_model = model or get_embedding_model()
    gemini_task_type = task_type or "RETRIEVAL_DOCUMENT"
    vectors = []
    for text in texts:
        response = requests.post(
            f"{get_google_generative_language_base_url()}/models/{embedding_model}:embedContent",
            headers={
                "x-goog-api-key": get_gemini_api_key(),
                "Content-Type": "application/json",
            },
            json={
                "model": f"models/{embedding_model}",
                "content": {
                    "parts": [
                        {"text": text}
                    ]
                },
                "taskType": gemini_task_type,
            },
            timeout=120,
        )
        if not response.ok:
            try:
                payload = response.json()
            except Exception:
                payload = response.text
            raise ValueError(f"Gemini embeddings API error ({response.status_code}): {payload}")
        payload = response.json()
        embedding = (payload.get("embedding") or {}).get("values")
        if not embedding:
            raise ValueError(f"Gemini embeddings API returned no embedding values: {payload}")
        vectors.append(embedding)
    return vectors


def save_json(path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
