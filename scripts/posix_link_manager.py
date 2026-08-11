#!/usr/bin/env python3
"""Receipt-backed POSIX link lifecycle for the Gamemaker bundle."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

from link_contract import ContractError, build_inventory, read_receipt, write_receipt


def link_state(entry: dict[str, str], require_recorded_type: bool) -> str:
    destination = Path(entry["destination"])
    if not os.path.lexists(destination):
        return "absent"
    if not destination.is_symlink():
        return "real-item"
    if require_recorded_type and entry.get("link_type") != "symlink":
        return "wrong-owner"
    actual = os.path.realpath(destination)
    return "owned" if actual == entry["source"] else "wrong-owner"


def remove_receipt_entry(entry: dict[str, str]) -> bool:
    state = link_state(entry, require_recorded_type=True)
    destination = Path(entry["destination"])
    if state == "absent":
        print(f"ABSENT  {destination}")
        return True
    if state != "owned":
        print(
            f"Refusing to remove unproven managed entry: {destination}; state={state}",
            file=sys.stderr,
        )
        return False
    destination.unlink()
    print(f"UNLINKED {destination}")
    return True


def receipt_entry(desired: dict[str, str]) -> dict[str, str]:
    return {**desired, "link_type": "symlink"}


def link_one(desired: dict[str, str], force: bool) -> dict[str, str]:
    destination = Path(desired["destination"])
    state = link_state(desired, require_recorded_type=False)
    if state == "owned":
        print(f"OK      {destination} -> {desired['source']}")
        return receipt_entry(desired)
    if state == "real-item":
        raise ContractError(f"Refusing to replace a real file or directory: {destination}")
    if state == "wrong-owner":
        if not force:
            raise ContractError(
                f"Conflicting link exists: {destination} (use --force to replace only this symlink)"
            )
        destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(desired["source"], target_is_directory=desired["kind"] == "directory")
    print(f"LINKED  {destination} -> {desired['source']}")
    return receipt_entry(desired)


def link(root: Path, codex_home: Path, force: bool) -> None:
    inventory = build_inventory(root, codex_home)
    receipt_path = Path(inventory["receipt_path"])
    old = read_receipt(receipt_path, codex_home, root)
    desired = {entry["destination"]: entry for entry in inventory["entries"]}
    kept: list[dict[str, str]] = []
    stale_failure = False
    for old_entry in old["entries"] if old else []:
        current = desired.get(old_entry["destination"])
        if current and all(old_entry[key] == current[key] for key in ("source", "kind")):
            kept.append(old_entry)
        elif not remove_receipt_entry(old_entry):
            kept.append(old_entry)
            stale_failure = True
    if stale_failure:
        write_receipt(receipt_path, inventory, kept)
        raise ContractError(
            "One or more stale Gamemaker entries could not be proven owned; current links were not changed"
        )

    installed: list[dict[str, str]] = []
    try:
        for entry in inventory["entries"]:
            installed.append(link_one(entry, force))
    except Exception:
        by_destination = {entry["destination"]: entry for entry in installed}
        for entry in kept:
            by_destination.setdefault(entry["destination"], entry)
        if by_destination:
            write_receipt(receipt_path, inventory, list(by_destination.values()))
        raise
    write_receipt(receipt_path, inventory, installed)
    print(f"Gamemaker links installed from {inventory['repository_root']}")
    print(f"Canonical product root: {desired_product_root(inventory)}")
    print(f"Install receipt: {receipt_path}")


def desired_product_root(inventory: dict[str, Any]) -> str:
    return next(
        entry["destination"]
        for entry in inventory["entries"]
        if entry["inventory_id"] == "product-root:gamemaker"
    )


def unlink(root: Path, codex_home: Path) -> None:
    receipt_path = codex_home / "state" / "gamemaker" / "install-receipt.json"
    receipt = read_receipt(receipt_path, codex_home, root)
    if receipt is None:
        print("No Gamemaker install receipt exists; nothing was removed.")
        return
    remaining = [entry for entry in receipt["entries"] if not remove_receipt_entry(entry)]
    if remaining:
        inventory = {
            "repository_root": receipt.get("repository_root", str(root.resolve())),
            "receipt_path": str(receipt_path),
            "codex_home": str(Path(os.path.abspath(codex_home.expanduser()))),
        }
        write_receipt(receipt_path, inventory, remaining)
        raise ContractError("Some receipt entries were preserved because ownership could not be proven")
    receipt_path.unlink()
    try:
        receipt_path.parent.rmdir()
    except OSError:
        pass
    print("Gamemaker receipt-owned links removed. Unrelated Codex files were preserved.")


def doctor(root: Path, codex_home: Path, skip_link_check: bool) -> None:
    inventory = build_inventory(root, codex_home)
    if skip_link_check:
        print("GAMEMAKER_BUNDLE_OK")
        print("GAMEMAKER_DOCTOR_OK")
        return
    receipt_path = Path(inventory["receipt_path"])
    receipt = read_receipt(receipt_path, codex_home, root)
    if receipt is None:
        raise ContractError(f"Missing managed install receipt: {receipt_path}")
    if receipt.get("repository_root") != inventory["repository_root"]:
        raise ContractError("Receipt repository root does not match this working tree")
    desired = {entry["destination"]: entry for entry in inventory["entries"]}
    recorded = {entry["destination"]: entry for entry in receipt["entries"]}
    if set(desired) != set(recorded):
        raise ContractError("Receipt destinations do not exactly match manifest link inventory")
    for destination, wanted in desired.items():
        entry = recorded[destination]
        if any(entry[key] != wanted[key] for key in ("source", "kind", "inventory_id")):
            raise ContractError(f"Receipt contract mismatch: {wanted['inventory_id']}")
        state = link_state(entry, require_recorded_type=True)
        if state != "owned":
            raise ContractError(f"Managed link is not owned: {destination}; state={state}")
        print(f"LINK OK {destination}")
    print("GAMEMAKER_BUNDLE_OK")
    print("GAMEMAKER_DOCTOR_OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("link", "unlink", "doctor"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-link-check", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "link":
            link(args.root, args.codex_home, args.force)
        elif args.command == "unlink":
            unlink(args.root, args.codex_home)
        else:
            doctor(args.root, args.codex_home, args.skip_link_check)
    except (ContractError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
