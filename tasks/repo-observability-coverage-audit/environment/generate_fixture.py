from __future__ import annotations

from pathlib import Path
import csv
import json
import sys
import textwrap


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


def write_json(root: Path, relative: str, value: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv(root: Path, relative: str, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def service_source(root: Path, service_id: str, relative: str, body: str) -> None:
    write(root, f"services/{service_id}/src/{relative}", body)
    for index in range(1, 26):
        write(
            root,
            f"services/{service_id}/src/generated/noise_{index:02d}.py",
            f"""
            from __future__ import annotations

            SERVICE_ID = {service_id!r}
            NOISE_INDEX = {index}

            def marker(seed: int) -> str:
                return f"{{SERVICE_ID}}:{{NOISE_INDEX}}:{{seed % 19}}"
            """,
        )


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)

    write(
        root,
        "README.md",
        """
        # Synthetic Platform Repo

        Repository used for an observability coverage audit. The route catalog, source telemetry,
        dashboards, alerts, incident records, owner metadata, and temporary exemptions intentionally
        drift from each other.
        """,
    )
    write_json(
        root,
        "catalog/services.json",
        [
            {"service_id": "admin", "display_name": "Admin Console", "team": "platform", "tier": 1, "language": "python"},
            {"service_id": "analytics", "display_name": "Analytics", "team": "data", "tier": 2, "language": "python"},
            {"service_id": "billing", "display_name": "Billing", "team": "finance", "tier": 1, "language": "python"},
            {"service_id": "checkout", "display_name": "Checkout", "team": "commerce", "tier": 1, "language": "typescript"},
            {"service_id": "identity", "display_name": "Identity", "team": "platform", "tier": 1, "language": "go"},
            {"service_id": "support", "display_name": "Support", "team": "care", "tier": 3, "language": "python"},
        ],
    )
    write_csv(
        root,
        "catalog/routes.csv",
        [
            {"route_id": "admin.grant_role", "service_id": "admin", "method": "POST", "path": "/admin/roles/grant", "handler": "grant_role", "tier_override": "", "pii_expected": "false"},
            {"route_id": "analytics.export", "service_id": "analytics", "method": "POST", "path": "/analytics/export", "handler": "export_report", "tier_override": "2", "pii_expected": "false"},
            {"route_id": "billing.apply_credit", "service_id": "billing", "method": "POST", "path": "/billing/credits", "handler": "apply_credit", "tier_override": "2", "pii_expected": "false"},
            {"route_id": "billing.invoice_pdf", "service_id": "billing", "method": "GET", "path": "/billing/invoices/:id.pdf", "handler": "invoice_pdf", "tier_override": "2", "pii_expected": "false"},
            {"route_id": "checkout.create_order", "service_id": "checkout", "method": "POST", "path": "/checkout/orders", "handler": "createOrder", "tier_override": "", "pii_expected": "false"},
            {"route_id": "checkout.refund", "service_id": "checkout", "method": "POST", "path": "/checkout/refunds", "handler": "refundOrder", "tier_override": "", "pii_expected": "false"},
            {"route_id": "identity.login", "service_id": "identity", "method": "POST", "path": "/identity/login", "handler": "Login", "tier_override": "", "pii_expected": "false"},
            {"route_id": "support.bulk_reply", "service_id": "support", "method": "POST", "path": "/support/replies/bulk", "handler": "bulk_reply", "tier_override": "", "pii_expected": "true"},
            {"route_id": "support.portal_save_card", "service_id": "support", "method": "POST", "path": "/support/portal/cards", "handler": "save_card", "tier_override": "1", "pii_expected": "true"},
        ],
        ["route_id", "service_id", "method", "path", "handler", "tier_override", "pii_expected"],
    )
    write_csv(
        root,
        "owners/teams.csv",
        [
            {"team": "care", "manager": "Mira Cole", "slack": "#care", "pagerduty": "pd-care"},
            {"team": "commerce", "manager": "Nia Ford", "slack": "#commerce", "pagerduty": "pd-commerce"},
            {"team": "data", "manager": "Omar Bell", "slack": "#data", "pagerduty": "pd-data"},
            {"team": "finance", "manager": "Pri Shah", "slack": "#finance", "pagerduty": "pd-finance"},
            {"team": "platform", "manager": "Ren Ito", "slack": "#platform", "pagerduty": "pd-platform"},
        ],
        ["team", "manager", "slack", "pagerduty"],
    )
    write_json(
        root,
        "policies/coverage_rules.json",
        {
            "report_date": "2026-07-07",
            "required_events": ["request_started", "request_succeeded", "request_failed"],
            "dashboard_required_tier": 2,
            "paging_alert_required_tier": 2,
            "runbook_required_tier": 2,
            "runbook_review_days": 90,
            "trace_edge_required_tier": 2,
            "deploy_recency_days": 14,
            "pii_tokens": ["email", "ssn", "card_number"],
            "due_days": {
                "blocked": 1,
                "needs_work": 7,
                "accepted_risk": 14,
                "ready": 30,
            },
        },
    )
    write_csv(
        root,
        "dependencies/route_edges.csv",
        [
            {"source_route_id": "checkout.create_order", "target_service_id": "billing", "critical": "true"},
            {"source_route_id": "checkout.refund", "target_service_id": "billing", "critical": "true"},
            {"source_route_id": "support.portal_save_card", "target_service_id": "billing", "critical": "true"},
            {"source_route_id": "admin.grant_role", "target_service_id": "identity", "critical": "false"},
            {"source_route_id": "analytics.export", "target_service_id": "billing", "critical": "true"},
        ],
        ["source_route_id", "target_service_id", "critical"],
    )
    write_json(
        root,
        "runbooks/route_runbooks.json",
        [
            {"route_id": "admin.grant_role", "url": "runbooks/admin-grant-role.md", "reviewed_on": "2026-06-15"},
            {"route_id": "analytics.export", "url": "runbooks/analytics-export.md", "reviewed_on": "2026-05-01"},
            {"route_id": "billing.apply_credit", "url": "runbooks/billing-credits.md", "reviewed_on": "2026-02-01"},
            {"route_id": "checkout.create_order", "url": "runbooks/checkout-orders.md", "reviewed_on": "2026-06-20"},
            {"route_id": "identity.login", "url": "runbooks/identity-login.md", "reviewed_on": "2026-06-01"},
            {"route_id": "support.portal_save_card", "url": "runbooks/support-cards.md", "reviewed_on": "2026-07-01"},
        ],
    )
    write_csv(
        root,
        "deployments/recent_deploys.csv",
        [
            {"service_id": "checkout", "deployed_at": "2026-07-04", "commit": "cafe001", "changed_routes": "checkout.create_order;checkout.refund", "rollback_ready": "true"},
            {"service_id": "support", "deployed_at": "2026-07-06", "commit": "cafe002", "changed_routes": "support.portal_save_card", "rollback_ready": "false"},
            {"service_id": "billing", "deployed_at": "2026-06-10", "commit": "cafe003", "changed_routes": "*", "rollback_ready": "true"},
            {"service_id": "identity", "deployed_at": "2026-07-02", "commit": "cafe004", "changed_routes": "identity.login", "rollback_ready": "true"},
        ],
        ["service_id", "deployed_at", "commit", "changed_routes", "rollback_ready"],
    )
    write_csv(
        root,
        "incidents/incidents.csv",
        [
            {"route_id": "support.portal_save_card", "date": "2026-07-06", "severity": "P1", "status": "open"},
            {"route_id": "checkout.refund", "date": "2026-07-02", "severity": "P2", "status": "open"},
            {"route_id": "identity.login", "date": "2026-07-01", "severity": "P0", "status": "resolved"},
        ],
        ["route_id", "date", "severity", "status"],
    )
    write_csv(
        root,
        "exemptions/observability_exemptions.csv",
        [
            {"route_id": "analytics.export", "control": "dashboard_panel", "expires_on": "2026-07-31", "reason": "warehouse migration"},
            {"route_id": "analytics.export", "control": "paging_alert", "expires_on": "2026-07-31", "reason": "warehouse migration"},
            {"route_id": "billing.apply_credit", "control": "request_failed", "expires_on": "2026-07-21", "reason": "shared billing middleware rollout"},
            {"route_id": "billing.invoice_pdf", "control": "dashboard_panel", "expires_on": "2026-06-30", "reason": "old pdf dashboard"},
        ],
        ["route_id", "control", "expires_on", "reason"],
    )
    write_json(
        root,
        "dashboards/customer-journey.json",
        {
            "panels": [
                {"title": "Create order latency", "route_id": "checkout.create_order"},
                {"title": "Refund health", "route_id": "checkout.refund"},
                {"title": "Admin grants", "route_id": "admin.grant_role"},
                {"title": "Portal card saves", "route_id": "support.portal_save_card"},
            ]
        },
    )
    write_json(
        root,
        "dashboards/finance.json",
        {"panels": [{"title": "Credit applications", "route_id": "billing.apply_credit"}]},
    )
    write(
        root,
        "alerts/routes.yaml",
        """
        alerts:
          - route_id: checkout.create_order
            severity: page
          - route_id: checkout.refund
            severity: page
          - route_id: billing.invoice_pdf
            severity: ticket
          - route_id: identity.login
            severity: page
          - route_id: support.portal_save_card
            severity: page
        """,
    )

    service_source(
        root,
        "checkout",
        "routes/orders.ts",
        """
        // route_id: checkout.create_order
        export function createOrder(req) {
          telemetry.track("request_started", {route_id: "checkout.create_order", trace_id: req.trace_id});
          telemetry.track("request_succeeded", {route_id: "checkout.create_order", trace_id: req.trace_id});
          telemetry.track("request_failed", {route_id: "checkout.create_order", trace_id: req.trace_id});
          telemetry.track("downstream_call", {route_id: "checkout.create_order", target_service_id: "billing", downstream_trace_id: req.trace_id});
        }

        // route_id: checkout.refund
        export function refundOrder(req) {
          telemetry.track("request_started", {route_id: "checkout.refund", trace_id: req.trace_id});
          telemetry.track("request_succeeded", {route_id: "checkout.refund", trace_id: req.trace_id});
        }
        """,
    )
    service_source(
        root,
        "billing",
        "routes/invoices.py",
        """
        # route_id: billing.invoice_pdf
        def invoice_pdf(req):
            telemetry.track("request_started", {"route_id": "billing.invoice_pdf", "trace_id": req.trace_id})
            telemetry.track("request_succeeded", {"route_id": "billing.invoice_pdf", "trace_id": req.trace_id})
            telemetry.track("request_failed", {"route_id": "billing.invoice_pdf", "trace_id": req.trace_id})

        # route_id: billing.apply_credit
        def apply_credit(req):
            telemetry.track("request_started", {"route_id": "billing.apply_credit", "trace_id": req.trace_id})
            telemetry.track("request_succeeded", {"route_id": "billing.apply_credit", "trace_id": req.trace_id})
        """,
    )
    service_source(
        root,
        "identity",
        "routes/login.go",
        """
        // route_id: identity.login
        func Login(req Request) {
          telemetry.Track("request_started", map[string]string{"route_id": "identity.login", "trace_id": req.TraceID, "email": req.Email})
          telemetry.Track("request_succeeded", map[string]string{"route_id": "identity.login", "trace_id": req.TraceID})
          telemetry.Track("request_failed", map[string]string{"route_id": "identity.login", "trace_id": req.TraceID})
        }
        """,
    )
    service_source(
        root,
        "admin",
        "routes/roles.py",
        """
        # route_id: admin.grant_role
        def grant_role(req):
            telemetry.track("request_started", {"route_id": "admin.grant_role", "trace_id": req.trace_id})
            telemetry.track("request_succeeded", {"route_id": "admin.grant_role", "trace_id": req.trace_id})
            telemetry.track("request_failed", {"route_id": "admin.grant_role", "trace_id": req.trace_id})
        """,
    )
    service_source(
        root,
        "analytics",
        "routes/export.py",
        """
        # route_id: analytics.export
        def export_report(req):
            telemetry.track("request_started", {"route_id": "analytics.export", "trace_id": req.trace_id})
            telemetry.track("request_succeeded", {"route_id": "analytics.export", "trace_id": req.trace_id})
            telemetry.track("request_failed", {"route_id": "analytics.export", "trace_id": req.trace_id})
            telemetry.track("downstream_call", {"route_id": "analytics.export", "target_service_id": "billing"})
        """,
    )
    service_source(
        root,
        "support",
        "routes/replies.py",
        """
        # route_id: support.bulk_reply
        def bulk_reply(req):
            telemetry.track("request_started", {"route_id": "support.bulk_reply", "trace_id": req.trace_id, "email": req.email})
            telemetry.track("request_succeeded", {"route_id": "support.bulk_reply", "trace_id": req.trace_id})
            telemetry.track("request_failed", {"route_id": "support.bulk_reply", "trace_id": req.trace_id})

        # route_id: support.portal_save_card
        def save_card(req):
            telemetry.track("request_started", {"route_id": "support.portal_save_card", "trace_id": req.trace_id, "card_number": req.card_number})
            telemetry.track("request_succeeded", {"route_id": "support.portal_save_card", "trace_id": req.trace_id})
            telemetry.track("request_failed", {"route_id": "support.portal_save_card", "trace_id": req.trace_id})
            telemetry.track("downstream_call", {"route_id": "support.portal_save_card", "target_service_id": "billing", "downstream_trace_id": req.trace_id})
        """,
    )


if __name__ == "__main__":
    main()
