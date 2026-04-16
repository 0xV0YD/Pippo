import _bootstrap  # noqa: F401

from utils.embedding_client import save_json
from utils.meeting_indexer import MEETING_EMBEDDINGS_FILE, build_meeting_embeddings_from_chunks


def build_meeting_embeddings() -> list[dict]:
    return build_meeting_embeddings_from_chunks()


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
