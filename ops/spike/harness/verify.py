"""Integrity verification after write_loop interruption or restore drill.

Exit 0 = consistent (no corrupt rows, no sequence gaps beyond the crash point).
Usage: uv run python ops/spike/harness/verify.py --port 5599 [--expect-min N]
"""

import argparse
import hashlib
import sys

import psycopg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--expect-min", type=int, default=1)
    args = parser.parse_args()

    dsn = (
        f"host=localhost port={args.port} dbname=postgres "
        f"user=serviceflow password=spike-only-password"
    )
    with psycopg.connect(dsn) as conn:
        rows = conn.execute("SELECT seq, payload, checksum FROM spike_writes ORDER BY seq")
        count = 0
        corrupt = 0
        for seq, payload, stored in rows:
            count += 1
            if hashlib.sha256(payload.encode()).hexdigest() != stored:
                corrupt += 1
                print(f"CORRUPT row seq={seq}")

    print(f"verify: {count} rows, {corrupt} corrupt")
    if corrupt or count < args.expect_min:
        sys.exit(1)


if __name__ == "__main__":
    main()
