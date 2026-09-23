#!/usr/bin/env python3
"""CLI utility to scan and import Chrome profiles into Dola Render Gateway."""

import argparse
import sys
from pathlib import Path

from chrome_profile_scanner import (
    bulk_import_chrome_profiles,
    format_bytes,
    import_chrome_profile,
    scan_chrome_profiles,
)


def print_table(profiles: list[dict]):
    """Prints a formatted console table of profiles."""
    print(f"\n{'#':<4} {'Directory':<14} {'Name':<24} {'Email':<32} {'Status':<15}")
    print("-" * 92)
    for idx, p in enumerate(profiles, start=1):
        status = f"✓ Imported ({p['imported_name']})" if p["is_imported"] else "○ Not imported"
        name_disp = (p["name"][:21] + "...") if len(p["name"]) > 24 else p["name"]
        email_disp = (p["email"][:29] + "...") if len(p["email"]) > 32 else p["email"]
        print(f"{idx:<4} {p['directory']:<14} {name_disp:<24} {email_disp:<32} {status:<15}")
    print("-" * 92)
    total = len(profiles)
    with_email = sum(1 for p in profiles if p["email"])
    imported = sum(1 for p in profiles if p["is_imported"])
    print(f"Total: {total} | With Email: {with_email} | Imported in Dola: {imported}\n")


def main():
    parser = argparse.ArgumentParser(description="Scan and import Chrome profiles into Dola")
    parser.add_argument("--list", action="store_true", help="List all scanned Chrome profiles")
    parser.add_argument("--search", default="", help="Search profiles by query (email, name, directory)")
    parser.add_argument("--import-dir", dest="import_dir", default="", help="Import a single profile by directory name (e.g. 'Profile 11')")
    parser.add_argument("--import-email", dest="import_email", default="", help="Import a profile by email address")
    parser.add_argument("--import-all", action="store_true", help="Bulk import all scanned Chrome profiles")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of profiles when importing bulk (0 = all)")
    parser.add_argument("--prefix", default="p_", help="Prefix for account names (default: 'p_')")
    args = parser.parse_args()

    profiles = scan_chrome_profiles()

    if args.search:
        q = args.search.lower()
        matched = [
            p for p in profiles
            if q in p["directory"].lower() or q in p["name"].lower() or q in p["email"].lower()
        ]
        print(f"[*] Found {len(matched)} matching profile(s) for '{args.search}':")
        print_table(matched)
        return

    if args.import_dir:
        target = next((p for p in profiles if p["directory"].lower() == args.import_dir.lower()), None)
        if not target:
            print(f"[!] Error: Chrome profile directory '{args.import_dir}' not found.", file=sys.stderr)
            sys.exit(1)
        print(f"[*] Importing {target['directory']} ({target['name']} <{target['email']}>)...")
        res = import_chrome_profile(target["directory"], email=target["email"])
        print(f"[+] Successfully imported as account: {res['name']} ({res['path']})")
        return

    if args.import_email:
        target = next((p for p in profiles if p["email"].lower() == args.import_email.lower()), None)
        if not target:
            print(f"[!] Error: No Chrome profile found with email '{args.import_email}'.", file=sys.stderr)
            sys.exit(1)
        print(f"[*] Importing {target['directory']} ({target['name']} <{target['email']}>)...")
        res = import_chrome_profile(target["directory"], email=target["email"])
        print(f"[+] Successfully imported as account: {res['name']} ({res['path']})")
        return

    if args.import_all:
        candidates = [p for p in profiles if not p["is_imported"]]
        if args.limit > 0:
            candidates = candidates[:args.limit]
        if not candidates:
            print("[*] All profiles are already imported in Dola pool!")
            return
        print(f"[*] Starting bulk import of {len(candidates)} profile(s)...")
        dirs = [p["directory"] for p in candidates]
        summary = bulk_import_chrome_profiles(dirs, prefix=args.prefix)
        print(f"\n[+] Bulk Import Complete:")
        print(f"    - Imported: {summary['imported_count']}")
        print(f"    - Skipped:  {summary['skipped_count']}")
        print(f"    - Failed:   {summary['failed_count']}")
        return

    # Default action: list
    print_table(profiles)
    print("Tip: Use --search <term> to filter, or --import-dir <dir> to import a profile.")


if __name__ == "__main__":
    main()
