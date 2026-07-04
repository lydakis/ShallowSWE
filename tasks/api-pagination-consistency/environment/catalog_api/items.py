def list_items(items, page=None, per_page=None): return list(items)
def summarize_page(items, page=None, per_page=None):
    selected=list_items(items, page=page, per_page=per_page)
    return {"count":len(selected),"ids":[item["id"] for item in selected]}
