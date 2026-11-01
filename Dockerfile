FROM python:3.11-slim

# Múi giờ chuẩn Việt Nam GMT+7 (Render mặc định chạy UTC)
ENV TZ=Asia/Ho_Chi_Minh

# Cài đặt các gói hệ thống cơ bản
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
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
