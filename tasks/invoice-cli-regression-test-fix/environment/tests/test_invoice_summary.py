from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from invoice_tool.importer import import_invoices
from invoice_tool.summary import summarize


class InvoiceSummaryTests(unittest.TestCase):
    def test_imports_and_summarizes_invoices(self) -> None:
        invoices = import_invoices(Path("/app/sample_invoices.csv"))

        self.assertEqual(len(invoices), 3)
        self.assertEqual(
            summarize(invoices),
            {
                "invoice_count": 3,
                "total_amount": 245.75,
                "open_amount": 165.75,
            },
        )

    def test_import_trims_status_and_customer_fields(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
            handle.write("invoice_id,customer,amount,status\n")
            handle.write("INV-1,  Ada Lovelace  ,12.00, OPEN \n")
            path = Path(handle.name)

        invoice = import_invoices(path)[0]

        self.assertEqual(invoice.customer, "Ada Lovelace")
        self.assertEqual(invoice.status, "open")


if __name__ == "__main__":
    unittest.main()
