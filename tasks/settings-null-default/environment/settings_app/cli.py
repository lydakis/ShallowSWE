from __future__ import annotations
import argparse, json
from .config import load_settings
def main() -> None:
    parser = argparse.ArgumentParser(prog="settings-dump")
    parser.add_argument("config_path")
    args = parser.parse_args()
    print(json.dumps(load_settings(args.config_path), sort_keys=True))
if __name__ == "__main__": main()
