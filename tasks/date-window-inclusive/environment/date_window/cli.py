from __future__ import annotations
import argparse
from datetime import date
from .events import filter_events, load_events
def main() -> None:
    parser = argparse.ArgumentParser(prog="event-window")
    parser.add_argument("csv_path"); parser.add_argument("--start-date", required=True); parser.add_argument("--end-date", required=True)
    args = parser.parse_args()
    for event in filter_events(load_events(args.csv_path), date.fromisoformat(args.start_date), date.fromisoformat(args.end_date)):
        print(event.event_id)
if __name__ == "__main__": main()
