FROM python:3.11-slim

# System deps for GDAL + geospatial stack
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libspatialindex-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_VERSION=3.6.2
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

# Pre-create dirs the app expects at runtime
RUN mkdir -p data/temporal results/demo config/lease_boundaries

EXPOSE 8000

CMD ["uvicorn", "src.dispatch.dashboard_api:app", "--host", "0.0.0.0", "--port", "8000"]