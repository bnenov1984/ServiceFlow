"""UUIDv7 identifiers (ADR-013): time-ordered, globally unique, per RFC 9562."""

import os
import time
import uuid


def new_id() -> uuid.UUID:
    unix_ms = time.time_ns() // 1_000_000
    rand = os.urandom(10)
    b = bytearray(16)
    b[0:6] = unix_ms.to_bytes(6, "big")
    b[6] = 0x70 | (rand[0] & 0x0F)  # version 7
    b[7] = rand[1]
    b[8] = 0x80 | (rand[2] & 0x3F)  # variant 10
    b[9:16] = rand[3:10]
    return uuid.UUID(bytes=bytes(b))
