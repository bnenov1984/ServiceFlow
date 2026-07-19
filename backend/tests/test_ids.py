import time

from business_os.shared_kernel.ids import new_id


def test_uuid7_version_and_variant() -> None:
    u = new_id()
    assert u.version == 7
    assert (u.bytes[8] & 0xC0) == 0x80


def test_uuid7_time_ordered() -> None:
    a = new_id()
    time.sleep(0.002)
    b = new_id()
    assert a < b


def test_uuid7_unique() -> None:
    ids = {new_id() for _ in range(10_000)}
    assert len(ids) == 10_000
