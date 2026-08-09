import argparse

from app.services.ingestion.ingestion_service import ingest_file


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a document into Chroma"
    )

    parser.add_argument(
        "file_path",
        help="Path to a TXT, PDF, or DOCX file",
    )

    args = parser.parse_args()

    chunks = ingest_file(
        args.file_path
    )

    print(
        f"Ingestion completed: {len(chunks)} chunks"
    )


if __name__ == "__main__":
    main()