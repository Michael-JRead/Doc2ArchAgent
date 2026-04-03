# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
#
# Multi-stage Docker build for Doc2ArchAgent
#
# Usage:
#   docker build -t doc2archagent .
#   docker run -v $(pwd)/architecture:/workspace/architecture doc2archagent validate architecture/system.yaml
#
# With ML support:
#   docker build --build-arg INSTALL_ML=true -t doc2archagent:ml .

FROM python:3.12-slim AS base

# System dependencies for PDF/OCR processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY tools/requirements.txt tools/requirements.txt
COPY pyproject.toml .
RUN pip install --no-cache-dir -r tools/requirements.txt

# Optional ML dependencies
ARG INSTALL_ML=false
RUN if [ "$INSTALL_ML" = "true" ]; then \
        pip install --no-cache-dir doclayout-yolo onnxruntime Pillow; \
    fi

# Copy application
COPY . .

# Default: run validation
ENTRYPOINT ["python", "-m"]
CMD ["tools.validate", "--help"]
