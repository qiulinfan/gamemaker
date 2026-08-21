#!/usr/bin/env python3
"""Hosted art generation client for Meshy and Tencent Cloud.

Standard library only. Four subcommands:

  probe     Free, read-only capability mapping for a credential file.
  submit    Start one billable generation task (requires --acknowledge-billable).
  status    Free polling of one task.
  download  Fetch a completed task's artifacts into a fresh output directory
            and write a generation-receipt.json.

Safety contract:
  - `probe` performs only whitelisted free calls; it can never bill.
  - `submit` refuses to run without --acknowledge-billable (exit 2).
  - Credentials are read from the file at call time and never printed.
  - `download` writes only beneath an existing --output-root, into a fresh
    per-task subdirectory, and refuses to overwrite existing files.

Exit codes: 0 = success, 1 = operation failed, 2 = invalid or refused request.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MESHY_BASE = "https://api.meshy.ai"
MESHY_ENDPOINTS = {
    "text-to-3d": "openapi/v2/text-to-3d",
    "image-to-3d": "openapi/v1/image-to-3d",
    "multi-image-to-3d": "openapi/v1/multi-image-to-3d",
    "retexture": "openapi/v1/retexture",
    "remesh": "openapi/v1/remesh",  # the rigging 400 error cites /openapi/v2/remesh, but only v1 exists
    "rigging": "openapi/v1/rigging",
    "animations": "openapi/v1/animations",
    "text-to-image": "openapi/v1/text-to-image",
}
# action -> (service, version, query_action, region)
TENCENT_ACTIONS = {
    "SubmitHunyuanTo3DJob": ("ai3d", "2025-05-13", "QueryHunyuanTo3DJob", "ap-guangzhou"),
    "SubmitHunyuanTo3DProJob": ("ai3d", "2025-05-13", "QueryHunyuanTo3DProJob", "ap-guangzhou"),
    "SubmitHunyuanTo3DRapidJob": ("ai3d", "2025-05-13", "QueryHunyuanTo3DRapidJob", "ap-guangzhou"),
    "SubmitHunyuanImageJob": ("hunyuan", "2023-09-01", "QueryHunyuanImageJob", "ap-guangzhou"),
}
PROBE_SENTINEL_JOB = "probe-nonexistent-id"


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


# --------------------------- credentials ---------------------------

def load_meshy_key(path: Path) -> str:
    key = path.read_text(encoding="utf-8").strip()
    if not key.startswith("msy_") or len(key) < 20 or any(c.isspace() for c in key):
        fail(2, "CREDENTIALS_INVALID: expected a single msy_... key in the file")
    return key


def load_tencent_keys(path: Path) -> tuple[str, str]:
    sid = skey = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.lower().startswith("secretid:"):
            sid = line.split(":", 1)[1].strip()
        elif line.lower().startswith("secretkey:"):
            skey = line.split(":", 1)[1].strip()
    if not sid.startswith("AKID") or not skey:
        fail(2, "CREDENTIALS_INVALID: expected SecretId:AKID.../SecretKey:... lines")
    return sid, skey


# --------------------------- transports ---------------------------

def http_json(req: urllib.request.Request, timeout: int = 60) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except Exception:
            return exc.code, {"http_error": exc.code}
    except Exception as exc:
        return 0, {"transport_error": str(exc)}


def meshy_request(key: str, method: str, path: str, payload: dict | None = None) -> tuple[int, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{MESHY_BASE}/{path}",
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method=method,
    )
    return http_json(req)


def tc3_headers(
    sid: str,
    skey: str,
    service: str,
    action: str,
    version: str,
    body: str,
    timestamp: int,
    region: str = "",
) -> dict[str, str]:
    """Pure TC3-HMAC-SHA256 signing; deterministic for fixed inputs."""
    host = f"{service}.tencentcloudapi.com"
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    canonical_headers = f"content-type:application/json\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    scope = f"{date}/{service}/tc3_request"
    string_to_sign = (
        "TC3-HMAC-SHA256\n"
        f"{timestamp}\n{scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    signing_key = _hmac(_hmac(_hmac(("TC3" + skey).encode("utf-8"), date), service), "tc3_request")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "Authorization": (
            f"TC3-HMAC-SHA256 Credential={sid}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "Content-Type": "application/json",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
    }
    if region:
        headers["X-TC-Region"] = region
    return headers


def tencent_request(
    sid: str, skey: str, service: str, action: str, version: str, payload: dict, region: str = ""
) -> tuple[int, object]:
    body = json.dumps(payload)
    headers = tc3_headers(sid, skey, service, action, version, body, int(time.time()), region)
    req = urllib.request.Request(
        f"https://{service}.tencentcloudapi.com",
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    return http_json(req)


def tencent_error_code(response: object) -> str:
    """Return the effective error code; ai3d wraps the real code inside
    FailedOperation.InnerError's message, so unwrap known job-miss markers."""
    if isinstance(response, dict):
        error = response.get("Response", {}).get("Error")
        if isinstance(error, dict):
            code = str(error.get("Code", ""))
            message = str(error.get("Message", ""))
            if code == "FailedOperation.InnerError" and (
                "JobNotFound" in message or "JobNotExist" in message
            ):
                return "FailedOperation.JobNotFound"
            return code
    return ""


# --------------------------- probe ---------------------------

def probe_meshy(credentials: Path) -> dict:
    key = load_meshy_key(credentials)
    report: dict = {"provider": "meshy", "capabilities": []}
    status, balance = meshy_request(key, "GET", "openapi/v1/balance")
    report["auth_ok"] = status == 200
    report["balance"] = balance.get("balance") if isinstance(balance, dict) else None
    for name, path in MESHY_ENDPOINTS.items():
        code, _ = meshy_request(key, "GET", f"{path}?page_size=1")
        report["capabilities"].append(
            {"name": name, "available": code == 200, "evidence": f"GET /{path} -> {code}"}
        )
    return report


def probe_tencent(credentials: Path) -> dict:
    sid, skey = load_tencent_keys(credentials)
    report: dict = {"provider": "tencent-cloud", "capabilities": []}

    code, resp = tencent_request(sid, skey, "billing", "DescribeAccountBalance", "2018-07-09", {})
    if isinstance(resp, dict) and "Response" in resp and "Error" not in resp["Response"]:
        r = resp["Response"]
        report["auth_ok"] = True
        report["uin"] = r.get("Uin")
        report["cash_balance"] = r.get("Balance")
    else:
        # A permission-limited key still proves auth if the error is authz, not signature.
        err = tencent_error_code(resp)
        report["auth_ok"] = err not in ("AuthFailure.SignatureFailure", "AuthFailure.SecretIdNotFound")
        report["billing_error"] = err or resp

    def classify(service: str, action: str, version: str, payload: dict, region: str) -> dict:
        _, resp = tencent_request(sid, skey, service, action, version, payload, region)
        err = tencent_error_code(resp)
        if err == "":
            state = "available"
        elif "JobNotFound" in err or "JobNotExist" in err or err.startswith("InvalidParameter"):
            state = "available"  # reachable; our sentinel id simply does not exist
        elif err.startswith("AuthFailure") or err.startswith("UnauthorizedOperation"):
            state = "no-permission"
        elif "NotActivated" in err or "Arrears" in err or err.startswith("ResourceUnavailable"):
            state = "not-activated"
        else:
            state = f"unknown ({err})"
        return {"service": service, "action": action, "state": state, "evidence": err or "ok"}

    for label, service, action, version, payload, region in [
        ("hunyuan-3d-standard", "ai3d", "QueryHunyuanTo3DJob", "2025-05-13", {"JobId": PROBE_SENTINEL_JOB}, "ap-guangzhou"),
        ("hunyuan-3d-pro", "ai3d", "QueryHunyuanTo3DProJob", "2025-05-13", {"JobId": PROBE_SENTINEL_JOB}, "ap-guangzhou"),
        ("hunyuan-3d-rapid", "ai3d", "QueryHunyuanTo3DRapidJob", "2025-05-13", {"JobId": PROBE_SENTINEL_JOB}, "ap-guangzhou"),
        ("hunyuan-image", "hunyuan", "QueryHunyuanImageJob", "2023-09-01", {"JobId": PROBE_SENTINEL_JOB}, "ap-guangzhou"),
        ("hunyuan-llm-tokencount", "hunyuan", "GetTokenCount", "2023-09-01", {"Prompt": "hi"}, ""),
    ]:
        entry = classify(service, action, version, payload, region)
        entry["name"] = label
        report["capabilities"].append(entry)
    return report


# --------------------------- submit / status ---------------------------

def submit(args: argparse.Namespace) -> dict:
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    if args.provider == "meshy":
        key = load_meshy_key(Path(args.credentials))
        if args.endpoint not in MESHY_ENDPOINTS:
            fail(2, f"UNKNOWN_ENDPOINT: choose one of {sorted(MESHY_ENDPOINTS)}")
        _, balance = meshy_request(key, "GET", "openapi/v1/balance")
        code, resp = meshy_request(key, "POST", MESHY_ENDPOINTS[args.endpoint], payload)
        if code not in (200, 201, 202) or not isinstance(resp, dict) or "result" not in resp:
            fail(1, f"SUBMIT_FAILED: HTTP {code} {json.dumps(resp)[:400]}")
        return {
            "provider": "meshy",
            "endpoint": args.endpoint,
            "task_id": resp["result"],
            "balance_before": balance.get("balance") if isinstance(balance, dict) else None,
        }
    sid, skey = load_tencent_keys(Path(args.credentials))
    if args.action not in TENCENT_ACTIONS:
        fail(2, f"UNKNOWN_ACTION: choose one of {sorted(TENCENT_ACTIONS)}")
    service, version, _, region = TENCENT_ACTIONS[args.action]
    code, resp = tencent_request(sid, skey, service, args.action, version, payload, region)
    job_id = None
    if isinstance(resp, dict):
        job_id = resp.get("Response", {}).get("JobId")
    if not job_id:
        fail(1, f"SUBMIT_FAILED: HTTP {code} {json.dumps(resp, ensure_ascii=False)[:400]}")
    return {"provider": "tencent-cloud", "action": args.action, "task_id": job_id}


def status(args: argparse.Namespace) -> dict:
    if args.provider == "meshy":
        key = load_meshy_key(Path(args.credentials))
        if args.endpoint not in MESHY_ENDPOINTS:
            fail(2, f"UNKNOWN_ENDPOINT: choose one of {sorted(MESHY_ENDPOINTS)}")
        code, resp = meshy_request(key, "GET", f"{MESHY_ENDPOINTS[args.endpoint]}/{args.task_id}")
        if code != 200:
            fail(1, f"STATUS_FAILED: HTTP {code} {json.dumps(resp)[:400]}")
        return resp  # includes status/progress and artifact URLs when done
    sid, skey = load_tencent_keys(Path(args.credentials))
    if args.action not in TENCENT_ACTIONS:
        fail(2, f"UNKNOWN_ACTION: choose one of {sorted(TENCENT_ACTIONS)}")
    service, version, query_action, region = TENCENT_ACTIONS[args.action]
    code, resp = tencent_request(
        sid, skey, service, query_action, version, {"JobId": args.task_id}, region
    )
    if not isinstance(resp, dict) or "Response" not in resp:
        fail(1, f"STATUS_FAILED: HTTP {code} {json.dumps(resp, ensure_ascii=False)[:400]}")
    return resp["Response"]


# --------------------------- download ---------------------------

def harvest_urls(node: object, urls: list[str]) -> None:
    if isinstance(node, str):
        if node.startswith("https://"):
            urls.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            harvest_urls(value, urls)
    elif isinstance(node, list):
        for value in node:
            harvest_urls(value, urls)


def download(args: argparse.Namespace) -> dict:
    output_root = Path(args.output_root)
    if not output_root.is_dir():
        fail(2, "OUTPUT_ROOT_MISSING: --output-root must be an existing directory")
    task_dir = output_root / f"{args.provider}-{args.task_id}"
    if task_dir.exists():
        fail(2, f"TASK_DIR_EXISTS: refusing to overwrite {task_dir}")

    task = status(args)
    urls: list[str] = []
    harvest_urls(task, urls)
    seen: set[str] = set()
    ordered = [u for u in urls if not (u in seen or seen.add(u))]
    if not ordered:
        fail(1, "NO_ARTIFACT_URLS: task has no downloadable https URLs yet (not finished?)")

    task_dir.mkdir()
    downloaded = []
    for url in ordered:
        name = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1] or "artifact"
        name = name.replace("\\", "_").replace("..", "_")[:120]
        target = task_dir / name
        stem, dot, ext = name.partition(".")
        counter = 1
        while target.exists():
            target = task_dir / f"{stem}-{counter}{dot}{ext}" if dot else task_dir / f"{name}-{counter}"
            counter += 1
        try:
            with urllib.request.urlopen(url, timeout=300) as resp, open(target, "wb") as out:
                digest = hashlib.sha256()
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    out.write(chunk)
                    digest.update(chunk)
            downloaded.append(
                {
                    "file": target.name,
                    "sha256": digest.hexdigest(),
                    "bytes": target.stat().st_size,
                    "url_host": url.split("/", 3)[2],
                }
            )
        except Exception as exc:
            downloaded.append({"file": target.name, "error": str(exc), "url_host": url.split("/", 3)[2]})

    receipt = {
        "provider": args.provider,
        "endpoint_or_action": getattr(args, "endpoint", None) or getattr(args, "action", None),
        "task_id": args.task_id,
        "task_status_snapshot": task.get("status") or task.get("Status"),
        "downloaded": downloaded,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "validation_status": "prototype",
        "validation_note": "Hosted output is unvalidated. Run the auto-ta Blender audit chain before any accepted/validated claim.",
    }
    (task_dir / "generation-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    receipt["task_dir"] = str(task_dir)
    return receipt


# --------------------------- CLI ---------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, provider_required: bool = True) -> None:
        p.add_argument("--provider", choices=["meshy", "tencent-cloud"], required=provider_required)
        p.add_argument("--credentials", required=True, help="path to the user's credential file")

    p_probe = sub.add_parser("probe", help="free read-only capability probe")
    common(p_probe)

    p_submit = sub.add_parser("submit", help="start one billable generation task")
    common(p_submit)
    p_submit.add_argument("--endpoint", help="meshy endpoint name")
    p_submit.add_argument("--action", help="tencent-cloud Submit* action name")
    p_submit.add_argument("--payload", required=True, help="path to JSON payload file")
    p_submit.add_argument(
        "--acknowledge-billable",
        action="store_true",
        help="required: confirms the user authorized this billable call",
    )

    p_status = sub.add_parser("status", help="free task status query")
    common(p_status)
    p_status.add_argument("--endpoint")
    p_status.add_argument("--action")
    p_status.add_argument("--task-id", required=True)

    p_download = sub.add_parser("download", help="download a finished task + write receipt")
    common(p_download)
    p_download.add_argument("--endpoint")
    p_download.add_argument("--action")
    p_download.add_argument("--task-id", required=True)
    p_download.add_argument("--output-root", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command in ("submit", "status", "download"):
        if args.provider == "meshy" and not args.endpoint:
            fail(2, "MISSING_ENDPOINT: meshy calls need --endpoint")
        if args.provider == "tencent-cloud" and not args.action:
            fail(2, "MISSING_ACTION: tencent-cloud calls need --action")
    if args.command == "probe":
        report = probe_meshy(Path(args.credentials)) if args.provider == "meshy" else probe_tencent(Path(args.credentials))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.command == "submit":
        if not args.acknowledge_billable:
            fail(2, "BILLABLE_NOT_ACKNOWLEDGED: pass --acknowledge-billable only after the user explicitly authorized this batch and its budget")
        print(json.dumps(submit(args), ensure_ascii=False, indent=2))
        return
    if args.command == "status":
        print(json.dumps(status(args), ensure_ascii=False, indent=2))
        return
    if args.command == "download":
        print(json.dumps(download(args), ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
