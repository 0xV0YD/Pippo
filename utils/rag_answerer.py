import os

import requests
from dotenv import load_dotenv

from utils.api_config import get_google_generative_language_base_url
from utils.embedding_client import get_gemini_api_key
from utils.meeting_retriever import retrieve_meeting_chunks


DEFAULT_GEMINI_ANSWER_MODEL = "gemini-2.5-flash"


def get_answer_model() -> str:
    load_dotenv()
    return os.getenv("RAG_ANSWER_MODEL", os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_ANSWER_MODEL)).strip()


def build_meeting_context(chunks: list[dict]) -> str:
    context_blocks = []
    for index, chunk in enumerate(chunks, start=1):
        context_blocks.append(
            "\n".join(
                [
                    f"Source {index}",
                    f"Chunk ID: {chunk['chunk_id']}",
                    f"Meeting: {chunk['title']}",
                    f"Date: {chunk['date']}",
                    f"Chunk Type: {chunk['chunk_type']}",
                    f"Similarity Score: {chunk['score']:.4f}",
                    "Text:",
                    chunk["text"],
                ]
            )
        )
    return "\n\n---\n\n".join(context_blocks)


def answer_from_meeting_context(query: str, top_k: int = 3) -> dict:
    retrieved_chunks = retrieve_meeting_chunks(query, top_k=top_k)
    context = build_meeting_context(retrieved_chunks)
    model = get_answer_model()

    prompt = f"""You are Pippo's meeting knowledge assistant.
Answer the user's question using only the meeting context below.
If the context does not contain the answer, say you do not know from the available meeting records.
Keep the answer concise and conversational.
Do not include chunk IDs, similarity scores, or a Sources section.

Meeting context:
{context}

User question:
{query}
"""

    response = requests.post(
        f"{get_google_generative_language_base_url()}/models/{model}:generateContent",
        headers={
            "x-goog-api-key": get_gemini_api_key(),
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
            },
        },
        timeout=120,
    )
    if not response.ok:
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        raise ValueError(f"Gemini answer API error ({response.status_code}): {payload}")

    payload = response.json()
    candidates = payload.get("candidates", [])
    if not candidates:
        raise ValueError(f"Gemini answer API returned no candidates: {payload}")
    parts = candidates[0].get("content", {}).get("parts", [])
    answer = "".join(part.get("text", "") for part in parts).strip()
    if not answer:
        raise ValueError(f"Gemini answer API returned an empty answer: {payload}")

    return {
        "query": query,
        "answer": answer,
        "sources": retrieved_chunks,
    }


def format_rag_answer(result: dict) -> str:
    lines = [result["answer"].strip(), "", "Retrieved Chunks:"]
    for source in result["sources"]:
        lines.append(
            f"- {source['chunk_id']} | {source['title']} | {source['chunk_type']} | score {source['score']:.4f}"
        )
    return "\n".join(lines)


def format_user_rag_answer(result: dict) -> str:
    return result["answer"].strip()
