# Copyright (c) 2026 KumoStack Contributors
# Copyright (c) 2024 MiniStack Contributors
# Licensed under the MIT License. See LICENSE for details.
"""
AWS Organizations stub.

JSON 1.1 protocol, target prefix ``AWSOrganizationsV20161128``.

Models a single-master-account organization. The master is whatever account
the request is made under (resolved via ``get_account_id``); the org returns
itself as ALL-features by default. Accounts and OUs are stored in
account-scoped state so each tenant gets its own org.

Includes the ``Path`` field on Account and OrganizationalUnit per the
2026-03-31 AWS additive change.
"""

import copy
import json
import logging
import time

from kumostack.core.responses import (
    AccountScopedDict,
    error_response_json,
    get_account_id,
    new_uuid,
)

logger = logging.getLogger("organizations")


# Per-master-account state. Each account that calls Organizations gets its
# own org graph; that mirrors how local-emulator multi-tenancy works.
_orgs = AccountScopedDict()       # singleton "self" -> Organization dict
_accounts = AccountScopedDict()   # account_id -> Account dict
_ous = AccountScopedDict()        # ou_id -> OU dict (with ParentId)
_roots = AccountScopedDict()      # root_id -> Root dict (single root)
# SCPs are org-wide (management-account-level) — plain dicts, not account-scoped
_policies: dict = {}              # policy_id -> SCP dict
_attachments: dict = {}           # target_id -> [policy_id, ...]
# Separate registry for PATCH-updated attachment overrides (bypasses in-place mutation issues)
_scp_attachment_overrides: dict = {}  # policy_id -> [target_id, ...]


def reset():
    _orgs.clear()
    _accounts.clear()
    _ous.clear()
    _roots.clear()
    _policies.clear()
    _attachments.clear()


def get_state():
    return {
        "orgs": copy.deepcopy(_orgs),
        "accounts": copy.deepcopy(_accounts),
        "ous": copy.deepcopy(_ous),
        "roots": copy.deepcopy(_roots),
        "policies": copy.deepcopy(_policies),
        "attachments": copy.deepcopy(_attachments),
    }


def restore_state(data):
    if not data:
        return
    for store, key in (
        (_orgs, "orgs"), (_accounts, "accounts"),
        (_ous, "ous"), (_roots, "roots"),
        (_policies, "policies"), (_attachments, "attachments"),
    ):
        store.clear()
        for k, v in (data.get(key) or {}).items():
            store[k] = v


def _json(status, body):
    return status, {"Content-Type": "application/x-amz-json-1.1"}, json.dumps(body).encode()


def _ensure_org():
    """Lazily initialise the org for the current master account."""
    if "self" in _orgs:
        return
    master = get_account_id()
    org_id = "o-" + new_uuid().replace("-", "")[:10]
    root_id = "r-" + new_uuid().replace("-", "")[:6]
    _orgs["self"] = {
        "Id": org_id,
        "Arn": f"arn:aws:organizations::{master}:organization/{org_id}",
        "FeatureSet": "ALL",
        "MasterAccountArn": f"arn:aws:organizations::{master}:account/{org_id}/{master}",
        "MasterAccountId": master,
        "MasterAccountEmail": f"master+{master}@kumostack.local",
        "AvailablePolicyTypes": [
            {"Type": "SERVICE_CONTROL_POLICY", "Status": "ENABLED"},
        ],
    }
    _roots[root_id] = {
        "Id": root_id,
        "Arn": f"arn:aws:organizations::{master}:root/{org_id}/{root_id}",
        "Name": "Root",
        "PolicyTypes": [],
    }
    # Master account record
    _accounts[master] = {
        "Id": master,
        "Arn": f"arn:aws:organizations::{master}:account/{org_id}/{master}",
        "Email": f"master+{master}@kumostack.local",
        "Name": "Master Account",
        "Status": "ACTIVE",
        "JoinedMethod": "INVITED",
        "JoinedTimestamp": int(time.time()),
        "Path": "/",
        "_ParentId": root_id,
    }


def _public_account(a: dict) -> dict:
    return {k: v for k, v in a.items() if not k.startswith("_")}


def _public_ou(o: dict) -> dict:
    return {k: v for k, v in o.items() if not k.startswith("_")}


def _describe_organization(_payload):
    _ensure_org()
    return _json(200, {"Organization": dict(_orgs["self"])})


def _list_roots(_payload):
    _ensure_org()
    return _json(200, {"Roots": list(_roots.values()), "NextToken": None})


def _list_accounts(_payload):
    _ensure_org()
    return _json(200, {
        "Accounts": [_public_account(a) for a in _accounts.values()],
        "NextToken": None,
    })


def _describe_account(payload):
    _ensure_org()
    aid = payload.get("AccountId")
    if not aid:
        return error_response_json("InvalidInputException", "AccountId is required", 400)
    a = _accounts.get(aid)
    if not a:
        return error_response_json("AccountNotFoundException",
                                   f"Account {aid} not found", 400)
    return _json(200, {"Account": _public_account(a)})


def _list_organizational_units_for_parent(payload):
    _ensure_org()
    parent_id = payload.get("ParentId") or ""
    out = [_public_ou(o) for o in _ous.values() if o.get("_ParentId") == parent_id]
    return _json(200, {"OrganizationalUnits": out, "NextToken": None})


def _list_accounts_for_parent(payload):
    _ensure_org()
    parent_id = payload.get("ParentId") or ""
    out = [_public_account(a) for a in _accounts.values()
           if a.get("_ParentId") == parent_id]
    return _json(200, {"Accounts": out, "NextToken": None})


def _create_organizational_unit(payload):
    _ensure_org()
    parent_id = payload.get("ParentId")
    name = payload.get("Name")
    if not parent_id or not name:
        return error_response_json("InvalidInputException",
                                   "ParentId and Name are required", 400)
    org_id = _orgs["self"]["Id"]
    master = get_account_id()
    ou_id = f"ou-{parent_id.split('-')[-1][:4]}-{new_uuid().replace('-','')[:10]}"
    parent_ou = _ous.get(parent_id)
    parent_path = (parent_ou or {}).get("Path", "/")
    rec = {
        "Id": ou_id,
        "Arn": f"arn:aws:organizations::{master}:ou/{org_id}/{ou_id}",
        "Name": name,
        "Path": (parent_path.rstrip("/") + "/" + name + "/") if parent_path != "/" else f"/{name}/",
        "_ParentId": parent_id,
    }
    _ous[ou_id] = rec
    return _json(200, {"OrganizationalUnit": _public_ou(rec)})


def _describe_organizational_unit(payload):
    _ensure_org()
    ou_id = payload.get("OrganizationalUnitId")
    o = _ous.get(ou_id) if ou_id else None
    if not o:
        return error_response_json("OrganizationalUnitNotFoundException",
                                   f"OU {ou_id} not found", 400)
    return _json(200, {"OrganizationalUnit": _public_ou(o)})


def _delete_organizational_unit(payload):
    _ensure_org()
    ou_id = payload.get("OrganizationalUnitId")
    if not ou_id or ou_id not in _ous:
        return error_response_json("OrganizationalUnitNotFoundException",
                                   f"OU {ou_id} not found", 400)
    del _ous[ou_id]
    return _json(200, {})


# ── Service Control Policies ──────────────────────────────────────────────────

def _require_management_account():
    """Return an error response if the caller is not the organization master account."""
    caller = get_account_id()
    org = _orgs.get("self")
    if org and org.get("MasterAccountId") and org["MasterAccountId"] != caller:
        return error_response_json(
            "AccessDeniedException",
            f"You need management account permissions to perform this operation. "
            f"Caller: {caller}, MasterAccount: {org['MasterAccountId']}",
            403,
        )
    return None


def _create_policy(payload):
    _ensure_org()
    if err := _require_management_account():
        return err
    name    = payload.get("Name", "")
    desc    = payload.get("Description", "")
    content = payload.get("Content", '{"Version":"2012-10-17","Statement":[]}')
    ptype   = payload.get("Type", "SERVICE_CONTROL_POLICY")
    if not name:
        return error_response_json("InvalidInputException", "Name is required", 400)
    policy_id = "p-" + new_uuid().replace("-", "")[:8]
    policy = {
        "PolicyId":    policy_id,
        "PolicyName":  name,
        "Description": desc,
        "Type":        ptype,
        "AwsManaged":  False,
        "Content":     content,
        "Status":      "ENABLED",
        "AttachedEntities": [],
        "CreatedTimestamp": time.time(),
    }
    _policies[policy_id] = policy
    return _json(200, {"Policy": {"PolicySummary": {k: v for k, v in policy.items() if k != "Content"}, "Content": content}})


def _list_policies(payload):
    _ensure_org()
    filter_type = payload.get("Filter", "SERVICE_CONTROL_POLICY")
    result = [
        {"PolicySummary": {k: v for k, v in p.items() if k != "Content"}, "Content": p["Content"]}
        for p in _policies.values()
        if p.get("Type") == filter_type
    ]
    return _json(200, {"Policies": result})


def _describe_policy(payload):
    policy_id = payload.get("PolicyId", "")
    policy = _policies.get(policy_id)
    if not policy:
        return error_response_json("PolicyNotFoundException", f"Policy {policy_id} not found", 400)
    return _json(200, {"Policy": {"PolicySummary": {k: v for k, v in policy.items() if k != "Content"}, "Content": policy["Content"]}})


def _update_policy(payload):
    policy_id = payload.get("PolicyId", "")
    policy = _policies.get(policy_id)
    if not policy:
        return error_response_json("PolicyNotFoundException", f"Policy {policy_id} not found", 400)
    if "Name"        in payload: policy["PolicyName"]  = payload["Name"]
    if "Description" in payload: policy["Description"] = payload["Description"]
    if "Content"     in payload: policy["Content"]     = payload["Content"]
    return _json(200, {"Policy": {"PolicySummary": {k: v for k, v in policy.items() if k != "Content"}, "Content": policy["Content"]}})


def _delete_policy(payload):
    policy_id = payload.get("PolicyId", "")
    if policy_id not in _policies:
        return error_response_json("PolicyNotFoundException", f"Policy {policy_id} not found", 400)
    del _policies[policy_id]
    return _json(200, {})


def _attach_policy(payload):
    if err := _require_management_account():
        return err
    policy_id = payload.get("PolicyId", "")
    target_id = payload.get("TargetId", "")
    if not _policies.get(policy_id):
        return error_response_json("PolicyNotFoundException", f"Policy {policy_id} not found", 400)
    # Update attachments index
    attachments = _attachments.get(target_id, [])
    if policy_id not in attachments:
        attachments.append(policy_id)
    _attachments[target_id] = attachments
    # Update the persistent override registry
    current = _scp_attachment_overrides.get(policy_id, _policies[policy_id].get("AttachedEntities", []))
    if target_id not in current:
        current = list(current) + [target_id]
    _scp_attachment_overrides[policy_id] = current
    _policies[policy_id]["AttachedEntities"] = current
    return _json(200, {})


def _detach_policy(payload):
    if err := _require_management_account():
        return err
    policy_id = payload.get("PolicyId", "")
    target_id = payload.get("TargetId", "")
    attachments = _attachments.get(target_id, [])
    if policy_id in attachments:
        attachments.remove(policy_id)
    _attachments[target_id] = attachments
    policy = _policies.get(policy_id)
    if policy and target_id in policy.get("AttachedEntities", []):
        policy["AttachedEntities"].remove(target_id)
    return _json(200, {})


def _list_policies_for_target(payload):
    target_id = payload.get("TargetId", "")
    filter_type = payload.get("Filter", "SERVICE_CONTROL_POLICY")
    attached_ids = _attachments.get(target_id, [])
    result = [
        {"PolicySummary": {k: v for k, v in p.items() if k != "Content"}, "Content": p["Content"]}
        for pid in attached_ids
        if (p := _policies.get(pid)) and p.get("Type") == filter_type
    ]
    return _json(200, {"Policies": result})


def _list_targets_for_policy(payload):
    policy_id = payload.get("PolicyId", "")
    policy = _policies.get(policy_id)
    if not policy:
        return error_response_json("PolicyNotFoundException", f"Policy {policy_id} not found", 400)
    targets = [{"TargetId": t, "Type": "ORGANIZATIONAL_UNIT"} for t in policy.get("AttachedEntities", [])]
    return _json(200, {"Targets": targets})


def _enable_policy_type(payload):
    return _json(200, {"Root": {}})


def _disable_policy_type(payload):
    return _json(200, {"Root": {}})


# ── Custom read endpoint (used by dashboard directly) ────────────────────────

def evaluate_scps(account_id: str, action: str, resource: str = "*") -> tuple[bool, str | None]:
    """Check active SCPs for a DENY against (action, resource).

    Returns (allowed: bool, denial_reason: str | None).
    Checks SCPs attached to the given account_id or to 'all' / 'root'.
    """
    import fnmatch

    def _matches_action(pattern: str, action: str) -> bool:
        return fnmatch.fnmatch(action.lower(), pattern.lower())

    def _matches_resource(pattern: str, resource: str) -> bool:
        return fnmatch.fnmatch(resource.lower(), pattern.lower())

    for policy in _policies.values():
        if policy.get("Type") != "SERVICE_CONTROL_POLICY":
            continue
        if policy.get("Status") != "ENABLED":
            continue
        attached = policy.get("AttachedEntities", [])
        # An SCP applies if:
        #  • explicitly attached to this account or its OU/root
        #  • OR no attachments at all (treat as org-wide guardrail)
        if attached and account_id not in attached and "r-0001" not in attached and "root" not in attached and "*" not in attached:
            continue

        try:
            doc = json.loads(policy["Content"]) if isinstance(policy["Content"], str) else policy["Content"]
        except Exception:
            continue

        for stmt in doc.get("Statement", []):
            if stmt.get("Effect") != "Deny":
                continue

            # Skip statements with conditions we can't evaluate at the emulator level.
            # Real AWS evaluates context keys (aws:PrincipalType, aws:RequestedRegion, etc.)
            # at request time. Here we skip conditional denies to avoid false positives,
            # consistent with the "benefit of the doubt" principle.
            if stmt.get("Condition"):
                continue

            raw_actions = stmt.get("Action", [])
            actions = [raw_actions] if isinstance(raw_actions, str) else raw_actions

            raw_resources = stmt.get("Resource", "*")
            resources = [raw_resources] if isinstance(raw_resources, str) else raw_resources

            action_match = any(_matches_action(a, action) for a in actions)
            resource_match = any(_matches_resource(r, resource) for r in resources)

            if action_match and resource_match:
                sid = stmt.get("Sid", policy["PolicyName"])
                return False, (
                    f"Explicit deny from SCP '{policy['PolicyName']}' "
                    f"(statement: {sid}): action '{action}' on '{resource}' is denied."
                )

    return True, None


def set_scp_attachments(policy_id: str, targets: list):
    """Persist attachment overrides for a policy (called from custom API PATCH)."""
    _scp_attachment_overrides[policy_id] = list(targets)
    # Also update the policy dict for consistency
    p = _policies.get(policy_id)
    if p is not None:
        p["AttachedEntities"] = list(targets)


def set_scp_status(policy_id: str, status: str):
    """Persist status override for a policy."""
    p = _policies.get(policy_id)
    if p is not None:
        p["Status"] = status


def list_scps_raw():
    """Return SCPs as plain dicts for the custom dashboard API."""
    result = []
    for p in _policies.values():
        if p.get("Type") != "SERVICE_CONTROL_POLICY":
            continue
        pid = p["PolicyId"]
        # Prefer override registry over in-dict value
        attached = _scp_attachment_overrides.get(pid, p.get("AttachedEntities", []))
        result.append({
            "id":          pid,
            "name":        p["PolicyName"],
            "description": p.get("Description", ""),
            "effect":      _infer_effect(p.get("Content", "")),
            "services":    _infer_services(p.get("Content", "")),
            "attachedTo":  attached,
            "status":      p.get("Status", "ENABLED"),
            "content":     p.get("Content", ""),
        })
    return result


def _infer_effect(content_str: str) -> str:
    try:
        doc = json.loads(content_str) if isinstance(content_str, str) else content_str
        stmts = doc.get("Statement", [])
        effects = {s.get("Effect", "Allow") for s in stmts}
        return "DENY" if "Deny" in effects else "ALLOW"
    except Exception:
        return "ALLOW"


def _infer_services(content_str: str) -> list:
    try:
        doc = json.loads(content_str) if isinstance(content_str, str) else content_str
        services = set()
        for stmt in doc.get("Statement", []):
            raw_action = stmt.get("Action") or []
            actions = [raw_action] if isinstance(raw_action, str) else raw_action
            for action in actions:
                if isinstance(action, str):
                    svc = action.split(":")[0].upper() if ":" in action else action
                    if svc == "*":
                        return ["*"]
                    services.add(svc)
        return list(services) if services else ["*"]
    except Exception:
        return ["*"]


_DISPATCH = {
    "DescribeOrganization": _describe_organization,
    "ListRoots": _list_roots,
    "ListAccounts": _list_accounts,
    "DescribeAccount": _describe_account,
    "ListOrganizationalUnitsForParent": _list_organizational_units_for_parent,
    "ListAccountsForParent": _list_accounts_for_parent,
    "CreateOrganizationalUnit": _create_organizational_unit,
    "DescribeOrganizationalUnit": _describe_organizational_unit,
    "DeleteOrganizationalUnit": _delete_organizational_unit,
    # SCP
    "CreatePolicy":              _create_policy,
    "ListPolicies":              _list_policies,
    "DescribePolicy":            _describe_policy,
    "UpdatePolicy":              _update_policy,
    "DeletePolicy":              _delete_policy,
    "AttachPolicy":              _attach_policy,
    "DetachPolicy":              _detach_policy,
    "ListPoliciesForTarget":     _list_policies_for_target,
    "ListTargetsForPolicy":      _list_targets_for_policy,
    "EnablePolicyType":          _enable_policy_type,
    "DisablePolicyType":         _disable_policy_type,
}


async def handle_request(method, path, headers, body, query_params):
    target = headers.get("X-Amz-Target") or headers.get("x-amz-target") or ""
    op = target.split(".", 1)[1] if "." in target else target
    if not op:
        return error_response_json("InvalidAction", "missing X-Amz-Target", 400)

    body_text = body.decode("utf-8") if isinstance(body, bytes) else (body or "")
    try:
        payload = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError:
        return error_response_json("SerializationException", "invalid JSON body", 400)

    fn = _DISPATCH.get(op)
    if fn is None:
        return error_response_json("InvalidAction",
                                   f"Operation '{op}' not implemented", 400)
    return fn(payload)
