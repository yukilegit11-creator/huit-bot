FROM python:3.11-slim

# Cài đặt các gói hệ thống cơ bản
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Cấp quyền thực thi cho file khởi động
RUN chmod +x start.sh

# Mở cổng mặc định của web (Render sẽ gán qua biến môi trường $PORT)
EXPOSE 8000

# Khởi động cả Web Dashboard và Bot chạy ngầm 24/7
CMD ["./start.sh"]
