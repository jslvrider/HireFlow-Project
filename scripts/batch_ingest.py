from pathlib import Path

from services.ingestion import ingest_resume


def batch_ingest():
    """
    Batch ingests every resume PDF in Resume_dataset, deriving a unique
    email per file from its filename.
    """
    successes = 0
    failures = 0

    for path in list(Path("Resume_dataset").glob("*.pdf"))[:15]:
        email = f"{path.stem}@example.com"
        print(f"Ingesting {path.name} as {email}...")

        try:
            with open(path, "rb") as file:
                ingest_resume(email, file)
                
            successes += 1
        except Exception as e:
            failures += 1
            print(f"Failed to ingest {path.name}: {e}")

    print(f"Done. {successes} succeeded, {failures} failed.")


if __name__ == "__main__":
    batch_ingest()
