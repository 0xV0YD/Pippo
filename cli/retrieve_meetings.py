import argparse

import _bootstrap  # noqa: F401

from utils.meeting_retriever import format_retrieval_results, retrieve_meeting_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve relevant meeting chunks for a query.")
    parser.add_argument("query", help="Natural-language query to search meeting knowledge.")
    parser.add_argument("--top-k", type=int, default=3, help="Number of matching chunks to return.")
    args = parser.parse_args()

    results = retrieve_meeting_chunks(args.query, top_k=args.top_k)
    print(format_retrieval_results(results))


if __name__ == "__main__":
    main()
