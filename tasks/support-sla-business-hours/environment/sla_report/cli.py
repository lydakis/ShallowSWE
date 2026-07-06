from __future__ import annotations

import argparse

from .report import write_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="sla-report")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    write_report(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
