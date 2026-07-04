import csv, json, sys
from .parser import parse_retry_row
def main():
    with open(sys.argv[1], newline="") as handle:
        for row in csv.DictReader(handle): print(json.dumps(parse_retry_row(row), sort_keys=True))
if __name__ == "__main__": main()
