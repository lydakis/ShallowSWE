from __future__ import annotations


def render_text(report: dict[str, float | int | str]) -> str:
    return "\n".join(
        [
            f"Account: {report['account']}",
            f"Transactions: {report['transaction_count']}",
            f"Debits: ${report['total_debits']:.2f}",
            f"Credits: ${report['total_credits']:.2f}",
            f"Net change: ${report['net_change']:.2f}",
        ]
    )


def render_csv(report: dict[str, float | int | str]) -> str:
    header = "account,transaction_count,total_debits,total_credits,net_change"
    row = (
        f"{report['account']},{report['transaction_count']},"
        f"{report['total_debits']:.2f},{report['total_credits']:.2f},"
        f"{report['net_change']:.2f}"
    )
    return f"{header}\n{row}"


def render_report(report: dict[str, float | int | str], output_format: str) -> str:
    if output_format == "text":
        return render_text(report)
    if output_format == "csv":
        return render_csv(report)
    raise ValueError(f"unsupported report format: {output_format}")
