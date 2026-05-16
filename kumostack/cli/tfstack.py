#!/usr/bin/env python3
"""
tfstack — Terraform CLI wrapper for KumoStack.

Generates a temporary ``kumostack_providers_override.tf`` file that redirects
every AWS provider endpoint to your local KumoStack instance, executes the
given ``terraform`` command, then removes the override file.

Usage:
    tfstack init
    tfstack plan
    tfstack apply -auto-approve
    tfstack destroy

Environment variables:
    AWS_ENDPOINT_URL           Override all service endpoints (e.g. http://localhost:4566)
    MINISTACK_HOSTNAME         KumoStack host           (default: localhost)
    GATEWAY_PORT               KumoStack port           (default: 4566)
    USE_SSL                    Use https instead of http (default: 0)
    S3_HOSTNAME                S3 virtual-host base     (default: s3.localhost.kumostack.org)
    TF_CMD                     Terraform binary         (default: terraform)
    DRY_RUN                    Write override but don't run terraform (default: 0)
    USE_EXEC                   Use os.execvpe instead of subprocess  (default: 0)
    CUSTOMIZE_ACCESS_KEY       Enable per-account access-key patching (default: 0)
    AWS_ACCESS_KEY_ID          Access key when CUSTOMIZE_ACCESS_KEY=1 (default: test)
    AWS_DEFAULT_REGION         AWS region               (default: us-east-1)
    TF_UNPROXIED_CMDS          Comma-separated commands to pass through unmodified
                               (default: fmt,validate,version)
    TS_PROVIDERS_FILE          Override filename        (default: kumostack_providers_override.tf)
    SKIP_ALIASES               Comma-separated provider aliases to skip
    ADDITIONAL_TF_OVERRIDE_LOCATIONS  Comma-separated extra dirs to receive the override
"""

import atexit
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _bool_env(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _str_env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, ""))
    except (ValueError, TypeError):
        return default


def _csv_env(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default).strip()
    return [v.strip() for v in raw.split(",") if v.strip()] if raw else []


# ---------------------------------------------------------------------------
# Resolved configuration
# ---------------------------------------------------------------------------

DRY_RUN             = _bool_env("DRY_RUN")
USE_EXEC            = _bool_env("USE_EXEC")
CUSTOMIZE_ACCESS_KEY = _bool_env("CUSTOMIZE_ACCESS_KEY")
USE_SSL             = _bool_env("USE_SSL")

TF_CMD              = _str_env("TF_CMD", "terraform")
TF_UNPROXIED_CMDS   = _csv_env("TF_UNPROXIED_CMDS", "fmt,validate,version")
SKIP_ALIASES        = _csv_env("SKIP_ALIASES")
ADDITIONAL_DIRS     = _csv_env("ADDITIONAL_TF_OVERRIDE_LOCATIONS")
TS_PROVIDERS_FILE   = _str_env("TS_PROVIDERS_FILE", "kumostack_providers_override.tf")

SCHEME = "https" if USE_SSL else "http"

# Resolve base endpoint from AWS_ENDPOINT_URL or MINISTACK_HOSTNAME + GATEWAY_PORT
_aws_ep = os.environ.get("AWS_ENDPOINT_URL", "").strip()
if _aws_ep:
    _p = urlparse(_aws_ep)
    MINISTACK_HOSTNAME = _p.hostname or "localhost"
    GATEWAY_PORT       = _p.port or 4566
else:
    MINISTACK_HOSTNAME = _str_env("MINISTACK_HOSTNAME", "localhost")
    GATEWAY_PORT       = _int_env("GATEWAY_PORT", 4566)

BASE_URL   = f"{SCHEME}://{MINISTACK_HOSTNAME}:{GATEWAY_PORT}"
S3_HOSTNAME = _str_env("S3_HOSTNAME", "s3.localhost.kumostack.org")
S3_URL      = f"{SCHEME}://{S3_HOSTNAME}:{GATEWAY_PORT}"

# ---------------------------------------------------------------------------
# All AWS Terraform provider endpoint keys.
# Grouped by service — only the first name in each group is written to the
# override file (avoids duplicate-key errors).  Extra names are aliases that
# older Terraform configs may use; we expand them so get_endpoint() resolves
# all of them correctly.
# ---------------------------------------------------------------------------

_ALIAS_GROUPS: list[list[str]] = [
    ["accessanalyzer"],
    ["account"],
    ["acm"],
    ["acmpca"],
    ["amg"],
    ["amp", "prometheus", "prometheusservice"],
    ["amplify"],
    ["apigateway"],
    ["apigatewayv2"],
    ["appautoscaling", "applicationautoscaling"],
    ["appconfig"],
    ["appconfigdata"],
    ["appfabric"],
    ["appflow"],
    ["appintegrations"],
    ["applicationinsights"],
    ["applicationsignals"],
    ["apprunner"],
    ["appstream"],
    ["appsync"],
    ["athena"],
    ["auditmanager"],
    ["autoscaling"],
    ["autoscalingplans"],
    ["b2bi"],
    ["backup"],
    ["backupgateway"],
    ["batch"],
    ["bcmdataexports"],
    ["bedrock"],
    ["bedrockagent"],
    ["budgets"],
    ["ce", "costexplorer"],
    ["chatbot"],
    ["chime"],
    ["chimesdkmediapipelines"],
    ["chimesdkmeetings"],
    ["chimesdkvoice"],
    ["cleanrooms"],
    ["cloud9"],
    ["cloudcontrol"],
    ["cloudformation"],
    ["cloudfront"],
    ["cloudfrontkeyvaluestore"],
    ["cloudhsmv2"],
    ["cloudsearch"],
    ["cloudtrail"],
    ["cloudwatch"],
    ["codeartifact"],
    ["codebuild"],
    ["codecatalyst"],
    ["codecommit"],
    ["codedeploy"],
    ["codeguruprofiler"],
    ["codegurureviewer"],
    ["codepipeline"],
    ["codestarconnections"],
    ["codestarnotifications"],
    ["cognitoidentity"],
    ["cognitoidentityprovider", "cognitoidp"],
    ["comprehend"],
    ["comprehendmedical"],
    ["computeoptimizer"],
    ["config", "configservice"],
    ["connect"],
    ["connectcases"],
    ["controltower"],
    ["cur", "costandusagereportservice"],
    ["customerprofiles"],
    ["dataexchange"],
    ["datasync"],
    ["datazone"],
    ["dax"],
    ["detective"],
    ["devicefarm"],
    ["devopsguru"],
    ["directconnect"],
    ["directoryservice", "ds"],
    ["dlm"],
    ["dms"],
    ["docdb"],
    ["docdbelastic"],
    ["drs"],
    ["dynamodb"],
    ["ec2"],
    ["ecr"],
    ["ecrpublic"],
    ["ecs"],
    ["efs"],
    ["eks"],
    ["elasticache"],
    ["elasticbeanstalk"],
    ["elasticloadbalancing"],
    ["elasticloadbalancingv2", "elbv2", "alb", "lb"],
    ["elasticsearch", "es"],
    ["elastictranscoder"],
    ["emr"],
    ["emrcontainers"],
    ["emrserverless"],
    ["eventbridge", "events"],
    ["evidently"],
    ["finspace"],
    ["firehose"],
    ["fis"],
    ["fms"],
    ["forecast"],
    ["fsx"],
    ["gamelift"],
    ["glacier"],
    ["globalaccelerator"],
    ["glue"],
    ["grafana"],
    ["greengrassv2"],
    ["guardduty"],
    ["healthlake"],
    ["iam"],
    ["identitystore"],
    ["imagebuilder"],
    ["inspector"],
    ["inspector2"],
    ["internetmonitor"],
    ["iot"],
    ["ioteventsdata"],
    ["iotfleethub"],
    ["iotfleetwise"],
    ["iotsitewise"],
    ["iottwinmaker"],
    ["ivs"],
    ["ivschat"],
    ["kafka"],
    ["kafkaconnect"],
    ["kendra"],
    ["keyspaces"],
    ["kinesis"],
    ["kinesisanalyticsv2"],
    ["kinesisvideo"],
    ["kms"],
    ["lakeformation"],
    ["lambda"],
    ["launchwizard"],
    ["lexmodelsv2", "lexv2models"],
    ["licensemanager"],
    ["lightsail"],
    ["location"],
    ["logs", "cloudwatchlogs"],
    ["lookoutmetrics"],
    ["m2"],
    ["macie2"],
    ["mediaconnect"],
    ["mediaconvert"],
    ["medialive"],
    ["mediapackage"],
    ["mediapackagev2"],
    ["mediastore"],
    ["mediastoredata"],
    ["memorydb"],
    ["mq"],
    ["mwaa"],
    ["neptune"],
    ["networkfirewall"],
    ["networkmanager"],
    ["opensearch"],
    ["opensearchserverless"],
    ["organizations"],
    ["osis"],
    ["outposts"],
    ["pinpoint"],
    ["pinpointsmsvoicev2"],
    ["pipes"],
    ["polly"],
    ["pricing"],
    ["qldb"],
    ["quicksight"],
    ["ram"],
    ["rbin"],
    ["rds"],
    ["rekognition"],
    ["resiliencehub"],
    ["resourceexplorer2"],
    ["resourcegroups"],
    ["resourcegroupstagging", "resourcegroupstaggingapi"],
    ["rolesanywhere"],
    ["route53"],
    ["route53domains"],
    ["route53recoverycontrolconfig"],
    ["route53recoveryreadiness"],
    ["route53resolver"],
    ["rum"],
    ["s3"],
    ["s3api"],
    ["s3control"],
    ["s3tables"],
    ["sagemaker"],
    ["sagemakerruntime"],
    ["scheduler"],
    ["schemas"],
    ["secretsmanager"],
    ["securityhub"],
    ["securitylake"],
    ["serverlessrepo"],
    ["servicecatalog"],
    ["servicecatalogappregistry"],
    ["servicediscovery"],
    ["servicequotas"],
    ["ses"],
    ["sesv2"],
    ["sfn", "stepfunctions"],
    ["shield"],
    ["signer"],
    ["sns"],
    ["sqs"],
    ["ssm"],
    ["ssoadmin"],
    ["sso"],
    ["storagegateway"],
    ["sts"],
    ["swf"],
    ["synthetics"],
    ["timestreamwrite"],
    ["transcribe"],
    ["transfer"],
    ["verifiedpermissions"],
    ["vpclattice"],
    ["waf"],
    ["wafregional"],
    ["wafv2"],
    ["wellarchitected"],
    ["workspaces"],
    ["xray"],
]

# Map every alias → canonical name (first in group)
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _grp in _ALIAS_GROUPS:
    for _alias in _grp:
        _ALIAS_TO_CANONICAL[_alias] = _grp[0]

# Canonical names only (written to the endpoints block)
CANONICAL_SERVICES: list[str] = [g[0] for g in _ALIAS_GROUPS]

# Services that need a subdomain-style URL
_SUBDOMAIN_SERVICES = {"mwaa", "s3control"}


# ---------------------------------------------------------------------------
# Endpoint resolution
# ---------------------------------------------------------------------------

def get_endpoint(service: str) -> str:
    """Return the KumoStack endpoint URL for a Terraform AWS provider service key."""
    canonical = _ALIAS_TO_CANONICAL.get(service, service)

    # Per-service env var override (e.g. S3_ENDPOINT=...)
    env_key = canonical.upper().replace("-", "_") + "_ENDPOINT"
    custom = os.environ.get(env_key, "").strip()
    if custom:
        return custom

    if canonical in ("s3", "s3api"):
        return S3_URL

    if canonical in _SUBDOMAIN_SERVICES:
        return f"{SCHEME}://{canonical}.localhost.kumostack.org:{GATEWAY_PORT}"

    return BASE_URL


# ---------------------------------------------------------------------------
# Credentials / region
# ---------------------------------------------------------------------------

def get_region() -> str:
    region = os.environ.get("AWS_DEFAULT_REGION", "").strip()
    if region:
        return region
    try:
        import boto3  # type: ignore
        return boto3.session.Session().region_name or "us-east-1"
    except Exception:
        pass
    return "us-east-1"


def get_access_key(tf_key: Optional[str] = None) -> str:
    if not CUSTOMIZE_ACCESS_KEY:
        return "test"
    key = (
        os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
        or tf_key
        or "test"
    )
    # Prefix prevents accidentally authenticating against real AWS
    if key.startswith("A"):
        key = "M" + key[1:]
    return key


# ---------------------------------------------------------------------------
# HCL2 parsing
# ---------------------------------------------------------------------------

def _hcl2():
    try:
        import hcl2  # type: ignore
        return hcl2
    except ImportError:
        sys.exit(
            "tfstack: python-hcl2 is required.\n"
            "  pip install 'python-hcl2>=8' packaging"
        )


def parse_tf_files(directory: str) -> list[dict]:
    lib = _hcl2()
    docs: list[dict] = []
    for tf in sorted(Path(directory).glob("*.tf")):
        if tf.name == TS_PROVIDERS_FILE:
            continue
        try:
            with tf.open() as fh:
                docs.append(lib.load(fh))
        except Exception:
            pass
    return docs


def find_provider_aliases(docs: list[dict]) -> list[str]:
    """Return all alias values declared in AWS provider blocks."""
    aliases: list[str] = []
    for doc in docs:
        for prov in doc.get("provider", []):
            block = prov.get("aws")
            if not block:
                continue
            blocks = block if isinstance(block, list) else [block]
            for b in blocks:
                alias = b.get("alias")
                if alias and alias not in aliases and alias not in SKIP_ALIASES:
                    aliases.append(alias)
    return aliases


def find_provider_access_key(docs: list[dict]) -> Optional[str]:
    for doc in docs:
        for prov in doc.get("provider", []):
            block = prov.get("aws")
            if not block:
                continue
            blocks = block if isinstance(block, list) else [block]
            for b in blocks:
                key = b.get("access_key")
                if key:
                    return key
    return None


def find_s3_backends(docs: list[dict]) -> list[dict]:
    backends: list[dict] = []
    for doc in docs:
        for tf_block in doc.get("terraform", []):
            be = tf_block.get("backend")
            if not be:
                continue
            s3 = (be if isinstance(be, dict) else {}).get("s3")
            if not s3:
                continue
            backends.append(s3[0] if isinstance(s3, list) else s3)
    return backends


def find_remote_states(docs: list[dict]) -> list[tuple[str, dict]]:
    results: list[tuple[str, dict]] = []
    for doc in docs:
        for data_block in doc.get("data", []):
            rs = data_block.get("terraform_remote_state", {})
            for name, cfg_list in rs.items():
                cfg = cfg_list[0] if isinstance(cfg_list, list) else cfg_list
                if cfg.get("backend") == "s3":
                    results.append((name, cfg))
    return results


# ---------------------------------------------------------------------------
# HCL generation
# ---------------------------------------------------------------------------

def _provider_block(
    alias: Optional[str],
    region: str,
    access_key: str,
    s3_path_style: bool,
) -> str:
    lines = ['provider "aws" {']
    lines += [
        f'  access_key                  = "{access_key}"',
        '  secret_key                  = "test"',
        '  skip_credentials_validation = true',
        '  skip_metadata_api_check     = true',
        '  skip_requesting_account_id  = true',
        f'  region                      = "{region}"',
    ]
    if s3_path_style:
        lines.append('  s3_use_path_style           = true')
    if alias:
        lines.append(f'  alias                       = "{alias}"')
    lines.append('  endpoints {')
    for svc in CANONICAL_SERVICES:
        ep = get_endpoint(svc)
        lines.append(f'    {svc:<30} = "{ep}"')
    lines += ['  }', '}']
    return "\n".join(lines)


def _s3_backend_block(cfg: dict, region: str, access_key: str) -> str:
    bucket     = cfg.get("bucket", "")
    key        = cfg.get("key", "terraform.tfstate")
    ws_prefix  = cfg.get("workspace_key_prefix", "")
    ddb_table  = cfg.get("dynamodb_table", "")

    lines = ['terraform {', '  backend "s3" {']
    lines += [
        f'    bucket                      = "{bucket}"',
        f'    key                         = "{key}"',
        f'    region                      = "{region}"',
        f'    access_key                  = "{access_key}"',
        '    secret_key                  = "test"',
        '    skip_credentials_validation = true',
        '    skip_metadata_api_check     = true',
    ]
    if ws_prefix:
        lines.append(f'    workspace_key_prefix        = "{ws_prefix}"')
    if ddb_table:
        lines.append(f'    dynamodb_table              = "{ddb_table}"')
    lines += [
        '    endpoints {',
        f'      s3       = "{get_endpoint("s3")}"',
        f'      iam      = "{BASE_URL}"',
        f'      sts      = "{BASE_URL}"',
        f'      dynamodb = "{BASE_URL}"',
        f'      sso      = "{BASE_URL}"',
        '    }',
        '  }',
        '}',
    ]
    return "\n".join(lines)


def _remote_state_block(name: str, cfg: dict, region: str, access_key: str) -> str:
    config: dict = dict(cfg.get("config", {}))
    config.update({
        "access_key": access_key,
        "secret_key": "test",
        "skip_credentials_validation": "true",
        "skip_metadata_api_check": "true",
        "region": config.get("region", region),
    })

    def _val(v: object) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, dict):
            inner = "\n".join(f'      {k} = "{vv}"' for k, vv in v.items())
            return "{\n" + inner + "\n    }"
        return f'"{v}"'

    workspace = cfg.get("workspace", "")
    lines = [f'data "terraform_remote_state" "{name}" {{']
    lines.append('  backend = "s3"')
    if workspace:
        lines.append(f'  workspace = "{workspace}"')
    lines.append('  config = {')
    for k, v in config.items():
        lines.append(f'    {k} = {_val(v)}')
    lines += ['  }', '}']
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build the full override file
# ---------------------------------------------------------------------------

def build_override(tf_dir: str) -> str:
    docs       = parse_tf_files(tf_dir)
    region     = get_region()
    access_key = get_access_key(find_provider_access_key(docs))
    # Path-style S3 when hostname has no "s3." subdomain prefix
    s3_path    = not S3_HOSTNAME.startswith("s3.")

    blocks: list[str] = [_provider_block(None, region, access_key, s3_path)]

    for alias in find_provider_aliases(docs):
        blocks.append(_provider_block(alias, region, access_key, s3_path))

    for s3_cfg in find_s3_backends(docs):
        blocks.append(_s3_backend_block(s3_cfg, region, access_key))

    for rs_name, rs_cfg in find_remote_states(docs):
        blocks.append(_remote_state_block(rs_name, rs_cfg, region, access_key))

    header = (
        "# Auto-generated by tfstack — do not edit manually.\n"
        "# This file is deleted automatically after `terraform` finishes.\n"
        f"# KumoStack endpoint: {BASE_URL}\n\n"
    )
    return header + "\n\n".join(blocks) + "\n"


# ---------------------------------------------------------------------------
# Override file lifecycle
# ---------------------------------------------------------------------------

def write_overrides(tf_dir: str, content: str) -> list[str]:
    dirs = [tf_dir, *ADDITIONAL_DIRS]
    written: list[str] = []
    for d in dirs:
        path = os.path.join(d, TS_PROVIDERS_FILE)
        try:
            with open(path, "w") as fh:
                fh.write(content)
            written.append(path)
        except OSError as exc:
            print(f"tfstack: warning: cannot write override to {d}: {exc}", file=sys.stderr)
    return written


def remove_overrides(paths: list[str]) -> None:
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _chdir_from_args(argv: list[str]) -> str:
    for arg in argv:
        m = re.match(r"-chdir=(.*)", arg)
        if m:
            return m.group(1)
    return os.getcwd()


def _subcommand(argv: list[str]) -> Optional[str]:
    for arg in argv:
        if not arg.startswith("-"):
            return arg
    return None


def main() -> None:
    argv = sys.argv[1:]

    # Version flag — print our version alongside terraform's
    if argv and argv[0] in ("--version", "-v", "-version"):
        print(f"tfstack v{__version__}", file=sys.stderr)

    subcmd = _subcommand(argv)

    # Pass formatting / validation commands straight through unchanged
    if subcmd in TF_UNPROXIED_CMDS:
        os.execvpe(TF_CMD, [TF_CMD, *argv], os.environ)
        return

    tf_dir = _chdir_from_args(argv)

    try:
        content = build_override(tf_dir)
    except Exception as exc:
        sys.exit(f"tfstack: failed to build provider override: {exc}")

    if DRY_RUN:
        dest = os.path.join(tf_dir, TS_PROVIDERS_FILE)
        print(f"tfstack: DRY_RUN — override written to {dest}", file=sys.stderr)
        with open(dest, "w") as fh:
            fh.write(content)
        print(content)
        return

    written = write_overrides(tf_dir, content)
    if not written:
        sys.exit("tfstack: could not write any provider override files")

    atexit.register(remove_overrides, written)

    cmd = [TF_CMD, *argv]

    if USE_EXEC:
        os.execvpe(TF_CMD, cmd, os.environ)
        return  # unreachable

    proc = subprocess.Popen(cmd)

    def _forward_signal(sig: int, _frame: object) -> None:
        try:
            proc.send_signal(sig)
        except Exception:
            pass

    signal.signal(signal.SIGINT, _forward_signal)
    proc.wait()
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
