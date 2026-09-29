# ---------------------------------------------------------------------------
# EVE Healthcare API — Dockerfile
#
# Multi-stage build:
#   Stage 1 (builder): install Python dependencies into a venv
#   Stage 2 (runtime): copy only the venv + source, no build tools
#
# Why multi-stage?
# The builder stage needs pip, gcc, and other tools. The runtime stage
# only needs Python and the installed packages. Keeping them separate
# produces a smaller, more secure final image.
# ---------------------------------------------------------------------------

# ---- Stage 1: builder ----
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies needed to build Python packages
# (e.g. bcrypt needs a C compiler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker caches this layer if requirements.txt
# hasn't changed, so subsequent builds are faster.
COPY requirements.txt .

# Install into a virtual environment inside the image
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ---- Stage 2: runtime ----
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system libraries (libpq for asyncpg PostgreSQL support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create a non-root user for security — never run as root in production
RUN adduser --disabled-password --no-create-home appuser
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Run the application.
# --host 0.0.0.0 makes it reachable from outside the container.
# --workers 1 is fine for development; scale up in production.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
