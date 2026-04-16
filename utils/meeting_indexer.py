import json
from pathlib import Path

from utils.embedding_client import embed_texts, get_embedding_model, save_json
from utils.meeting_chunker import (
    MEETING_CHUNKS_FILE,
    MEETING_RECORDS_FILE,
    build_meeting_chunks,
    load_meeting_records,
    save_meeting_chunks,
)


MEETING_EMBEDDINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "meeting_embeddings.json"


def file_is_missing_or_older(path: Path, source_path: Path) -> bool:
    if not path.exists():
        return True
    return path.stat().st_mtime < source_path.stat().st_mtime


def build_meeting_embeddings_from_chunks() -> list[dict]:
    chunks = json.loads(MEETING_CHUNKS_FILE.read_text(encoding="utf-8"))
    model = get_embedding_model()
    existing_by_chunk_id = load_existing_embeddings_by_chunk_id(model)
    chunks_needing_embeddings = [
        chunk
        for chunk in chunks
        if not embedding_can_be_reused(chunk, existing_by_chunk_id.get(chunk["chunk_id"]), model)
    ]
    new_vectors = embed_texts(
        [chunk["text"] for chunk in chunks_needing_embeddings],
        task_type="RETRIEVAL_DOCUMENT",
    )
    new_vectors_by_chunk_id = {
        chunk["chunk_id"]: vector
        for chunk, vector in zip(chunks_needing_embeddings, new_vectors, strict=True)
    }

    embedded_chunks = []
    for chunk in chunks:
        existing = existing_by_chunk_id.get(chunk["chunk_id"])
        vector = (
            existing["embedding"]
            if embedding_can_be_reused(chunk, existing, model)
            else new_vectors_by_chunk_id[chunk["chunk_id"]]
        )
        embedded_chunks.append(
            {
                **chunk,
                "embedding_model": model,
                "embedding_dimensions": len(vector),
                "embedding": vector,
            }
        )
    return embedded_chunks


def load_existing_embeddings_by_chunk_id(model: str) -> dict[str, dict]:
    if not MEETING_EMBEDDINGS_FILE.exists():
        return {}

    embedded_chunks = json.loads(MEETING_EMBEDDINGS_FILE.read_text(encoding="utf-8"))
    return {
        chunk["chunk_id"]: chunk
        for chunk in embedded_chunks
        if chunk.get("embedding_model") == model
    }


def embedding_can_be_reused(chunk: dict, existing: dict | None, model: str) -> bool:
    return bool(
        existing
        and existing.get("embedding_model") == model
        and existing.get("text") == chunk["text"]
        and existing.get("embedding")
    )


def ensure_meeting_knowledge_current() -> list[str]:
    actions = []

    if file_is_missing_or_older(MEETING_CHUNKS_FILE, MEETING_RECORDS_FILE):
        records = load_meeting_records()
        chunks = build_meeting_chunks(records)
        save_meeting_chunks(chunks)
        actions.append("rebuilt meeting chunks")

    if file_is_missing_or_older(MEETING_EMBEDDINGS_FILE, MEETING_CHUNKS_FILE):
        embedded_chunks = build_meeting_embeddings_from_chunks()
        save_json(MEETING_EMBEDDINGS_FILE, embedded_chunks)
        actions.append("rebuilt meeting embeddings")

    return actions
