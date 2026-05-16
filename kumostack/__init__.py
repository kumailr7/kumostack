import os as _os

# Backward-compat shim: accept KUMOSTACK_* env vars (new canonical names) and
# mirror them to their legacy MINISTACK_* equivalents so all internal code that
# still reads MINISTACK_* continues to work unchanged.
# KUMOSTACK_* takes precedence when both are set.
_COMPAT_VARS = [
    "ACCOUNT_ID",
    "APIGW_JWKS_TIMEOUT_SECONDS",
    "APIGW_PROXY_TIMEOUT_SECONDS",
    "AUTOCREATE_AWS_MANAGED",
    "COGNITO_PRETOKEN_STRICT",
    "EDITION",
    "HOST",
    "HOSTNAME",
    "IMAGE_PREFIX",
    "IMDS_V2_REQUIRED",
    "LAMBDA_PROXY_URL",
    "OPENSEARCH_ENDPOINT",
    "REGION",
    "SSL_CERT",
    "SSL_KEY",
    "TEST_NO_AUTOSTART",
    "VERSION",
    "WORKER_THREADS",
]
for _k in _COMPAT_VARS:
    _new, _old = f"KUMOSTACK_{_k}", f"MINISTACK_{_k}"
    if _new in _os.environ:
        _os.environ.setdefault(_old, _os.environ[_new])

# Handle per-function proxy prefix (KUMOSTACK_LAMBDA_PROXY_<name>).
for _key, _val in list(_os.environ.items()):
    if _key.startswith("KUMOSTACK_LAMBDA_PROXY_"):
        _os.environ.setdefault(_key.replace("KUMOSTACK_", "MINISTACK_", 1), _val)
