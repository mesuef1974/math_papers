"""القفل لا يتقادم: كل ما في requirements.txt مثبّت في requirements.lock بإصدار يوافق قيده وبتجزئاته،
وDockerfile يثبّت من القفل وحده بـ --require-hashes."""

import re
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)")


def declared() -> list[Requirement]:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [Requirement(text) for line in lines if (text := line.split("#", 1)[0].strip())]


def locked() -> dict[str, tuple[str, int]]:
    """اسم الحزمة → (إصدارها، عدد تجزئاتها)."""
    pins: dict[str, tuple[str, int]] = {}
    name = ""
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if match := PIN.match(line):
            name = canonicalize_name(match.group(1))
            pins[name] = (match.group(2), 0)
        elif "--hash=sha256:" in line and name:
            pins[name] = (pins[name][0], pins[name][1] + 1)
    return pins


def test_every_declared_requirement_is_locked_within_its_specifier():
    pins = locked()
    for requirement in declared():
        name = canonicalize_name(requirement.name)
        assert name in pins, f"{requirement.name} غير مثبّت في requirements.lock؛ جدّد القفل"
        version = pins[name][0]
        assert requirement.specifier.contains(version, prereleases=True), (
            f"{requirement.name}=={version} في القفل يخالف القيد {requirement.specifier} في requirements.txt"
        )


def test_every_locked_package_carries_hashes():
    pins = locked()
    assert pins, "requirements.lock فارغ"
    missing = [name for name, (_, hashes) in pins.items() if hashes == 0]
    assert missing == []


def test_dockerfile_installs_from_the_lock_only():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "pip install --no-cache-dir --require-hashes -r requirements.lock" in dockerfile
    assert "-r requirements.txt" not in dockerfile
