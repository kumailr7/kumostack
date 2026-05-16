FROM python:3.12-alpine AS builder

RUN pip install --no-cache-dir --no-compile \
        hypercorn==0.18.0 \
        "cbor2>=5.4.0" \
        "defusedxml>=0.7" \
        "docker>=7.0.0" \
        "pyyaml>=6.0" \
        "cryptography>=41.0" \
        "pymysql>=1.1" \
        "asyncssh>=2.14" \
        "boto3>=1.34" \
        "awscli"

# Strip awscli help examples (~25 MB) and Python cache files (~15 MB).
RUN rm -rf /usr/local/lib/python3.12/site-packages/awscli/examples \
    && find /usr/local/lib/python3.12/site-packages -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip*.dist-info \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip*

FROM python:3.12-alpine

LABEL maintainer="KumoStack" \
      description="Local AWS Service Emulator — drop-in LocalStack replacement"

# Upgrade base packages to pick up latest security patches.
RUN apk upgrade --no-cache && apk add --no-cache nodejs bash openssl && rm -f /usr/bin/wget /bin/wget \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip* \
              /usr/local/bin/pip*

WORKDIR /opt/kumostack

# Copy cleaned Python packages and CLI entrypoints from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/aws /usr/local/bin/aws
COPY --from=builder /usr/local/bin/aws_completer /usr/local/bin/aws_completer
COPY --from=builder /usr/local/bin/hypercorn /usr/local/bin/hypercorn

COPY bin/awslocal /usr/local/bin/awslocal
RUN chmod +x /usr/local/bin/awslocal

COPY kumostack/ kumostack/

RUN addgroup -S kumostack && adduser -S kumostack -G kumostack
RUN mkdir -p /tmp/kumostack-data/s3 && chown -R kumostack:kumostack /tmp/kumostack-data
RUN mkdir -p /docker-entrypoint-initaws.d/ready.d \
             /etc/localstack/init/boot.d \
             /etc/localstack/init/ready.d && \
    chown -R kumostack:kumostack /docker-entrypoint-initaws.d /etc/localstack
VOLUME /docker-entrypoint-initaws.d
VOLUME /etc/localstack/init

ARG MINISTACK_VERSION=dev
ENV MINISTACK_VERSION=${MINISTACK_VERSION} \
    GATEWAY_PORT=4566 \
    LOG_LEVEL=INFO \
    S3_PERSIST=0 \
    S3_DATA_DIR=/tmp/kumostack-data/s3 \
    REDIS_HOST=redis \
    REDIS_PORT=6379 \
    RDS_BASE_PORT=15432 \
    RDS_PERSIST=0 \
    ELASTICACHE_BASE_PORT=16379 \
    LAMBDA_EXECUTOR=local \
    USE_SSL=0 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2 \
    MALLOC_ARENA_MAX=2

EXPOSE 4566 2222

# Pure Python healthcheck — no curl dependency; USE_SSL for HTTP/HTTPS.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,ssl,urllib.request as r; t=os.environ.get('USE_SSL','').strip().lower() in ('1','true','yes'); r.urlopen(('https' if t else 'http')+'://localhost:4566/_kumostack/health',context=ssl._create_unverified_context() if t else None)" || exit 1

ENTRYPOINT ["python", "-m", "kumostack"]
