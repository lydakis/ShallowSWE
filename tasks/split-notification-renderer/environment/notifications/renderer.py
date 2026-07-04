def render_text(n): return f"[{n['severity'].upper()}] {n['title']}: {n['body']}"
def render_html(n): return f"<article class='{n['severity']}'><h1>{n['title']}</h1><p>{n['body']}</p></article>"
