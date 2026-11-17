FROM python:3.12-slim

WORKDIR /app

# Keep Python output unbuffered so logs show up immediately in Cloud Run
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

# 1. CPU-only PyTorch first (the default Linux build bundles GPU code: gigabytes we can't use)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 2. Then the app's dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Download the cross-encoder at build time, not on every startup
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# 4. Copy the code last
COPY . .

EXPOSE 8080

CMD ["sh", "-c", "exec streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.headless=true"]