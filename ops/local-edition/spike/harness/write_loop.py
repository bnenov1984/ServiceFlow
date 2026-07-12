"""Write-loop harness for the ADR-002 spike (power-loss & integrity checks).

Continuously inserts checksummed rows. After any interruption (pg_ctl -m immediate,
VM power-off), verify.py must find zero corrupt rows and a consistent count.

Usage: uv run python ops/spike/harness/write_loop.py --port 5599 [--duration 30]
"""

import argparse
import hashlib
import os
import time

import psycopg

DDL = """
CREATE TABLE IF NOT EXISTS spike_writes (
    seq bigserial PRIMARY KEY,
    payload text NOT NULL,
    checksum text NOT NULL
)
"""


def checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--duration", type=int, default=0, help="seconds; 0 = until killed")
    args = parser.parse_args()

    dsn = (
        f"host=localhost port={args.port} dbname=postgres "
        f"user=serviceflow password=spike-only-password"
    )
    deadline = time.monotonic() + args.duration if args.duration else None
    written = 0

    with psycopg.connect(dsn) as conn:
        conn.execute(DDL)
        conn.commit()
        while deadline is None or time.monotonic() < deadline:
            payload = os.urandom(64).hex()
            conn.execute(
                "INSERT INTO spike_writes (payload, checksum) VALUES (%s, %s)",
                (payload, checksum(payload)),
            )
            conn.commit()  # commit per row: every acknowledged write must survive
            written += 1

    print(f"write_loop: committed {written} rows")


if __name__ == "__main__":
    main()
