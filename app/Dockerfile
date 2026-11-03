FROM python@sha256:cf50a4f6ac4f026458b08d5222023d700ac806410dff5e9ca8728fa44f2b850f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EXITFORGE_DEPLOYMENT_MODE=public-demo EXITFORGE_ALLOW_CLOUD=0
WORKDIR /app
COPY requirements-web.lock .
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-web.lock
COPY exitforge ./exitforge
COPY static ./static
COPY examples ./examples
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3).read()"
CMD ["python","-m","uvicorn","exitforge.asgi:app","--host","0.0.0.0","--port","8000","--workers","1","--limit-concurrency","32","--timeout-keep-alive","5","--no-access-log","--no-server-header","--no-proxy-headers","--log-level","warning","--ws","none"]
