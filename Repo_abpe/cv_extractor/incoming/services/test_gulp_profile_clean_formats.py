"""Smoke-test: Gulp project formats → experience[]."""
from __future__ import annotations

from pathlib import Path

from gulp_profile_clean import clean_gulp_profile, profile_to_aid_plain

ROOT = Path(__file__).resolve().parents[4]
# repo root: .../udoo-reprap
SAMPLES = ROOT / "artifacts" / "gulp-keyword" / "dryrun-fails" / "txt"

EXPECT_MIN = {
    "broeckling_joerg.txt": 4,
    "pauser_wolfgang.txt": 15,
    "stotz_michael.txt": 5,
    "hoellig_thomas.txt": 1,
}


def test_formats_have_experience():
    assert SAMPLES.is_dir(), f"missing samples {SAMPLES}"
    for name, vmin in EXPECT_MIN.items():
        fp = SAMPLES / name
        assert fp.is_file(), name
        parts = fp.stem.rsplit("_", 1)
        last, first = parts[0], parts[1]
        prof = clean_gulp_profile(
            fp.read_text(encoding="utf-8", errors="replace"),
            first=first.title(),
            last=last.replace("_", " ").title(),
        )
        ex = prof.get("experience") or []
        plain = profile_to_aid_plain(prof)
        assert len(ex) >= vmin, f"{name}: exp={len(ex)} < {vmin}"
        assert plain.count("Zeitraum:") >= vmin, f"{name}: no Zeitraum in AID plain"
        with_period = sum(1 for e in ex if (e.get("period") or "").strip())
        assert with_period >= vmin, f"{name}: with_period={with_period}"


def test_stoll_no_false_kunde():
    fp = SAMPLES / "stoll_tobias.txt"
    if not fp.is_file():
        return
    prof = clean_gulp_profile(
        fp.read_text(encoding="utf-8", errors="replace"),
        first="Tobias",
        last="Stoll",
    )
    assert len(prof.get("experience") or []) == 0


if __name__ == "__main__":
    test_formats_have_experience()
    test_stoll_no_false_kunde()
    print("OK gulp_profile_clean formats")
