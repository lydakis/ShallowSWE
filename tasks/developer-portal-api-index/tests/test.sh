#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

app = Path(os.environ.get("APP_DIR", "/app"))
OUTPUT_FILES = {"api_inventory.json", "owner_matrix.csv", "docs_actions.md", "summary.json"}
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
RELEASE_RE = re.compile(r"^- ([A-Za-z0-9_-]+) ([A-Z]+) ([^:]+): (.+)$")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_page(path: Path) -> dict[str, object]:
    text = path.read_text()
    lines = text.splitlines()
    assert lines and lines[0] == "---", f"bad frontmatter start in {path}"
    end = lines.index("---", 1)
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1 :])
    redirects = [item.strip() for item in meta.get("redirect_from", "").split(";") if item.strip()]
    return {
        "slug": meta["slug"],
        "title": meta["title"],
        "service": meta["service"],
        "status": meta["status"],
        "redirect_from": redirects,
        "links": LINK_RE.findall(body),
    }


def load_model(root: Path) -> dict[str, object]:
    services = json.loads((root / "catalog" / "services.json").read_text())
    owners = {row["team"]: row for row in read_csv(root / "owners" / "teams.csv")}
    pages = {page["slug"]: page for page in (parse_page(path) for path in sorted((root / "docs" / "pages").glob("*.md")))}

    endpoints = []
    for path in sorted((root / "apis").glob("*.json")):
        fragment = json.loads(path.read_text())
        service_id = fragment["info"]["service_id"]
        service = next(item for item in services if item["service_id"] == service_id)
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

    release_notes = []
    current = ""
    for path in sorted((root / "releases").glob("*.md")):
        for line in path.read_text().splitlines():
            if line.startswith("## "):
                current = line.removeprefix("## ").strip().lower()
                continue
            match = RELEASE_RE.match(line)
            if not match or current not in {"added", "changed", "deprecated"}:
                continue
            service_id, method, route, note = match.groups()
            known = any(
                row["service_id"] == service_id
                and row["method"] == method.lower()
                and row["path"] == route
                for row in endpoints
            )
            release_notes.append(
                {
                    "service_id": service_id,
                    "method": method.lower(),
                    "path": route,
                    "change_type": current,
                    "note": note,
                    "known_endpoint": known,
                }
            )

    return {"services": services, "owners": owners, "pages": pages, "endpoints": endpoints, "release_notes": release_notes}


def expected(root: Path) -> dict[str, object]:
    model = load_model(root)
    services = model["services"]
    owners = model["owners"]
    pages = model["pages"]
    endpoints = sorted(model["endpoints"], key=lambda row: (row["service_id"], row["path"], row["method"]))
    release_notes = sorted(
        model["release_notes"],
        key=lambda row: (row["service_id"], row["method"], row["path"], row["change_type"]),
    )
    endpoint_counts = Counter(row["service_id"] for row in endpoints)
    public_counts = Counter(row["service_id"] for row in endpoints if row["visibility"] == "public")
    deprecated_counts = Counter(row["service_id"] for row in endpoints if row["deprecated"])
    release_counts = Counter(row["service_id"] for row in release_notes)

    service_rows = []
    missing_docs = []
    for service in sorted(services, key=lambda row: row["service_id"]):
        page = pages.get(service["doc_slug"])
        missing = not (page and page["service"] == service["service_id"] and page["status"] == "active")
        if missing:
            missing_docs.append(service)
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

    redirects = []
    for row in read_csv(root / "docs" / "redirects.csv"):
        redirects.append({"source": row["source"], "target": row["target"], "reason": row["reason"]})
    for page in pages.values():
        for source in page["redirect_from"]:
            redirects.append({"source": source, "target": f"/docs/{page['slug']}", "reason": "page_alias"})

    redirect_rows = []
    for row in redirects:
        service_id = ""
        status = "broken_missing"
        if row["target"].startswith("/docs/"):
            slug = row["target"].removeprefix("/docs/")
            page = pages.get(slug)
            if page:
                service_id = page["service"]
                status = "ok" if page["status"] == "active" else "broken_deprecated"
        redirect_rows.append(
            {
                "source": row["source"],
                "target": row["target"],
                "service_id": service_id,
                "status": status,
                "reason": row["reason"],
            }
        )
    redirect_rows.sort(key=lambda row: row["source"])

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

    owner_rows = []
    services_by_team: dict[str, list[dict[str, str]]] = defaultdict(list)
    for service in services:
        services_by_team[service["owner_team"]].append(service)
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

    deprecated_endpoint_items = []
    service_by_id = {row["service_id"]: row for row in services}
    for endpoint in endpoints:
        if endpoint["deprecated"]:
            service = service_by_id[endpoint["service_id"]]
            deprecated_endpoint_items.append(
                {
                    "service_id": endpoint["service_id"],
                    "method": endpoint["method"].upper(),
                    "path": endpoint["path"],
                    "sunset": endpoint["sunset"],
                    "owner_slack": owners[service["owner_team"]]["slack"],
                }
            )

    action_lines = ["# Developer Portal Actions", "", "## Missing Documentation"]
    if missing_docs:
        for service in sorted(missing_docs, key=lambda row: row["service_id"]):
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
    if deprecated_endpoint_items:
        for row in deprecated_endpoint_items:
            action_lines.append(
                f"- {row['service_id']} {row['method']} {row['path']} sunset={row['sunset']} owner={row['owner_slack']}"
            )
    else:
        action_lines.append("- none")
    docs_actions = "\n".join(action_lines) + "\n"

    inventory = {
        "services": service_rows,
        "endpoints": endpoints,
        "redirects": redirect_rows,
        "broken_links": broken_links,
        "release_notes": release_notes,
    }
    summary = {
        "services": len(service_rows),
        "endpoints": len(endpoints),
        "public_endpoints": sum(1 for row in endpoints if row["visibility"] == "public"),
        "deprecated_endpoints": sum(1 for row in endpoints if row["deprecated"]),
        "missing_docs": len(missing_docs),
        "redirects": len(redirect_rows),
        "broken_links": len(broken_links),
        "release_mentions": len(release_notes),
        "owner_teams": len(owners),
    }
    return {
        "api_inventory.json": inventory,
        "owner_matrix.csv": owner_rows,
        "docs_actions.md": docs_actions,
        "summary.json": summary,
    }


def write_hidden(root: Path) -> None:
    (root / "catalog").mkdir(parents=True)
    (root / "owners").mkdir(parents=True)
    (root / "apis").mkdir(parents=True)
    (root / "docs" / "pages").mkdir(parents=True)
    (root / "releases").mkdir(parents=True)
    (root / "catalog" / "services.json").write_text(
        json.dumps(
            [
                {"service_id": "files", "name": "Files API", "owner_team": "platform-files", "tier": "gold", "doc_slug": "files-api"},
                {"service_id": "notify", "name": "Notifications API", "owner_team": "platform-comms", "tier": "silver", "doc_slug": "notify-api"},
                {"service_id": "reports", "name": "Reports API", "owner_team": "platform-files", "tier": "bronze", "doc_slug": "reports-api"},
            ],
            indent=2,
        )
    )
    (root / "owners" / "teams.csv").write_text(
        "team,manager,slack,email\n"
        "platform-comms,Jo Stone,@comms-platform,comms@example.test\n"
        "platform-files,Rui Allen,@files-platform,files@example.test\n"
    )
    (root / "apis" / "files.json").write_text(
        json.dumps(
            {
                "info": {"service_id": "files", "version": "2026-07-02"},
                "paths": {
                    "/v2/files": {
                        "get": {"operationId": "listFiles", "visibility": "public", "flags": ["paginated"]},
                        "post": {"operationId": "createFile", "visibility": "partner"},
                    },
                    "/v1/files": {
                        "get": {"operationId": "listLegacyFiles", "visibility": "public", "deprecated": True, "sunset": "2026-10-01"}
                    },
                },
            },
            indent=2,
        )
    )
    (root / "apis" / "notify.json").write_text(
        json.dumps(
            {
                "info": {"service_id": "notify", "version": "2026-07-02"},
                "paths": {
                    "/v1/messages": {
                        "post": {"operationId": "sendMessage", "visibility": "public"},
                    },
                    "/v1/templates": {
                        "get": {"operationId": "listTemplates", "visibility": "internal"},
                    },
                },
            },
            indent=2,
        )
    )
    (root / "docs" / "pages" / "files-api.md").write_text(
        "---\nslug: files-api\ntitle: Files API\nservice: files\nstatus: active\nredirect_from: /docs/uploads\n---\n\n# Files\n\nSee [legacy files](/docs/files-v1) and [notifications](/docs/notify-api).\n"
    )
    (root / "docs" / "pages" / "files-v1.md").write_text(
        "---\nslug: files-v1\ntitle: Files v1\nservice: files\nstatus: deprecated\nredirect_from:\n---\n\n# Files v1\n"
    )
    (root / "docs" / "pages" / "notify-api.md").write_text(
        "---\nslug: notify-api\ntitle: Notifications API\nservice: notify\nstatus: active\nredirect_from: /docs/messages;/docs/notifications\n---\n\n# Notifications\n\nSee [missing report docs](/docs/reports-api).\n"
    )
    (root / "docs" / "redirects.csv").write_text(
        "source,target,reason\n"
        "/docs/file-api,/docs/files-api,typo\n"
        "/docs/old-files,/docs/files-v1,deprecated\n"
        "/docs/reporting,/docs/reports-api,renamed\n"
    )
    (root / "releases" / "2026-07-02.md").write_text(
        "# 2026-07-02 Notes\n\n"
        "## Added\n\n"
        "- files GET /v2/files: files listing launched\n"
        "- notify POST /v1/messages: public message sending launched\n"
        "- reports GET /v1/reports: report listing planned\n\n"
        "## Deprecated\n\n"
        "- files GET /v1/files: legacy files endpoint retires\n"
    )


def assert_outputs(root: Path) -> None:
    output = root / "output"
    actual_files = {path.name for path in output.iterdir() if path.is_file()}
    assert actual_files == OUTPUT_FILES, f"unexpected output files: {actual_files}"
    exp = expected(root)
    assert json.loads((output / "api_inventory.json").read_text()) == exp["api_inventory.json"]
    assert json.loads((output / "summary.json").read_text()) == exp["summary.json"]
    assert (output / "docs_actions.md").read_text() == exp["docs_actions.md"]
    assert read_csv(output / "owner_matrix.csv") == exp["owner_matrix.csv"]


def run_script(root: Path) -> None:
    subprocess.run([sys.executable, str(root / "scripts" / "build_portal_index.py")], cwd=root, check=True)


script = app / "scripts" / "build_portal_index.py"
assert script.exists(), "missing scripts/build_portal_index.py"
run_script(app)
assert_outputs(app)

with tempfile.TemporaryDirectory() as tmp:
    hidden = Path(tmp) / "app"
    shutil.copytree(app / "scripts", hidden / "scripts")
    write_hidden(hidden)
    run_script(hidden)
    assert_outputs(hidden)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"
