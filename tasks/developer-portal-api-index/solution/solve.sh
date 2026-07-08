#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_portal_index.py" <<'PY'
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import re


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
RELEASE_RE = re.compile(r"^- ([A-Za-z0-9_-]+) ([A-Z]+) ([^:]+): (.+)$")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_page(path: Path) -> dict[str, object]:
    lines = path.read_text().splitlines()
    end = lines.index("---", 1)
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1 :])
    return {
        "slug": meta["slug"],
        "title": meta["title"],
        "service": meta["service"],
        "status": meta["status"],
        "redirect_from": [item.strip() for item in meta.get("redirect_from", "").split(";") if item.strip()],
        "links": LINK_RE.findall(body),
    }


def main() -> None:
    root = Path.cwd()
    output = root / "output"
    output.mkdir(exist_ok=True)
    services = json.loads((root / "catalog" / "services.json").read_text())
    owners = {row["team"]: row for row in read_csv(root / "owners" / "teams.csv")}
    pages = {
        page["slug"]: page
        for page in (parse_page(path) for path in sorted((root / "docs" / "pages").glob("*.md")))
    }
    service_by_id = {row["service_id"]: row for row in services}

    endpoints = []
    for api_path in sorted((root / "apis").glob("*.json")):
        fragment = json.loads(api_path.read_text())
        service_id = fragment["info"]["service_id"]
        service = service_by_id[service_id]
        for route, methods in fragment["paths"].items():
            for method, spec in methods.items():
                endpoints.append(
                    {
                        "service_id": service_id,
                        "method": method.lower(),
                        "path": route,
                        "operation_id": spec["operationId"],
                        "visibility": spec["visibility"],
                        "deprecated": bool(spec.get("deprecated", False)),
                        "sunset": spec.get("sunset", ""),
                        "flags": list(spec.get("flags", [])),
                        "doc_slug": service["doc_slug"],
                        "owner_team": service["owner_team"],
                    }
                )
    endpoints.sort(key=lambda row: (row["service_id"], row["path"], row["method"]))

    release_notes = []
    for release_path in sorted((root / "releases").glob("*.md")):
        section = ""
        for line in release_path.read_text().splitlines():
            if line.startswith("## "):
                section = line.removeprefix("## ").strip().lower()
                continue
            match = RELEASE_RE.match(line)
            if not match or section not in {"added", "changed", "deprecated"}:
                continue
            service_id, method, route, note = match.groups()
            release_notes.append(
                {
                    "service_id": service_id,
                    "method": method.lower(),
                    "path": route,
                    "change_type": section,
                    "note": note,
                    "known_endpoint": any(
                        row["service_id"] == service_id
                        and row["method"] == method.lower()
                        and row["path"] == route
                        for row in endpoints
                    ),
                }
            )
    release_notes.sort(key=lambda row: (row["service_id"], row["method"], row["path"], row["change_type"]))

    endpoint_counts = Counter(row["service_id"] for row in endpoints)
    public_counts = Counter(row["service_id"] for row in endpoints if row["visibility"] == "public")
    deprecated_counts = Counter(row["service_id"] for row in endpoints if row["deprecated"])
    release_counts = Counter(row["service_id"] for row in release_notes)

    service_rows = []
    missing_services = []
    for service in sorted(services, key=lambda row: row["service_id"]):
        page = pages.get(service["doc_slug"])
        missing = not (page and page["service"] == service["service_id"] and page["status"] == "active")
        if missing:
            missing_services.append(service)
        service_rows.append(
            {
                "service_id": service["service_id"],
                "name": service["name"],
                "owner_team": service["owner_team"],
                "tier": service["tier"],
                "doc_slug": service["doc_slug"],
                "owner_slack": owners[service["owner_team"]]["slack"],
                "endpoint_count": endpoint_counts[service["service_id"]],
                "public_endpoint_count": public_counts[service["service_id"]],
                "deprecated_endpoint_count": deprecated_counts[service["service_id"]],
                "missing_doc": missing,
                "release_mentions": release_counts[service["service_id"]],
            }
        )

    redirect_inputs = [
        {"source": row["source"], "target": row["target"], "reason": row["reason"]}
        for row in read_csv(root / "docs" / "redirects.csv")
    ]
    for page in pages.values():
        for source in page["redirect_from"]:
            redirect_inputs.append({"source": source, "target": f"/docs/{page['slug']}", "reason": "page_alias"})
    redirects = []
    for row in redirect_inputs:
        service_id = ""
        status = "broken_missing"
        if row["target"].startswith("/docs/"):
            slug = row["target"].removeprefix("/docs/")
            page = pages.get(slug)
            if page:
                service_id = page["service"]
                status = "ok" if page["status"] == "active" else "broken_deprecated"
        redirects.append(
            {
                "source": row["source"],
                "target": row["target"],
                "service_id": service_id,
                "status": status,
                "reason": row["reason"],
            }
        )
    redirects.sort(key=lambda row: row["source"])

    broken_links = []
    for page in pages.values():
        for target in page["links"]:
            if not target.startswith("/docs/"):
                continue
            slug = target.removeprefix("/docs/")
            target_page = pages.get(slug)
            if target_page is None:
                broken_links.append({"source_slug": page["slug"], "target": target, "reason": "missing_page"})
            elif target_page["status"] != "active":
                broken_links.append({"source_slug": page["slug"], "target": target, "reason": "deprecated_page"})
    broken_links.sort(key=lambda row: (row["source_slug"], row["target"]))

    services_by_team: dict[str, list[dict[str, str]]] = defaultdict(list)
    for service in services:
        services_by_team[service["owner_team"]].append(service)
    owner_rows = []
    for team in sorted(owners):
        owned = sorted(services_by_team.get(team, []), key=lambda row: row["service_id"])
        owner_rows.append(
            {
                "team": team,
                "manager": owners[team]["manager"],
                "slack": owners[team]["slack"],
                "email": owners[team]["email"],
                "services": ";".join(row["service_id"] for row in owned),
                "public_endpoints": str(sum(public_counts[row["service_id"]] for row in owned)),
                "deprecated_endpoints": str(sum(deprecated_counts[row["service_id"]] for row in owned)),
                "missing_docs": str(
                    sum(
                        1
                        for row in owned
                        if not (
                            pages.get(row["doc_slug"])
                            and pages[row["doc_slug"]]["service"] == row["service_id"]
                            and pages[row["doc_slug"]]["status"] == "active"
                        )
                    )
                ),
            }
        )

    action_lines = ["# Developer Portal Actions", "", "## Missing Documentation"]
    if missing_services:
        for service in sorted(missing_services, key=lambda row: row["service_id"]):
            action_lines.append(f"- {service['service_id']} {service['name']} -> /docs/{service['doc_slug']}")
    else:
        action_lines.append("- none")
    action_lines.extend(["", "## Broken Links"])
    if broken_links:
        for row in broken_links:
            action_lines.append(f"- {row['source_slug']} -> {row['target']} ({row['reason']})")
    else:
        action_lines.append("- none")
    action_lines.extend(["", "## Deprecated Endpoints"])
    deprecated_endpoint_rows = [row for row in endpoints if row["deprecated"]]
    if deprecated_endpoint_rows:
        for row in deprecated_endpoint_rows:
            service = service_by_id[row["service_id"]]
            action_lines.append(
                f"- {row['service_id']} {row['method'].upper()} {row['path']} "
                f"sunset={row['sunset']} owner={owners[service['owner_team']]['slack']}"
            )
    else:
        action_lines.append("- none")
    (output / "docs_actions.md").write_text("\n".join(action_lines) + "\n")

    inventory = {
        "services": service_rows,
        "endpoints": endpoints,
        "redirects": redirects,
        "broken_links": broken_links,
        "release_notes": release_notes,
    }
    (output / "api_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    summary = {
        "services": len(service_rows),
        "endpoints": len(endpoints),
        "public_endpoints": sum(1 for row in endpoints if row["visibility"] == "public"),
        "deprecated_endpoints": sum(1 for row in endpoints if row["deprecated"]),
        "missing_docs": len(missing_services),
        "redirects": len(redirects),
        "broken_links": len(broken_links),
        "release_mentions": len(release_notes),
        "owner_teams": len(owners),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write_csv(
        output / "owner_matrix.csv",
        ["team", "manager", "slack", "email", "services", "public_endpoints", "deprecated_endpoints", "missing_docs"],
        owner_rows,
    )


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_portal_index.py
