from notifier.renderer import render_event


def test_default_catalog_still_renders_existing_template():
    assert render_event(
        {"id": "x", "locale": "default", "template": "welcome", "vars": {"name": "Ada"}}
    ) == {"id": "x", "locale": "default", "body": "Welcome, Ada!"}
