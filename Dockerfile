# Base Python Image with GCC build tools for Cython compilation
FROM python:3.11-slim

WORKDIR /app

# Install system compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt .

# Install Python libraries
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Compile Cython matching engine in-place
RUN python setup.py build_ext --inplace

# Expose Streamlit web dashboard port
EXPOSE 8501

# Default command to run web dashboard
CMD ["streamlit", "run", "web_dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]

# Dockerfile spec v1.0
# In-place compilation
# Port 8501 exposed
