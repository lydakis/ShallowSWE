from __future__ import annotations

import argparse

from .migrate import migrate


def main() -> None:
    parser = argparse.ArgumentParser(prog="ledger-migrate")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    migrate(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
