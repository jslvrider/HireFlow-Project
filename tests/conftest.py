import os

# Fake values so modules can be imported without real credentials.
# Tests must never reach a real API; anything that would is monkeypatched.
import os

# Fake values so modules can be imported without real credentials.
# Tests must never reach a real API; anything that would is monkeypatched.
for key in ["GEMINI_API_KEY", "PINECONE_API_KEY", "GCS_BUCKET_NAME"]:
    os.environ.setdefault(key, "fake-value-for-tests")