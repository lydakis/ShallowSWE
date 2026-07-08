from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class TaskVerifierWrapperTests(unittest.TestCase):
    def test_task_verifiers_propagate_hidden_check_status(self) -> None:
        for verifier in sorted((REPO_ROOT / "tasks").glob("*/tests/test.sh")):
            with self.subTest(verifier=verifier):
                text = verifier.read_text()

                self.assertIn("status=$?", text)
                self.assertIn('exit "$status"', text)

    def test_exact_artifact_schemas_are_visible_in_instructions(self) -> None:
        required_snippets = {
            "access-log-to-incidents": [
                "`summary.json` with keys `high`, `medium`, and `total_incidents`",
                "`incidents.csv` with columns `timestamp,service,method,path,status,severity,request_id`",
                "`rejects.csv` with columns `line,reason`",
            ],
            "billing-revenue-rollup": [
                "`summary.json`",
                "`period,plan,gross_usd,credits_usd,open_disputes_usd,net_usd`",
                "`account_id,segment,region,manager,recognized_usd,open_disputes_usd,net_at_risk_usd,status`",
                "`adjustment_id,invoice_id,account_id,type,amount_usd,status,period`",
                "`input,event_id,reason`",
            ],
            "ledger-schema-upgrade": [
                "`normalized_events.jsonl`",
                "`account_id,currency,event_id,event_type,amount_cents,amount_usd_micros,running_balance_cents,running_balance_usd_micros,recognition_month`",
                "`account_id,region,segment,currency,ending_balance_cents,ending_balance_usd_micros,status`",
                "`recognition_month,plan_id,currency,gross_cents,discount_cents,tax_cents,net_cents,net_usd_micros`",
                "`schema_version`, `source_files`, `normalized_events`, `ledger_rows`, `account_balance_rows`, `plan_revenue_rows`, `reject_count`, `currencies`, `net_usd_micros`, `generated_at`",
            ],
            "support-metrics-package": [
                "`summary.json` with keys `escalations`, `sla_breaches`, and `tickets`",
                "`agent_summary.csv` with columns `agent_id,name,tickets,sla_breaches`",
                "`sla_breaches.csv` with columns `ticket_id,agent_id,priority,response_minutes,target_minutes`",
            ],
            "ticket-update-dont-duplicate": [
                "Add one non-empty comment to the matching existing ticket",
                "The comment should mention saved-card coupon purchases",
                "`update_ticket <ticket_id> priority=P0`",
            ],
            "merge-divergent-config-branches": [
                "`merge_report.json` with exactly these keys",
                "`resolved_conflicts`: an array containing `retry_timeout_seconds`",
                "`sources`: an array containing `release` followed by `feature`",
            ],
        }

        for task_id, snippets in required_snippets.items():
            with self.subTest(task_id=task_id):
                instruction = (REPO_ROOT / "tasks" / task_id / "instruction.md").read_text()

                for snippet in snippets:
                    self.assertIn(snippet, instruction)

    def test_stateful_apply_task_verifiers_use_fresh_roots(self) -> None:
        stateful_tasks = {
            "merge-divergent-config-branches",
            "post-build-status",
            "release-branch-cherry-pick",
            "ticket-cut-from-bug-report",
            "ticket-update-dont-duplicate",
        }

        for task_id in stateful_tasks:
            with self.subTest(task_id=task_id):
                verifier = REPO_ROOT / "tasks" / task_id / "tests" / "test.sh"
                text = verifier.read_text()

                self.assertIn("copy_script_to_fresh_root", text)
                self.assertIn("write_file(", text)
                self.assertNotIn('run_script("apply_task.py", app)', text)
                self.assertNotIn("assert_json(app /", text)
                self.assertNotIn("assert_text(app /", text)


if __name__ == "__main__":
    unittest.main()
