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

BATCH_MIN = {
    "beemers_heiko.txt": 3,
    "ackermann_stefan.txt": 5,
    "bauchmueller_peter.txt": 10,
    "ahmad_ahmad.txt": 3,
    "arnold_jens.txt": 3,
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


def test_batch_samples_have_experience():
    batch_dir = ROOT / "artifacts" / "gulp-samples" / "txt"
    assert batch_dir.is_dir(), batch_dir
    for name, vmin in BATCH_MIN.items():
        fp = batch_dir / name
        assert fp.is_file(), name
        stem = fp.stem
        last, first = stem.rsplit("_", 1)
        prof = clean_gulp_profile(
            fp.read_text(encoding="utf-8", errors="replace"),
            first=first.title(),
            last=last.replace("_", " ").title(),
        )
        ex = prof.get("experience") or []
        plain = profile_to_aid_plain(prof)
        assert len(ex) >= vmin, f"{name}: exp={len(ex)} < {vmin}"
        assert plain.count("Zeitraum:") >= vmin, f"{name}: Zeitraum={plain.count('Zeitraum:')}"


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
    test_batch_samples_have_experience()
    test_stoll_no_false_kunde()
    print("OK gulp_profile_clean formats")
