import json
import math
import re
from pathlib import Path

from utils.embedding_client import embed_texts


MEETING_EMBEDDINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "meeting_embeddings.json"
BM25_K1 = 1.5
BM25_B = 0.75
RRF_K = 60
HYBRID_CANDIDATE_MULTIPLIER = 4


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


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def calculate_bm25_scores(query: str, chunks: list[dict]) -> dict[str, float]:
    query_terms = tokenize(query)
    if not query_terms or not chunks:
        return {chunk["chunk_id"]: 0.0 for chunk in chunks}

    tokenized_chunks = {chunk["chunk_id"]: tokenize(chunk["text"]) for chunk in chunks}
    document_count = len(chunks)
    average_length = sum(len(tokens) for tokens in tokenized_chunks.values()) / document_count
    document_frequencies = {}

    for tokens in tokenized_chunks.values():
        for term in set(tokens):
            document_frequencies[term] = document_frequencies.get(term, 0) + 1

    scores = {}
    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        tokens = tokenized_chunks[chunk_id]
        term_counts = {}
        for token in tokens:
            term_counts[token] = term_counts.get(token, 0) + 1

        score = 0.0
        document_length = len(tokens)
        for term in query_terms:
            term_frequency = term_counts.get(term, 0)
            if term_frequency == 0:
                continue

            document_frequency = document_frequencies.get(term, 0)
            idf = math.log(1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))
            denominator = term_frequency + BM25_K1 * (
                1 - BM25_B + BM25_B * document_length / average_length
            )
            score += idf * (term_frequency * (BM25_K1 + 1)) / denominator

        scores[chunk_id] = score

    return scores


def rank_chunk_ids(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)


def calculate_rrf_scores(rankings: list[list[str]], candidate_count: int) -> dict[str, float]:
    scores = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking[:candidate_count], start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank)
    return scores


def build_retrieval_result(chunk: dict, score: float, embedding_score: float, bm25_score: float, rrf_score: float) -> dict:
    return {
        "score": score,
        "embedding_score": embedding_score,
        "bm25_score": bm25_score,
        "rrf_score": rrf_score,
        "chunk_id": chunk["chunk_id"],
        "chunk_type": chunk["chunk_type"],
        "meeting_id": chunk["meeting_id"],
        "title": chunk["title"],
        "date": chunk["date"],
        "text": chunk["text"],
        "tags": chunk.get("tags", []),
        "attendees": chunk.get("attendees", []),
    }


def retrieve_meeting_chunks(query: str, top_k: int = 3) -> list[dict]:
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    embedded_chunks = load_meeting_embeddings()
    if not embedded_chunks:
        return []

    query_embedding = embed_texts([cleaned_query], task_type="RETRIEVAL_QUERY")[0]

    embedding_scores = {}
    for chunk in embedded_chunks:
        embedding_scores[chunk["chunk_id"]] = cosine_similarity(query_embedding, chunk["embedding"])

    bm25_scores = calculate_bm25_scores(cleaned_query, embedded_chunks)
    embedding_ranking = rank_chunk_ids(embedding_scores)
    bm25_ranking = rank_chunk_ids(bm25_scores)
    candidate_count = max(top_k * HYBRID_CANDIDATE_MULTIPLIER, top_k)
    rrf_scores = calculate_rrf_scores([embedding_ranking, bm25_ranking], candidate_count)
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in embedded_chunks}

    fused_results = [
        build_retrieval_result(
            chunks_by_id[chunk_id],
            score=rrf_score,
            embedding_score=embedding_scores.get(chunk_id, 0.0),
            bm25_score=bm25_scores.get(chunk_id, 0.0),
            rrf_score=rrf_score,
        )
        for chunk_id, rrf_score in rrf_scores.items()
    ]
    return sorted(fused_results, key=lambda item: item["score"], reverse=True)[:top_k]


def format_retrieval_results(results: list[dict]) -> str:
    if not results:
        return "No matching meeting chunks found."

    lines = []
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result['title']} [{result['chunk_type']}]")
        lines.append(f"   Date: {result['date']}")
        lines.append(f"   RRF Score: {result['rrf_score']:.4f}")
        lines.append(f"   Embedding Score: {result['embedding_score']:.4f}")
        lines.append(f"   BM25 Score: {result['bm25_score']:.4f}")
        lines.append(f"   Chunk: {result['chunk_id']}")
        lines.append("   Text:")
        for text_line in result["text"].splitlines():
            lines.append(f"   {text_line}")
        lines.append("")
    return "\n".join(lines).strip()
