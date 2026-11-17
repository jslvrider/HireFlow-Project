# Deployment

## Overview
One paragraph: how code gets from my laptop to production.
(PR → tests → merge → build → staging → approve → production)

## The pieces
For each file or tool, a few lines in your own words:
### Tests (pytest)
- Run locally first, before building the deployment.
- In the pipeline: on every PR and every release.
- Fake keys (conftest.py) let the code load without real credentials.
  Fakes (monkeypatch) replace Gemini, Pinecone, and GCS, so tests never
  call real services: fast, free, and the same result every time.
- Check: JSON parsing of LLM replies, the order of the retrieval stages
  and their return shape (including no results), and signed URL generation.
- Don't check: search quality or whether the real services work.
  That's for the eval set and staging.


## Environment variables
  | Variable | Controls | Local default |
  |---|---|---|
  | DB_PATH | Where the SQLite file lives | hireflow.db |
  | PINECONE_NAMESPACE | Which section of the index to use | resumes |
  | GCS_PREFIX | Folder in the bucket for uploads | "" (none) |

- **What it is**
- **When it runs** (once at setup / every PR / every merge)
- **Who runs it** (me, or which service account)

## One-time setup
The exact commands, in order, to build everything from scratch:
terraform apply, adding the secret, gcloud deploy apply, etc.
-First create test files and run tests locally.
-Local docker build is for testing the Dockerfile. Cloud Build builds the real images on every push to main.


## Everyday workflow
How to ship a change: branch → PR → merge → check staging → approve.

## Gotchas
Things that broke and why. For example:
- When test fails, determine if test or code needs rewriting. 
-“Signing URLs in Cloud Run needs IAM signing: no key file, so the runtime account needs Token Creator on itself.”
- Signed URLs need IAM signing in the cloud (no key file)
- "Names must match" across Terraform and the YAML files
-Upon running dockerfile locally, streamlit tried to look inside .streamlit for a secrets file, but streamlit was a file and caused an error on linux that was accepted on window. Updated .streamlit to a folder with a config.toml file to fix. 
-pypdf is an optional dependency, so it wasn’t installed automatically
-The real key name goes only in source=; inside the container it’s always /secrets/key.json
-Test every feature, because the untested one hides the broken setup
-“Seed the cloud DB once. After that, cloud and local databases diverge, so never re-upload the local one.”