from __future__ import annotations

import argparse

from src.graph import ask


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the academic administration RAG agent.")
    parser.add_argument("question", help="Question to ask.")
    args = parser.parse_args()

    print(ask(args.question))


if __name__ == "__main__":
    main()
