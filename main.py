"""Pipeline entrypoint.

Usage:
    python main.py discover              # dump OneMap theme catalog (run first)
    python main.py dining                # fetch healthier dining options
    python main.py residential           # fetch HDB (+ condo) residential locations
    python main.py accessibility [--limit N]
    python main.py all [--limit N]       # run dining -> residential -> accessibility
"""

from __future__ import annotations

import argparse

from src import compute_accessibility, discover_themes, fetch_dining, fetch_residential


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("discover", help="Dump OneMap's theme catalog to find real queryNames.")
    sub.add_parser("dining", help="Fetch healthier dining options.")
    sub.add_parser("residential", help="Fetch HDB (+ condo) residential locations.")

    acc_parser = sub.add_parser("accessibility", help="Compute dining options within 1km walk per postal code.")
    acc_parser.add_argument("--limit", type=int, default=None)

    all_parser = sub.add_parser("all", help="Run dining -> residential -> accessibility.")
    all_parser.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()

    if args.command == "discover":
        discover_themes.main()
    elif args.command == "dining":
        fetch_dining.main()
    elif args.command == "residential":
        fetch_residential.main()
    elif args.command == "accessibility":
        compute_accessibility.run(args.limit)
    elif args.command == "all":
        fetch_dining.main()
        fetch_residential.main()
        compute_accessibility.run(args.limit)


if __name__ == "__main__":
    main()
