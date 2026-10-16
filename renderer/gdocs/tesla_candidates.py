#!/usr/bin/env python3
"""Generate MOON42 Google Docs profiles for the 'in progress' candidates of
the tracking sheet."""

import argparse
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from renderer.gdocs import auth, config as config_module, logic, render, sheet  # noqa: E402

PROFILES_DIR = REPOSITORY_ROOT / "profiles"


def load_profiles(profiles_dir):
    """Return ({id: profile dict}, {id: is_draft}, {id: error text})."""
    profiles, drafts, errors = {}, {}, {}
    for path in sorted(Path(profiles_dir).glob("*.yaml")):
        try:
            profiles[path.stem], drafts[path.stem] = render.load_profile(path)
        except render.ProfileError as error:
            errors[path.stem] = str(error)
    return profiles, drafts, errors


def plan(rows, profiles):
    """Eligible rows with their match results: [(row, MatchResult)]."""
    eligible = [r for r in rows
                if logic.is_eligible(r.status, r.profile_text, r.profile_has_chip)]
    names = [(r.number, r.name) for r in eligible]
    known = [(pid, p["personalData"]["firstName"], p["personalData"]["lastName"])
             for pid, p in profiles.items()]
    matches = logic.match_rows(names, known)
    return [(row, matches[row.number]) for row in eligible]


def dry_run(planned, profiles, drafts, profile_errors):
    print(f"Dry-run: {len(planned)} jogosult sor, semmi nem készül.")
    for row, match in planned:
        if match.status == "matched":
            draft = " [DRAFT]" if drafts[match.profile_id] else ""
            print(f"  {row.number}. sor – {row.name}: {match.profile_id} → "
                  f"{render.doc_name(profiles[match.profile_id])}{draft}")
        else:
            print(f"  {row.number}. sor – {row.name}: kihagyva ({match.reason})")
        for warning in match.warnings:
            print(f"      Figyelmeztetés: {warning}")
    for pid, reason in profile_errors.items():
        print(f"  Hibás profil: {pid}: {reason}")
    return 1 if profile_errors or any(m.status == "error" for _, m in planned) else 0


def process(row, profile_id, profiles, drafts, ctx, report):
    """Generate one candidate; every failure is recorded in `report`."""
    label = f"{row.number}. sor – {row.name} ({profile_id})"
    doc = None
    try:
        try:
            doc, warnings = render.generate(
                ctx["drive"], ctx["docs"], profile_id, profiles[profile_id],
                drafts[profile_id], template_id=ctx["config"]["templateId"],
                folder_id=ctx["config"]["targetFolderId"],
                receipt_dir=ctx["receipt_dir"], sheet_email=row.email,
                sheet_mobile=row.mobile, sheet_row=row.number)
        except render._docfill().GenerationError as error:
            url = f" ({error.url})" if error.url else ""
            report["failed"].append(f"{label}: {error}{url}")
            return
        _finish(row, profile_id, drafts, ctx, report, label, doc, warnings)
    except Exception as error:
        report["failed"].append(f"{label}: {error}" + (f" ({doc.url})" if doc else ""))


def _finish(row, profile_id, drafts, ctx, report, label, doc, warnings):
    issues = warnings + doc.layout_issues
    draft = drafts[profile_id]
    notes = render.report_lines(doc, draft, warnings)
    notes[0] = f"{label}: {notes[0]}"
    ok = not doc.layout_issues
    try:
        written, message = sheet.write_profile_link(
            ctx["sheets"], ctx["config"]["spreadsheetId"], ctx["columns"],
            row, doc.name, doc.url)
        if not written:
            notes.append(f"      A táblázatba nem írtam: {message}. Doksi: {doc.url}")
            issues.append(f"Táblázatírás kihagyva: {message}")
            ok = False
        elif message:
            notes.append(f"      Chip helyett {message} került a cellába.")
    except Exception as error:
        notes.append(f"      Táblázatírás sikertelen: {error}. Doksi: {doc.url}")
        issues.append(f"Táblázatírás sikertelen: {error}")
        ok = False
    try:
        render.write_receipt(ctx["receipt_dir"], profile_id, doc, draft, issues,
                             row.number)
    except OSError as error:
        notes.append(f"      A nyugta nem írható: {error}")
        ok = False
    report["generated"].extend(notes)
    if not ok:
        report["problems"] = True


def run(args):
    cfg = config_module.load_config(args.config)
    credentials = auth.authenticate()
    drive, docs, sheets = auth.build_services(credentials)
    columns, rows = sheet.read_candidates(sheets, cfg["spreadsheetId"])
    profiles, drafts, profile_errors = load_profiles(PROFILES_DIR)
    planned = plan(rows, profiles)
    if args.dry_run:
        return dry_run(planned, profiles, drafts, profile_errors)

    ctx = {"drive": drive, "docs": docs, "sheets": sheets, "config": cfg,
           "columns": columns, "receipt_dir": render.RECEIPT_DIR}
    report = {"generated": [], "skipped": [],
              "failed": [f"Profil {pid}: {reason}" for pid, reason in profile_errors.items()],
              "problems": False}
    for row, match in planned:
        label = f"{row.number}. sor – {row.name}"
        if match.status == "matched":
            process(row, match.profile_id, profiles, drafts, ctx, report)
        elif match.status == "error":
            report["failed"].append(f"{label}: {match.reason}")
        else:
            report["skipped"].append(f"{label}: {match.reason}")
        for warning in match.warnings:
            report["skipped"].append(f"      Figyelmeztetés: {warning}")

    print(f"Összesítő: {len(planned)} jogosult sor.")
    for title, key in (("Generált", "generated"), ("Kihagyott", "skipped"),
                       ("Hibás", "failed")):
        if report[key]:
            print(f"{title}:")
            for line in report[key]:
                print(line if line.startswith("      ") else f"  {line}")
    return 1 if report["failed"] or report["problems"] else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="csak listáz, semmit nem hoz létre és nem ír")
    parser.add_argument("--config", type=Path, default=render.DEFAULT_CONFIG,
                        help="konfigurációs fájl (alapértelmezett: %(default)s)")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as error:  # config, sheet, API errors etc.
        print(f"Hiba: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
