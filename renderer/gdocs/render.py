#!/usr/bin/env python3
"""Generate MOON42 Google Docs profiles for the 'in progress' candidates of
the tracking sheet."""

import argparse
import json
from pathlib import Path
import re
import sys
import types

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from renderer.gdocs import auth, config as config_module, logic, sheet  # noqa: E402

DEFAULT_CONFIG = REPOSITORY_ROOT / "renderer" / "gdocs" / "config.yaml"
PROFILES_DIR = REPOSITORY_ROOT / "profiles"
RECEIPT_DIR = REPOSITORY_ROOT / "target" / "gdocs"


def _docfill():
    from renderer.gdocs import docfill
    return docfill


def is_draft(text):
    """True if a line of the leading '#' comment block starts with '# DRAFT'."""
    for line in text.splitlines():
        if not line.startswith("#"):
            return False
        if line.startswith("# DRAFT"):
            return True
    return False


def load_profiles(profiles_dir):
    """Return ({id: profile dict}, {id: is_draft}, {id: error text})."""
    profiles, drafts, errors = {}, {}, {}
    for path in sorted(Path(profiles_dir).glob("*.yaml")):
        try:
            text = path.read_text(encoding="utf-8")
            drafts[path.stem] = is_draft(text)
            personal = yaml.safe_load(text)["personalData"]
            for key in ("firstName", "lastName"):
                if not isinstance(personal[key], str) or not personal[key].strip():
                    raise ValueError(f"hiányzó vagy nem szöveges {key}")
            profiles[path.stem] = yaml.safe_load(text)
        except (OSError, UnicodeDecodeError, yaml.YAMLError, KeyError,
                TypeError, ValueError) as error:
            errors[path.stem] = f"A profil nem olvasható: {error}"
    return profiles, drafts, errors


def doc_name(profile):
    personal = profile["personalData"]
    return f"{personal['firstName']} {personal['lastName']} - MOON42"


def write_receipt(receipt_dir, profile_id, doc, row, draft, issues):
    path = Path(receipt_dir) / f"{profile_id}.json"
    previous = []
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            previous = list(old.get("previousDocuments", []))
            if old.get("documentId"):
                previous.append({"documentId": old["documentId"], "url": old.get("url")})
        except (OSError, ValueError, AttributeError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "documentId": doc.document_id, "name": doc.name, "url": doc.url,
        "parentFolderIds": doc.parent_folder_ids, "sheetRow": row.number,
        "draft": draft, "issues": issues, "previousDocuments": previous,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


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
                  f"{doc_name(profiles[match.profile_id])}{draft}")
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
        docfill = _docfill()
        profile = profiles[profile_id]
        personal = profile["personalData"]
        email, email_warning = logic.moon42_email(
            personal["firstName"], personal["lastName"], row.email)
        mobile = logic.pick_mobile(personal.get("contacts"), row.mobile)
        try:
            doc = docfill.generate_document(
                ctx["drive"], ctx["docs"], template_id=ctx["config"]["templateId"],
                folder_id=ctx["config"]["targetFolderId"], profile=profile,
                email=email, mobile=mobile)
        except docfill.GenerationError as error:
            url = f" ({error.url})" if error.url else ""
            report["failed"].append(f"{label}: {error}{url}")
            if error.document_id:
                failed_doc = types.SimpleNamespace(
                    document_id=error.document_id, name=doc_name(profile),
                    url=error.url, parent_folder_ids=[ctx["config"]["targetFolderId"]])
                write_receipt(ctx["receipt_dir"], profile_id, failed_doc, row,
                              drafts[profile_id], [f"Generálási hiba: {error}"])
            return
        _finish(row, profile_id, drafts, ctx, report, label, doc, email_warning)
    except Exception as error:
        report["failed"].append(f"{label}: {error}" + (f" ({doc.url})" if doc else ""))


def _finish(row, profile_id, drafts, ctx, report, label, doc, email_warning):
    warnings = ([email_warning] if email_warning else []) + doc.warnings
    issues = warnings + doc.layout_issues
    draft = drafts[profile_id]
    notes = [f"{label}: {doc.url}" + (" [DRAFT]" if draft else "")]
    notes += [f"      Figyelmeztetés: {w}" for w in warnings]
    notes += [f"      Tördelési probléma: {i} (kézi döntés kell)"
              for i in doc.layout_issues]
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
        write_receipt(ctx["receipt_dir"], profile_id, doc, row, draft, issues)
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
           "columns": columns, "receipt_dir": RECEIPT_DIR}
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
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="konfigurációs fájl (alapértelmezett: %(default)s)")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as error:  # config, sheet, API errors etc.
        print(f"Hiba: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
