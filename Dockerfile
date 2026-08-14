# Dockerfile — 南京大学通知公告多 Agent 协作系统
# 构建: docker build -t whalequery .
# 运行（key 经 .env 挂载传入，不进命令行）:
#   cd query-agent && python -m src.keys set   # 首次引导录入 key → 写入 .env
#   docker run --rm -v $PWD/query-agent/.env:/app/query-agent/.env whalequery "问题"
FROM python:3.11-slim

# Node.js（crawler 是 JS）—— 用官方安装脚本，兼容 slim
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖清单先装（利用层缓存）
COPY explorer-agent/requirements.txt /app/explorer-agent/requirements.txt
COPY query-agent/requirements.txt /app/query-agent/requirements.txt
COPY rag-manager/requirements.txt /app/rag-manager/requirements.txt
RUN pip install --no-cache-dir \
    -r /app/explorer-agent/requirements.txt \
    -r /app/query-agent/requirements.txt \
    -r /app/rag-manager/requirements.txt

# 复制全部代码
COPY . /app

# 入口命令：默认 query
ENTRYPOINT ["python", "query-agent/query.py"]
