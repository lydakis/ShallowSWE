#!/usr/bin/env bash
set -uo pipefail
mkdir -p /logs/verifier
python3 - <<'PY'
from __future__ import annotations
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
RISK_FIELDS={"account","owner","segment","arr","days_to_renewal","seat_utilization_pct","open_critical_tickets","concession_days_remaining","risk_level","risk_reasons","recommended_action"}
CONCESSION_FIELDS={"account","owner","type","amount","days_remaining","status","reason"}
RISK_ORDER={"blocked":0,"critical":1,"attention":2,"healthy":3}
def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True))
def write_fixture(root: Path, *, variant: str) -> Path:
    data_dir=root/variant; data_dir.mkdir()
    if variant=="hidden-a":
        accounts=[{"account_id":"ha-1","name":"Aster Labs","owner":"Ada Chen","segment":"enterprise"},{"account_id":"ha-2","name":"Boreal Energy","owner":"Ben Cruz","segment":"midmarket"},{"account_id":"ha-3","name":"Canyon Retail","owner":"Ada Chen","segment":"growth"}]
        contracts={"report_date":"2026-09-01","contracts":[{"account_id":"ha-1","status":"active","renewal_date":"2026-09-12","arr":210000},{"account_id":"ha-2","status":"active","renewal_date":"2026-10-15","arr":55000},{"account_id":"ha-3","status":"canceled","renewal_date":"2026-09-25","arr":32000}]}
        usage=[{"account_id":"ha-1","active_users":40,"licensed_seats":120,"last_login_at":"2026-07-20"},{"account_id":"ha-2","active_users":72,"licensed_seats":80,"last_login_at":"2026-08-25"},{"account_id":"ha-3","active_users":10,"licensed_seats":0,"last_login_at":"2026-08-31"}]
        tickets=[{"account_id":"ha-2","severity":"critical","status":"open","opened_at":"2026-08-30"},{"account_id":"ha-1","severity":"critical","status":"resolved","opened_at":"2026-08-20"},{"account_id":"ha-3","severity":"critical","status":"open","opened_at":"2026-08-31"}]
        concessions=[{"account_id":"ha-1","type":"discount","amount":9000,"expires_on":"2026-09-08","reason":"adoption recovery"},{"account_id":"ha-2","type":"credit","amount":2500,"expires_on":"2026-10-01","reason":"support incident"},{"account_id":"ha-1","type":"old_credit","amount":1000,"expires_on":"2026-08-01","reason":"expired"}]
    else:
        accounts=[{"account_id":"hb-1","name":"Delta School","owner":"Nia Shah","segment":"education"},{"account_id":"hb-2","name":"Elm Robotics","owner":"Nia Shah","segment":"enterprise"},{"account_id":"hb-3","name":"Fjord Media","owner":"Omar Reid","segment":"midmarket"},{"account_id":"hb-4","name":"Grove Studio","owner":"Pam Yu","segment":"startup"}]
        contracts={"report_date":"2026-11-10","contracts":[{"account_id":"hb-1","status":"trialing","renewal_date":"2026-11-20","arr":24000},{"account_id":"hb-2","status":"active","renewal_date":"2026-12-30","arr":180000},{"account_id":"hb-3","status":"active","renewal_date":"2026-11-25","arr":76000},{"account_id":"hb-4","status":"active","renewal_date":"2027-01-05","arr":9000}]}
        usage=[{"account_id":"hb-1","active_users":8,"licensed_seats":30,"last_login_at":"2026-11-09"},{"account_id":"hb-2","active_users":420,"licensed_seats":500,"last_login_at":"2026-09-20"},{"account_id":"hb-3","active_users":70,"licensed_seats":100,"last_login_at":"2026-11-05"},{"account_id":"hb-4","active_users":25,"licensed_seats":30,"last_login_at":"2026-11-04"}]
        tickets=[{"account_id":"hb-3","severity":"critical","status":"resolved","opened_at":"2026-11-01"},{"account_id":"hb-4","severity":"low","status":"open","opened_at":"2026-11-02"}]
        concessions=[{"account_id":"hb-1","type":"pilot_credit","amount":1500,"expires_on":"2026-11-18","reason":"trial close"},{"account_id":"hb-2","type":"service_credit","amount":8000,"expires_on":"2026-12-20","reason":"stability"},{"account_id":"hb-2","type":"discount","amount":5000,"expires_on":"2026-12-01","reason":"older active duplicate"},{"account_id":"hb-3","type":"expired","amount":2000,"expires_on":"2026-10-01","reason":"expired"}]
    for name, value in [("accounts.json",accounts),("contracts.json",contracts),("usage.json",usage),("tickets.json",tickets),("concessions.json",concessions)]: write_json(data_dir/name,value)
    return data_dir
def load_json(data_dir: Path, name: str) -> object: return json.loads((data_dir/name).read_text())
def expected(data_dir: Path) -> dict[str, object]:
    accounts=load_json(data_dir,"accounts.json"); contracts_doc=load_json(data_dir,"contracts.json"); usage_rows=load_json(data_dir,"usage.json"); tickets=load_json(data_dir,"tickets.json"); concessions=load_json(data_dir,"concessions.json")
    report_date=date.fromisoformat(contracts_doc["report_date"]); contracts={r["account_id"]:r for r in contracts_doc["contracts"]}; usage={r["account_id"]:r for r in usage_rows}
    active_concessions={}
    for c in concessions:
        exp=date.fromisoformat(c["expires_on"])
        if exp<report_date: continue
        cur=active_concessions.get(c["account_id"])
        if cur is None or c["expires_on"]>cur["expires_on"]: active_concessions[c["account_id"]]=c
    open_critical=defaultdict(int)
    for t in tickets:
        if t["severity"]=="critical" and t["status"] not in {"closed","resolved"}: open_critical[t["account_id"]]+=1
    risk_rows=[]
    for a in accounts:
        aid=a["account_id"]; contract=contracts[aid]; u=usage[aid]; days=(date.fromisoformat(contract["renewal_date"])-report_date).days
        licensed=int(u["licensed_seats"]); util=0 if licensed==0 else int(int(u["active_users"])*100/licensed); crit=int(open_critical.get(aid,0)); c=active_concessions.get(aid)
        concession_days=""; concession_expiring=False
        if c is not None:
            concession_days=(date.fromisoformat(c["expires_on"])-report_date).days; concession_expiring=int(concession_days)<=14
        contract_active=contract["status"] in {"active","trialing"}; stale=(report_date-date.fromisoformat(u["last_login_at"])).days>30; high_arr_stale=int(contract["arr"])>=100000 and stale
        reasons=[]
        if not contract_active: reasons.append("contract_not_active")
        if days<=30: reasons.append("renewal_soon")
        if util<60: reasons.append("low_seat_utilization")
        if crit>=1: reasons.append("open_critical_ticket")
        if concession_expiring: reasons.append("concession_expiring")
        if high_arr_stale: reasons.append("stale_usage")
        if not contract_active: level="blocked"; action="Restore contract"
        elif crit>=1: level="critical"; action="Escalate support"
        elif days<=14 and util<50: level="critical"; action="Executive renewal review"
        elif days<=30: level="attention"; action="Schedule renewal plan"
        elif util<60: level="attention"; action="Drive adoption plan"
        elif concession_expiring: level="attention"; action="Review concession"
        elif high_arr_stale: level="attention"; action="Verify executive engagement"
        else: level="healthy"; action="Monitor"
        risk_rows.append({"account_id":aid,"account":a["name"],"owner":a["owner"],"segment":a["segment"],"arr":int(contract["arr"]),"days_to_renewal":days,"seat_utilization_pct":util,"open_critical_tickets":crit,"concession_days_remaining":concession_days,"risk_level":level,"risk_reasons":",".join(reasons) if reasons else "none","recommended_action":action})
    risk_rows.sort(key=lambda r:(RISK_ORDER[str(r["risk_level"])],str(r["owner"]),str(r["account"])))
    by_id={a["account_id"]:a for a in accounts}; concession_rows=[]
    for aid,c in active_concessions.items():
        a=by_id[aid]; days=(date.fromisoformat(c["expires_on"])-report_date).days
        concession_rows.append({"account_id":aid,"account":a["name"],"owner":a["owner"],"type":c["type"],"amount":int(c["amount"]),"days_remaining":days,"status":"expiring" if days<=14 else "active","reason":c["reason"]})
    concession_rows.sort(key=lambda r:(int(r["days_remaining"]),str(r["owner"]),str(r["account"]),str(r["type"])))
    return {"risk_rows":risk_rows,"risk_metrics":{"accounts":len(accounts),"critical":sum(r["risk_level"] in {"blocked","critical"} for r in risk_rows),"attention":sum(r["risk_level"]=="attention" for r in risk_rows),"concessions-expiring":sum(r["concession_days_remaining"]!="" and int(r["concession_days_remaining"])<=14 for r in risk_rows)},"concession_rows":concession_rows,"concession_metrics":{"active-concessions":len(concession_rows),"expiring-concessions":sum(r["status"]=="expiring" for r in concession_rows),"total-concession-amount":sum(int(r["amount"]) for r in concession_rows)}}
class ContractParser(HTMLParser):
    def __init__(self): super().__init__(); self.main_screens=[]; self.h1_texts=[]; self.metrics={}; self.tables=defaultdict(list); self._metric=None; self._metric_text=[]; self._h1=False; self._h1_text=[]; self._table=None; self._row=None; self._field=None; self._field_text=[]
    def handle_starttag(self,tag,attrs):
        attr={k:v or "" for k,v in attrs}
        if tag=="main" and "data-screen" in attr: self.main_screens.append(attr["data-screen"])
        if tag=="h1": self._h1=True; self._h1_text=[]
        if "data-metric" in attr: self._metric=attr["data-metric"]; self._metric_text=[]
        if tag=="table" and "data-table" in attr: self._table=attr["data-table"]
        if tag=="tr" and self._table and "data-account-id" in attr: self._row={"account_id":attr["data-account-id"],"fields":{}}
        if tag=="td" and self._row is not None and "data-field" in attr: self._field=attr["data-field"]; self._field_text=[]
    def handle_data(self,data):
        if self._metric is not None: self._metric_text.append(data)
        if self._h1: self._h1_text.append(data)
        if self._field is not None: self._field_text.append(data)
    def handle_endtag(self,tag):
        if tag=="h1" and self._h1: self.h1_texts.append("".join(self._h1_text).strip()); self._h1=False
        if self._metric is not None and tag in {"span","div","section","strong"}: self.metrics[self._metric]="".join(self._metric_text).strip(); self._metric=None
        if tag=="td" and self._row is not None and self._field is not None: self._row["fields"][self._field]="".join(self._field_text).strip(); self._field=None
        if tag=="tr" and self._table and self._row is not None: self.tables[self._table].append(self._row); self._row=None
        if tag=="table": self._table=None
def parse(html): p=ContractParser(); p.feed(html); return p
def render(route: str, data_dir: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp)/"out.html"; subprocess.run([sys.executable,"-m","workspace_app.cli","--route",route,"--data-dir",str(data_dir),"--output",str(out)],check=True,cwd="/app"); return out.read_text()
def assert_metrics(tc,p,exp): tc.assertEqual(p.metrics,{k:str(v) for k,v in exp.items()})
def assert_risk(tc,data_dir):
    exp=expected(data_dir); html=render("/renewals/risk",data_dir); p=parse(html); tc.assertIn("renewal-risk",p.main_screens); tc.assertIn("Renewal Risk",p.h1_texts); tc.assertIn('href="/renewals/risk"',html); tc.assertIn('>Renewals</a>',html); assert_metrics(tc,p,exp["risk_metrics"]); rows=p.tables.get("renewal-risk",[]); tc.assertEqual(len(rows),len(exp["risk_rows"])); tc.assertEqual([r["account_id"] for r in rows],[r["account_id"] for r in exp["risk_rows"]]); actual={r["account_id"]:r["fields"] for r in rows}
    for row in exp["risk_rows"]:
        f=actual[row["account_id"]]; tc.assertEqual(set(f),RISK_FIELDS)
        for field in RISK_FIELDS: tc.assertEqual(f[field],str(row[field]),(row["account_id"],field))
def assert_concessions(tc,data_dir):
    exp=expected(data_dir); html=render("/renewals/concessions",data_dir); p=parse(html); tc.assertIn("renewal-concessions",p.main_screens); tc.assertIn("Renewal Concessions",p.h1_texts); assert_metrics(tc,p,exp["concession_metrics"]); rows=p.tables.get("renewal-concessions",[]); tc.assertEqual(len(rows),len(exp["concession_rows"])); tc.assertEqual([r["account_id"] for r in rows],[r["account_id"] for r in exp["concession_rows"]]); actual={r["account_id"]:r["fields"] for r in rows}
    for row in exp["concession_rows"]:
        f=actual[row["account_id"]]; tc.assertEqual(set(f),CONCESSION_FIELDS)
        for field in CONCESSION_FIELDS: tc.assertEqual(f[field],str(row[field]),(row["account_id"],field))
class RenewalVerifier(unittest.TestCase):
    def test_source_structure_and_unittest_regression(self):
        for path in ["/app/workspace_app/screens/renewal_risk.py","/app/workspace_app/screens/renewal_concessions.py","/app/workspace_app/selectors/renewals.py"]: self.assertTrue(Path(path).exists(),path)
        routing=Path("/app/workspace_app/routing.py").read_text(); self.assertIn("/renewals/risk",routing); self.assertIn("/renewals/concessions",routing)
        nav=Path("/app/workspace_app/nav.py").read_text(); self.assertIn("Renewals",nav); self.assertIn("/renewals/risk",nav)
        test_files=list(Path("/app/tests").glob("test*.py")); self.assertTrue(test_files); text="\n".join(p.read_text() for p in test_files); self.assertIn("/renewals/risk",text); self.assertIn("/renewals/concessions",text)
        subprocess.run([sys.executable,"-m","unittest","discover","-s","tests"],cwd="/app",check=True)
    def test_existing_routes_still_render_and_nav_includes_new_item(self):
        for route,screen in [("/","home"),("/accounts","accounts"),("/support","support"),("/billing","billing"),("/reports","reports")]:
            html=render(route,Path("/app/fixtures/visible")); self.assertIn(f'data-screen="{screen}"',html); self.assertIn('href="/renewals/risk"',html); self.assertIn('>Renewals</a>',html)
    def test_visible_fixture_exact(self):
        data=Path("/app/fixtures/visible"); assert_risk(self,data); assert_concessions(self,data)
    def test_hidden_fixtures_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for variant in ["hidden-a","hidden-b"]:
                with self.subTest(variant=variant): data=write_fixture(root,variant=variant); assert_risk(self,data); assert_concessions(self,data)
suite=unittest.defaultTestLoader.loadTestsFromTestCase(RenewalVerifier); result=unittest.TextTestRunner(verbosity=1).run(suite); Path("/logs/verifier/reward.txt").write_text("1" if result.wasSuccessful() else "0")
if not result.wasSuccessful(): sys.exit(1)
PY
status=$?
cat /logs/verifier/reward.txt 2>/dev/null || echo 0
exit "$status"
