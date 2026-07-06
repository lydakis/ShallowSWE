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


        def simple_table(table_key: str, headers: list[str], rows: list[list[object]]) -> str:
            header_html = "".join("<th>%s</th>" % escape(header) for header in headers)
            row_html = []
            for row in rows:
                cells = "".join("<td>%s</td>" % escape(str(cell)) for cell in row)
                row_html.append("<tr>%s</tr>" % cells)
            return (
                '<table data-table="%s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
                % (escape(table_key), header_html, "".join(row_html))
            )
        """,
    )

    screen_specs = {
        "home": {
            "route": "/",
            "title": "Home",
            "data_screen": "home",
            "body": "<h1>Operations Home</h1><p>Daily operating summary.</p>",
        },
        "accounts": {
            "route": "/accounts",
            "title": "Accounts",
            "data_screen": "accounts",
            "body": "<h1>Accounts</h1><p>Account portfolio and ownership.</p>",
        },
        "support": {
            "route": "/support",
            "title": "Support",
            "data_screen": "support",
            "body": "<h1>Support</h1><p>Support workload and queues.</p>",
        },
        "billing": {
            "route": "/billing",
            "title": "Billing",
            "data_screen": "billing",
            "body": "<h1>Billing</h1><p>Invoices and renewals.</p>",
        },
        "reports": {
            "route": "/reports",
            "title": "Reports",
            "data_screen": "reports",
            "body": "<h1>Reports</h1><p>Recurring operations reports.</p>",
        },
    }
    for name, spec in screen_specs.items():
        write(
            root,
            f"workspace_app/screens/{name}.py",
            f"""
            from __future__ import annotations

            from pathlib import Path

            from workspace_app.layout import render_layout


            def render(data_dir: Path) -> str:
                body = {spec["body"]!r}
                return render_layout(
                    {spec["title"]!r},
                    {spec["route"]!r},
                    body,
                    data_screen={spec["data_screen"]!r},
                )
            """,
        )

    for index in range(1, 76):
        write(
            root,
            f"workspace_app/components/generated_panel_{index:02d}.py",
            f"""
            from __future__ import annotations

            from html import escape


            PANEL_KEY = "generated-panel-{index:02d}"


            def render_panel(title: str, value: object, caption: str = "") -> str:
                body = [
                    '<section class="ops-panel" data-panel="%s">' % PANEL_KEY,
                    "<h2>%s</h2>" % escape(title),
                    "<strong>%s</strong>" % escape(str(value)),
                ]
                if caption:
                    body.append("<p>%s</p>" % escape(caption))
                body.append("</section>")
                return "".join(body)


            def panel_summary(rows: list[dict[str, object]]) -> dict[str, object]:
                total = len(rows)
                populated = sum(1 for row in rows if row)
                return {{"panel": PANEL_KEY, "total": total, "populated": populated}}
            """,
        )

    for index in range(1, 56):
        write(
            root,
            f"workspace_app/selectors/generated_metric_{index:02d}.py",
            f"""
            from __future__ import annotations


            METRIC_KEY = "generated-metric-{index:02d}"


            def count_records(rows: list[dict[str, object]], field: str | None = None) -> int:
                if field is None:
                    return len(rows)
                return sum(1 for row in rows if row.get(field))


            def bucket_records(rows: list[dict[str, object]], field: str) -> dict[str, int]:
                buckets: dict[str, int] = {{}}
                for row in rows:
                    key = str(row.get(field, "unknown"))
                    buckets[key] = buckets.get(key, 0) + 1
                return buckets
            """,
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
