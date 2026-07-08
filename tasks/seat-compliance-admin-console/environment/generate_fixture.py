from __future__ import annotations

from pathlib import Path
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


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)

    write(
        root,
        "README.md",
        """
        # Workspace App

        A static internal operations app. Screens render server-side HTML through
        `python -m workspace_app.cli --route <route> --data-dir <dir> --output <file>`.
        """,
    )
    write(
        root,
        "pyproject.toml",
        """
        [project]
        name = "workspace-app"
        version = "0.1.0"
        requires-python = ">=3.12"
        """,
    )
    write(root, "workspace_app/__init__.py", "__version__ = '0.1.0'\n")
    write(
        root,
        "workspace_app/data.py",
        """
        from __future__ import annotations

        from pathlib import Path
        import json


        def load_json(data_dir: str | Path, name: str) -> object:
            path = Path(data_dir) / name
            return json.loads(path.read_text())


        def as_int(value: object, default: int = 0) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        """,
    )
    write(
        root,
        "workspace_app/layout.py",
        """
        from __future__ import annotations

        from html import escape

        from .nav import NAV_ITEMS


        def render_nav(active_route: str) -> str:
            links = []
            for item in NAV_ITEMS:
                active = "true" if item["href"] == active_route else "false"
                links.append(
                    '<a data-nav-item="true" aria-current="%s" href="%s">%s</a>'
                    % (active, escape(item["href"]), escape(item["label"]))
                )
            return '<nav data-testid="primary-nav">%s</nav>' % "".join(links)


        def render_layout(title: str, active_route: str, body: str, *, data_screen: str) -> str:
            return (
                '<!doctype html>'
                '<html lang="en">'
                '<head><meta charset="utf-8"><title>%s</title></head>'
                '<body>'
                '<header><div class="brand">Workspace App</div>%s</header>'
                '<main data-screen="%s">%s</main>'
                '</body></html>'
            ) % (escape(title), render_nav(active_route), escape(data_screen), body)
        """,
    )
    write(
        root,
        "workspace_app/nav.py",
        """
        NAV_ITEMS = [
            {"label": "Home", "href": "/"},
            {"label": "Accounts", "href": "/accounts"},
            {"label": "Support", "href": "/support"},
            {"label": "Billing", "href": "/billing"},
            {"label": "Reports", "href": "/reports"},
        ]
        """,
    )
    write(
        root,
        "workspace_app/routing.py",
        """
        from __future__ import annotations

        from pathlib import Path
        from typing import Callable

        from .screens import accounts, billing, home, reports, support

        RenderFn = Callable[[Path], str]

        ROUTES: dict[str, RenderFn] = {
            "/": home.render,
            "/accounts": accounts.render,
            "/support": support.render,
            "/billing": billing.render,
            "/reports": reports.render,
        }


        def route_names() -> list[str]:
            return sorted(ROUTES)


        def render_route(route: str, data_dir: str | Path) -> str:
            if route not in ROUTES:
                known = ", ".join(route_names())
                raise SystemExit(f"Unknown route {route!r}. Known routes: {known}")
            return ROUTES[route](Path(data_dir))
        """,
    )
    write(
        root,
        "workspace_app/cli.py",
        """
        from __future__ import annotations

        from pathlib import Path
        import argparse

        from .routing import render_route, route_names


        def main(argv: list[str] | None = None) -> int:
            parser = argparse.ArgumentParser()
            parser.add_argument("--route", default="/")
            parser.add_argument("--data-dir", default="fixtures/visible")
            parser.add_argument("--output")
            parser.add_argument("--list-routes", action="store_true")
            args = parser.parse_args(argv)

            if args.list_routes:
                print("\\n".join(route_names()))
                return 0

            html = render_route(args.route, args.data_dir)
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(html)
            else:
                print(html)
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """,
    )
    write(root, "workspace_app/screens/__init__.py", "")
    write(root, "workspace_app/selectors/__init__.py", "")
    write(root, "workspace_app/components/__init__.py", "")

    write(
        root,
        "workspace_app/components/html.py",
        """
        from __future__ import annotations

        from html import escape


        def stat_card(key: str, label: str, value: object) -> str:
            return (
                '<section class="stat-card" data-metric="%s">'
                '<span class="stat-label">%s</span>'
                '<strong>%s</strong>'
                '</section>'
            ) % (escape(key), escape(label), escape(str(value)))
        """,
    )

    screen_specs = {
        "home": ("/", "Home", "home", "<h1>Operations Home</h1><p>Daily operating summary.</p>"),
        "accounts": ("/accounts", "Accounts", "accounts", "<h1>Accounts</h1><p>Account portfolio and ownership.</p>"),
        "support": ("/support", "Support", "support", "<h1>Support</h1><p>Support workload and queues.</p>"),
        "billing": ("/billing", "Billing", "billing", "<h1>Billing</h1><p>Invoices and renewals.</p>"),
        "reports": ("/reports", "Reports", "reports", "<h1>Reports</h1><p>Recurring operations reports.</p>"),
    }
    for name, (route, title, data_screen, body) in screen_specs.items():
        write(
            root,
            f"workspace_app/screens/{name}.py",
            f"""
            from __future__ import annotations

            from pathlib import Path

            from workspace_app.layout import render_layout


            def render(data_dir: Path) -> str:
                return render_layout({title!r}, {route!r}, {body!r}, data_screen={data_screen!r})
            """,
        )

    for index in range(1, 91):
        write(
            root,
            f"workspace_app/components/generated_panel_{index:02d}.py",
            f"""
            from __future__ import annotations

            PANEL_KEY = "generated-panel-{index:02d}"


            def marker(value: object) -> str:
                return f"{{PANEL_KEY}}:{{value}}"
            """,
        )
    for index in range(1, 61):
        write(
            root,
            f"workspace_app/selectors/generated_metric_{index:02d}.py",
            f"""
            from __future__ import annotations

            METRIC_KEY = "generated-metric-{index:02d}"


            def count_truthy(rows: list[dict[str, object]], key: str) -> int:
                return sum(1 for row in rows if row.get(key))
            """,
        )

    fixture = root / "fixtures" / "visible"
    write_json(
        fixture,
        "accounts.json",
        [
            {"account_id": "acct-1", "name": "Atlas Labs", "owner": "Mina Patel", "plan": "enterprise", "segment": "strategic", "arr": 220000},
            {"account_id": "acct-2", "name": "Bright Foods", "owner": "Owen Kim", "plan": "growth", "segment": "commercial", "arr": 64000},
            {"account_id": "acct-3", "name": "Cinder Bank", "owner": "Mina Patel", "plan": "enterprise", "segment": "regulated", "arr": 310000},
            {"account_id": "acct-4", "name": "Delta Clinic", "owner": "Rae Singh", "plan": "starter", "segment": "smb", "arr": 18000},
        ],
    )
    write_json(
        fixture,
        "subscriptions.json",
        {
            "report_date": "2026-07-07",
            "subscriptions": [
                {"account_id": "acct-1", "status": "active", "renewal_date": "2026-07-25"},
                {"account_id": "acct-2", "status": "trialing", "renewal_date": "2026-08-30"},
                {"account_id": "acct-3", "status": "past_due", "renewal_date": "2026-07-14"},
                {"account_id": "acct-4", "status": "active", "renewal_date": "2026-07-20"},
            ],
        },
    )
    write_json(
        fixture,
        "plan_limits.json",
        {
            "enterprise": {"seat_limit": 80, "contractor_limit": 12, "included_sso": True},
            "growth": {"seat_limit": 35, "contractor_limit": 4, "included_sso": True},
            "starter": {"seat_limit": 10, "contractor_limit": 1, "included_sso": False},
        },
    )
    write_json(
        fixture,
        "allocations.json",
        [
            {"account_id": "acct-1", "seat_limit_override": 75, "effective_on": "2026-06-01", "source": "contract"},
            {"account_id": "acct-1", "seat_limit_override": 90, "effective_on": "2026-08-01", "source": "future-contract"},
            {"account_id": "acct-2", "seat_limit_override": 32, "effective_on": "2026-07-01", "source": "amendment"},
        ],
    )
    write_json(
        fixture,
        "users.json",
        [
            {"user_id": "u-1", "account_id": "acct-1", "status": "active", "user_type": "employee", "sso_enabled": True},
            {"user_id": "u-2", "account_id": "acct-1", "status": "active", "user_type": "employee", "sso_enabled": False},
            {"user_id": "u-3", "account_id": "acct-1", "status": "active", "user_type": "contractor", "sso_enabled": False},
            {"user_id": "u-4", "account_id": "acct-2", "status": "active", "user_type": "employee", "sso_enabled": True},
            {"user_id": "u-5", "account_id": "acct-2", "status": "active", "user_type": "contractor", "sso_enabled": True},
            {"user_id": "u-6", "account_id": "acct-3", "status": "active", "user_type": "employee", "sso_enabled": True},
            {"user_id": "u-7", "account_id": "acct-3", "status": "suspended", "user_type": "employee", "sso_enabled": False},
            {"user_id": "u-8", "account_id": "acct-4", "status": "active", "user_type": "contractor", "sso_enabled": False},
        ],
    )
    write_json(
        fixture,
        "invitations.json",
        [
            {"invite_id": "i-1", "account_id": "acct-1", "status": "pending", "expires_on": "2026-07-12", "user_type": "employee"},
            {"invite_id": "i-2", "account_id": "acct-2", "status": "pending", "expires_on": "2026-07-01", "user_type": "employee"},
            {"invite_id": "i-3", "account_id": "acct-2", "status": "pending", "expires_on": "2026-07-20", "user_type": "contractor"},
            {"invite_id": "i-4", "account_id": "acct-4", "status": "accepted", "expires_on": "2026-07-30", "user_type": "employee"},
        ],
    )
    write_json(
        fixture,
        "exceptions.json",
        [
            {"account_id": "acct-1", "control": "sso_gap", "expires_on": "2026-07-30", "reason": "idp migration", "approver": "vp-security"},
            {"account_id": "acct-2", "control": "contractor_overage", "expires_on": "2026-07-31", "reason": "agency rollout", "approver": "vp-success"},
            {"account_id": "acct-4", "control": "seat_overage", "expires_on": "2026-07-01", "reason": "expired launch pad", "approver": "ops"},
        ],
    )
    write_json(
        fixture,
        "tickets.json",
        [
            {"account_id": "acct-1", "status": "open", "priority": "p2"},
            {"account_id": "acct-2", "status": "open", "priority": "p1"},
            {"account_id": "acct-2", "status": "closed", "priority": "p1"},
            {"account_id": "acct-3", "status": "open", "priority": "p0"},
        ],
    )

    write(
        root,
        "tests/test_existing_routes.py",
        """
        from __future__ import annotations

        from pathlib import Path
        import subprocess
        import sys
        import tempfile
        import unittest


        class ExistingRouteTests(unittest.TestCase):
            def render(self, route: str) -> str:
                with tempfile.TemporaryDirectory() as tmp:
                    output = Path(tmp) / "out.html"
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "workspace_app.cli",
                            "--route",
                            route,
                            "--data-dir",
                            "/app/fixtures/visible",
                            "--output",
                            str(output),
                        ],
                        check=True,
                    )
                    return output.read_text()

            def test_existing_routes_render(self) -> None:
                for route, screen in [
                    ("/", "home"),
                    ("/accounts", "accounts"),
                    ("/support", "support"),
                    ("/billing", "billing"),
                    ("/reports", "reports"),
                ]:
                    with self.subTest(route=route):
                        self.assertIn(f'data-screen="{screen}"', self.render(route))


        if __name__ == "__main__":
            unittest.main()
        """,
    )


if __name__ == "__main__":
    main()
