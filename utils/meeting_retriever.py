import json
import math
from pathlib import Path

from utils.embedding_client import embed_texts


MEETING_EMBEDDINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "meeting_embeddings.json"


def load_meeting_embeddings() -> list[dict]:
    return json.loads(MEETING_EMBEDDINGS_FILE.read_text(encoding="utf-8"))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError(f"Vector dimensions do not match: {len(left)} != {len(right)}")

    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def retrieve_meeting_chunks(query: str, top_k: int = 3) -> list[dict]:
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    embedded_chunks = load_meeting_embeddings()
    query_embedding = embed_texts([cleaned_query], task_type="RETRIEVAL_QUERY")[0]

    scored_chunks = []
    for chunk in embedded_chunks:
        score = cosine_similarity(query_embedding, chunk["embedding"])
        scored_chunks.append(
            {
                "score": score,
                "chunk_id": chunk["chunk_id"],
                "chunk_type": chunk["chunk_type"],
                "meeting_id": chunk["meeting_id"],
                "title": chunk["title"],
                "date": chunk["date"],
                "text": chunk["text"],
                "tags": chunk.get("tags", []),
                "attendees": chunk.get("attendees", []),
            }
        )

    return sorted(scored_chunks, key=lambda item: item["score"], reverse=True)[:top_k]


def format_retrieval_results(results: list[dict]) -> str:
    if not results:
        return "No matching meeting chunks found."

    lines = []
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result['title']} [{result['chunk_type']}]")
        lines.append(f"   Date: {result['date']}")
        lines.append(f"   Score: {result['score']:.4f}")
        lines.append(f"   Chunk: {result['chunk_id']}")
        lines.append("   Text:")
        for text_line in result["text"].splitlines():
            lines.append(f"   {text_line}")
        lines.append("")
    return "\n".join(lines).strip()
