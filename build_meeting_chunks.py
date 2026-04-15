from utils.meeting_chunker import build_meeting_chunks, load_meeting_records, save_meeting_chunks


def main() -> None:
    records = load_meeting_records()
    chunks = build_meeting_chunks(records)
    save_meeting_chunks(chunks)
    print(f"Loaded {len(records)} meeting records")
    print(f"Built {len(chunks)} meeting chunks")


if __name__ == "__main__":
    main()
