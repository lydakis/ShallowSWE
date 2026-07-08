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


LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
NOTE = re.compile(r"^- ([A-Za-z0-9_-]+) ([A-Z]+) ([^:]+): (.+)$")


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def page(path: Path) -> dict[str, object]:
    lines = path.read_text().splitlines()
    end = lines.index("---", 1)
    meta: dict[str, str] = {}
    for raw in lines[1:end]:
        key, _, value = raw.partition(":")
        meta[key.strip()] = value.strip()
    return {
        "slug": meta["slug"],
        "title": meta["title"],
        "service": meta["service"],
        "status": meta["status"],
        "aliases": [item.strip() for item in meta.get("redirect_from", "").split(";") if item.strip()],
        "links": LINK.findall("\n".join(lines[end + 1 :])),
    }


def main() -> None:
    root = Path.cwd()
    out = root / "output"
    out.mkdir(exist_ok=True)
    services = json.loads((root / "catalog" / "services.json").read_text())
    service_by_id = {row["service_id"]: row for row in services}
    teams = {row["team"]: row for row in csv_rows(root / "owners" / "teams.csv")}
    pages = {item["slug"]: item for item in (page(path) for path in sorted((root / "docs" / "pages").glob("*.md")))}

    endpoints: list[dict[str, object]] = []
    for api_file in sorted((root / "apis").glob("*.json")):
        data = json.loads(api_file.read_text())
        sid = data["info"]["service_id"]
        svc = service_by_id[sid]
        for route in sorted(data["paths"]):
            for method in sorted(data["paths"][route]):
                spec = data["paths"][route][method]
                endpoints.append(
                    {
                        "service_id": sid,
                        "method": method.lower(),
                        "path": route,
                        "operation_id": spec["operationId"],
                        "visibility": spec["visibility"],
                        "deprecated": bool(spec.get("deprecated", False)),
                        "sunset": spec.get("sunset", ""),
                        "flags": list(spec.get("flags", [])),
                        "doc_slug": svc["doc_slug"],
                        "owner_team": svc["owner_team"],
                    }
                )
    endpoints.sort(key=lambda row: (row["service_id"], row["path"], row["method"]))
    endpoint_key = {(row["service_id"], row["method"], row["path"]) for row in endpoints}

    notes: list[dict[str, object]] = []
    for path in sorted((root / "releases").glob("*.md")):
        section = ""
        for line in path.read_text().splitlines():
            if line.startswith("## "):
                section = line[3:].strip().lower()
                continue
            match = NOTE.match(line)
            if match and section in {"added", "changed", "deprecated"}:
                sid, method, route, text = match.groups()
                lower = method.lower()
                notes.append(
                    {
                        "service_id": sid,
                        "method": lower,
                        "path": route,
                        "change_type": section,
                        "note": text,
                        "known_endpoint": (sid, lower, route) in endpoint_key,
                    }
                )
    notes.sort(key=lambda row: (row["service_id"], row["method"], row["path"], row["change_type"]))

    endpoint_count = Counter(row["service_id"] for row in endpoints)
    public_count = Counter(row["service_id"] for row in endpoints if row["visibility"] == "public")
    deprecated_count = Counter(row["service_id"] for row in endpoints if row["deprecated"])
    note_count = Counter(row["service_id"] for row in notes)

    missing = []
    service_rows = []
    for svc in sorted(services, key=lambda row: row["service_id"]):
        doc = pages.get(svc["doc_slug"])
        missing_doc = not (doc and doc["service"] == svc["service_id"] and doc["status"] == "active")
        if missing_doc:
            missing.append(svc)
        service_rows.append(
            {
                "service_id": svc["service_id"],
                "name": svc["name"],
                "owner_team": svc["owner_team"],
                "tier": svc["tier"],
                "doc_slug": svc["doc_slug"],
                "owner_slack": teams[svc["owner_team"]]["slack"],
                "endpoint_count": endpoint_count[svc["service_id"]],
                "public_endpoint_count": public_count[svc["service_id"]],
                "deprecated_endpoint_count": deprecated_count[svc["service_id"]],
                "missing_doc": missing_doc,
                "release_mentions": note_count[svc["service_id"]],
            }
        )

    redirect_seed = [
        {"source": row["source"], "target": row["target"], "reason": row["reason"]}
        for row in csv_rows(root / "docs" / "redirects.csv")
    ]
    for doc in pages.values():
        for alias in doc["aliases"]:
            redirect_seed.append({"source": alias, "target": f"/docs/{doc['slug']}", "reason": "page_alias"})

    redirects = []
    for row in redirect_seed:
        status = "broken_missing"
        sid = ""
        if row["target"].startswith("/docs/"):
            target = pages.get(row["target"].removeprefix("/docs/"))
            if target:
                sid = target["service"]
                status = "ok" if target["status"] == "active" else "broken_deprecated"
        redirects.append({"source": row["source"], "target": row["target"], "service_id": sid, "status": status, "reason": row["reason"]})
    redirects.sort(key=lambda row: row["source"])

    broken = []
    for doc in pages.values():
        for target in doc["links"]:
            if not target.startswith("/docs/"):
                continue
            target_doc = pages.get(target.removeprefix("/docs/"))
            if target_doc is None:
                broken.append({"source_slug": doc["slug"], "target": target, "reason": "missing_page"})
            elif target_doc["status"] != "active":
                broken.append({"source_slug": doc["slug"], "target": target, "reason": "deprecated_page"})
    broken.sort(key=lambda row: (row["source_slug"], row["target"]))

    by_team: dict[str, list[dict[str, str]]] = defaultdict(list)
    for svc in services:
        by_team[svc["owner_team"]].append(svc)
    owner_rows = []
    for team in sorted(teams):
        owned = sorted(by_team.get(team, []), key=lambda row: row["service_id"])
        owner_rows.append(
            {
                "team": team,
                "manager": teams[team]["manager"],
                "slack": teams[team]["slack"],
                "email": teams[team]["email"],
                "services": ";".join(row["service_id"] for row in owned),
                "public_endpoints": str(sum(public_count[row["service_id"]] for row in owned)),
                "deprecated_endpoints": str(sum(deprecated_count[row["service_id"]] for row in owned)),
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

    lines = ["# Developer Portal Actions", "", "## Missing Documentation"]
    lines.extend(
        [f"- {svc['service_id']} {svc['name']} -> /docs/{svc['doc_slug']}" for svc in sorted(missing, key=lambda row: row["service_id"])]
        or ["- none"]
    )
    lines.extend(["", "## Broken Links"])
    lines.extend([f"- {row['source_slug']} -> {row['target']} ({row['reason']})" for row in broken] or ["- none"])
    lines.extend(["", "## Deprecated Endpoints"])
    deprecated = [row for row in endpoints if row["deprecated"]]
    if deprecated:
        for row in deprecated:
            svc = service_by_id[row["service_id"]]
            lines.append(f"- {row['service_id']} {row['method'].upper()} {row['path']} sunset={row['sunset']} owner={teams[svc['owner_team']]['slack']}")
    else:
        lines.append("- none")
    (out / "docs_actions.md").write_text("\n".join(lines) + "\n")

    (out / "api_inventory.json").write_text(
        json.dumps(
            {
                "services": service_rows,
                "endpoints": endpoints,
                "redirects": redirects,
                "broken_links": broken,
                "release_notes": notes,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (out / "summary.json").write_text(
        json.dumps(
            {
                "services": len(service_rows),
                "endpoints": len(endpoints),
                "public_endpoints": sum(1 for row in endpoints if row["visibility"] == "public"),
                "deprecated_endpoints": sum(1 for row in endpoints if row["deprecated"]),
                "missing_docs": len(missing),
                "redirects": len(redirects),
                "broken_links": len(broken),
                "release_mentions": len(notes),
                "owner_teams": len(teams),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    write_csv(out / "owner_matrix.csv", ["team", "manager", "slack", "email", "services", "public_endpoints", "deprecated_endpoints", "missing_docs"], owner_rows)


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_portal_index.py
