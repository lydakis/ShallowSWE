import csv, io, json
def build_rows(users): return [{"id":u["id"],"email":u["email"],"display_name":f"{u['first_name']} {u['last_name']}"} for u in users]
def render_json(users): return json.dumps(build_rows(users), indent=2, sort_keys=True)
def render_csv(users):
    out=io.StringIO(); writer=csv.DictWriter(out, fieldnames=["id","email","display_name"]); writer.writeheader(); writer.writerows(build_rows(users)); return out.getvalue().strip()
