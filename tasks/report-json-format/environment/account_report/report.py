from __future__ import annotations

from .model import Transaction


def build_report(transactions: list[Transaction]) -> dict[str, float | int | str]:
    if not transactions:
        raise ValueError("cannot build report for an empty transaction set")

    accounts = {transaction.account for transaction in transactions}
    if len(accounts) != 1:
        raise ValueError("all transactions must belong to one account")

    total_debits = sum(
        transaction.amount for transaction in transactions if transaction.kind == "debit"
    )
    total_credits = sum(
        transaction.amount for transaction in transactions if transaction.kind == "credit"
    )
    return {
        "account": transactions[0].account,
        "transaction_count": len(transactions),
        "total_debits": round(total_debits, 2),
        "total_credits": round(total_credits, 2),
        "net_change": round(total_credits - total_debits, 2),
    }
