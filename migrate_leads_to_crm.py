"""
One-shot migration: push all existing bot leads to the CRM.

Usage (from projectpress/):
    python migrate_leads_to_crm.py [--dry-run]
"""
import argparse
import sys

from db import connect
from dialog import get_lead_snapshot
from crm_sync import send_event, crm_sync_enabled


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without sending")
    args = parser.parse_args()

    if not args.dry_run and not crm_sync_enabled():
        print("ERROR: CRM_API_URL is not set in .env — aborting.")
        sys.exit(1)

    conn = connect()
    leads = conn.execute(
        "SELECT id, tg_id, status FROM leads ORDER BY id"
    ).fetchall()

    print(f"Found {len(leads)} leads to migrate.")
    ok = 0
    fail = 0

    for row in leads:
        snapshot = get_lead_snapshot(conn, row["id"])
        if not snapshot:
            print(f"  [SKIP] lead id={row['id']} — snapshot empty")
            continue

        event = "lead.migrated"
        meta = {"actor_tg_id": "migration_script"}

        if args.dry_run:
            print(f"  [DRY] lead id={row['id']} tg_id={row['tg_id']} status={row['status']}")
        else:
            result = send_event(event, snapshot, meta)
            if result:
                print(f"  [OK]  lead id={row['id']} tg_id={row['tg_id']} status={row['status']}")
                ok += 1
            else:
                print(f"  [ERR] lead id={row['id']} tg_id={row['tg_id']} — send failed")
                fail += 1

    conn.close()

    if not args.dry_run:
        print(f"\nDone: {ok} synced, {fail} failed.")


if __name__ == "__main__":
    main()
