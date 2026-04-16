import argparse

import _bootstrap  # noqa: F401

from utils.rag_answerer import answer_from_meeting_context, format_rag_answer


def main() -> None:
    parser = argparse.ArgumentParser(description="Answer a question using retrieved meeting knowledge.")
    parser.add_argument("query", help="Question to answer from meeting knowledge.")
    parser.add_argument("--top-k", type=int, default=3, help="Number of meeting chunks to retrieve.")
    args = parser.parse_args()

    result = answer_from_meeting_context(args.query, top_k=args.top_k)
    print(format_rag_answer(result))


if __name__ == "__main__":
    main()
