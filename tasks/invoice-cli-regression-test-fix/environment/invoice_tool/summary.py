from __future__ import annotations

from .importer import Invoice


def summarize(invoices: list[Invoice]) -> dict[str, float | int]:
    total_amount = sum(invoice.amount for invoice in invoices)
    open_amount = sum(invoice.amount for invoice in invoices if invoice.status == "open")
    return {
        "invoice_count": len(invoices),
        "total_amount": round(total_amount, 2),
        "open_amount": round(open_amount, 2),
    }
