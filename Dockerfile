# ==========================================
# 阶段一：构建者 (Builder)
# ==========================================
FROM python:3.10-slim AS builder

WORKDIR /build

# 【国内加速魔法 1】强行把 Debian 的系统软件源替换为阿里云源（兼容新老版本 Debian）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true && \
    sed -i 's|security.debian.org/debian-security|mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true

# 安装编译可能需要的底层 C/C++ 依赖 (现在下载速度会像火箭一样快！)
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# 【国内加速魔法 2】强行把 pip 源替换为阿里云 PyPI 镜像站！
RUN pip install --no-cache-dir --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ \
    && pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# ==========================================
# 阶段二：生产运行环境 (Runner)
# ==========================================
FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

# 创建非 root 用户
RUN useradd -m -u 1000 appuser

# 【本次核心修复！】以 root 身份提前建好 data 和 storage 文件夹，并把整个 /app 目录的所有权交给 appuser
RUN mkdir -p /app/data /app/storage && chown -R appuser:appuser /app

# 切换为安全用户
USER appuser

# 拷贝代码和刚才本地建的 data 目录进镜像
COPY --chown=appuser:appuser . .

EXPOSE 7860
CMD ["python", "app.py"]

