import json
from pathlib import Path

import _bootstrap  # noqa: F401

from utils.embedding_client import embed_texts, get_embedding_model, save_json


MEETING_CHUNKS_FILE = Path(__file__).resolve().parent.parent / "data" / "meeting_chunks.json"
MEETING_EMBEDDINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "meeting_embeddings.json"


def load_meeting_chunks() -> list[dict]:
    return json.loads(MEETING_CHUNKS_FILE.read_text(encoding="utf-8"))


def build_meeting_embeddings() -> list[dict]:
    chunks = load_meeting_chunks()
    texts = [chunk["text"] for chunk in chunks]
    vectors = embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
    model = get_embedding_model()

    embedded_chunks = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        embedded_chunks.append(
            {
                **chunk,
                "embedding_model": model,
                "embedding_dimensions": len(vector),
                "embedding": vector,
            }
        )
    return embedded_chunks


def main() -> None:
    embedded_chunks = build_meeting_embeddings()
    save_json(MEETING_EMBEDDINGS_FILE, embedded_chunks)
    print(f"Loaded {len(embedded_chunks)} meeting chunks")
    if embedded_chunks:
        print(
            f"Built embeddings with model {embedded_chunks[0]['embedding_model']} "
            f"and dimension {embedded_chunks[0]['embedding_dimensions']}"
        )


if __name__ == "__main__":
    main()
