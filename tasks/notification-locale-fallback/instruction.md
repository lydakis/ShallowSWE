# Add Notification Locale Fallback

The notification renderer currently loads exactly one catalog. Add locale fallback and escaping without changing default-locale output.

Fallback rules:

- Locale catalogs live in `notifier/catalogs/`.
- `default.json` is the final fallback catalog.
- A locale with a region falls back from the full locale to the base language, then to default.
- Example: `de-AT` falls back to `de`, then `default`.
- Missing message keys should use the first catalog in the fallback chain that defines the key.
- Missing template variables should render as an empty string.
- Template values must be HTML-escaped with `quote=True`.
- Default-locale output for existing templates must stay byte-identical except for required escaping.
- Keep the public CLI: `python -m notifier.cli <events.json>` prints one JSON object per event.

Keep the work local to this repository. Do not use network access.
