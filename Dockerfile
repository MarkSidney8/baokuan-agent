FROM python:3.12-slim

WORKDIR /srv/baokuan

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PORT=8000
EXPOSE 8000

# 数据库文件 baokuan.db 落在 /srv/baokuan，挂载 volume 做持久化
VOLUME ["/srv/baokuan"]

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
