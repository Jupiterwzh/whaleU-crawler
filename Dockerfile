# Dockerfile — 南京大学通知公告多 Agent 协作系统
# 构建: docker build -t whalequery .
# 运行: docker run -v $PWD/.env:/app/explorer-agent/.env -e CHERRYIN_API_KEY=$CHERRYIN_API_KEY whalequery query "最近有哪些通知"
FROM python:3.11-slim

# Node.js（crawler 是 JS）—— 用官方安装脚本，兼容 slim
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖清单先装（利用层缓存）
COPY explorer-agent/requirements.txt /app/explorer-agent/requirements.txt
RUN pip install --no-cache-dir -r /app/explorer-agent/requirements.txt

# 复制全部代码
COPY . /app

# 入口命令：默认 query；可用 whale-key 管理凭据
ENTRYPOINT ["python", "explorer-agent/query.py"]
