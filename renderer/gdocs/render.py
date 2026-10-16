#!/usr/bin/env python3
"""Generate the MOON42 Google Docs profile of one YAML profile into a Drive
folder."""

import argparse
import json
from pathlib import Path
import sys
import types

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from renderer.gdocs import auth, config as config_module, logic  # noqa: E402

DEFAULT_CONFIG = REPOSITORY_ROOT / "renderer" / "gdocs" / "config.yaml"
RECEIPT_DIR = REPOSITORY_ROOT / "target" / "gdocs"


class ProfileError(ValueError):
    """Unreadable or invalid profile; the message is user-facing (Hungarian)."""


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


def load_profile(path):
    """Return (profile dict, is_draft); raise ProfileError if unusable."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        profile = yaml.safe_load(text)
        personal = profile["personalData"]
        for key in ("firstName", "lastName"):
            if not isinstance(personal[key], str) or not personal[key].strip():
                raise ValueError(f"hiányzó vagy nem szöveges {key}")
    except (OSError, UnicodeDecodeError, yaml.YAMLError, KeyError,
            TypeError, ValueError) as error:
        raise ProfileError(f"A profil nem olvasható: {error}") from None
    return profile, is_draft(text)


def doc_name(profile):
    personal = profile["personalData"]
    return f"{personal['firstName']} {personal['lastName']} - MOON42"


def write_receipt(receipt_dir, profile_id, doc, draft, issues, sheet_row=None):
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
    receipt = {"documentId": doc.document_id, "name": doc.name, "url": doc.url,
               "parentFolderIds": doc.parent_folder_ids}
    if sheet_row is not None:
        receipt["sheetRow"] = sheet_row
    receipt.update({"draft": draft, "issues": issues, "previousDocuments": previous})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def generate(drive, docs, profile_id, profile, draft, *, template_id, folder_id,
             receipt_dir, sheet_email=None, sheet_mobile=None, sheet_row=None):
    """Create the filled document in `folder_id`. Return (doc, warnings);
    the caller writes the receipt of a successful run (it may add issues).
    On docfill.GenerationError the receipt of a left-over copy is written
    here, then the error is re-raised."""
    docfill = _docfill()
    personal = profile["personalData"]
    email, email_warning = logic.moon42_email(
        personal["firstName"], personal["lastName"], sheet_email)
    mobile = logic.pick_mobile(personal.get("contacts"), sheet_mobile)
    try:
        doc = docfill.generate_document(
            drive, docs, template_id=template_id, folder_id=folder_id,
            profile=profile, email=email, mobile=mobile)
    except docfill.GenerationError as error:
        if error.document_id:
            failed_doc = types.SimpleNamespace(
                document_id=error.document_id, name=doc_name(profile),
                url=error.url, parent_folder_ids=[folder_id])
            write_receipt(receipt_dir, profile_id, failed_doc, draft,
                          [f"Generálási hiba: {error}"], sheet_row)
        raise
    return doc, ([email_warning] if email_warning else []) + doc.warnings


def report_lines(doc, draft, warnings):
    lines = [doc.url + (" [DRAFT]" if draft else "")]
    lines += [f"      Figyelmeztetés: {w}" for w in warnings]
    lines += [f"      Tördelési probléma: {i}" for i in doc.layout_issues]
    return lines


def run(args):
    cfg = config_module.load_config(args.config, required=("templateId",))
    folder_id = args.folder_id.strip()
    if not folder_id:
        raise ValueError("Üres Drive-mappaazonosító.")
    profile, draft = load_profile(args.profile)
    credentials = auth.authenticate()
    drive, docs, _ = auth.build_services(credentials)
    profile_id = args.profile.stem
    try:
        doc, warnings = generate(drive, docs, profile_id, profile, draft,
                                 template_id=cfg["templateId"], folder_id=folder_id,
                                 receipt_dir=RECEIPT_DIR)
    except _docfill().GenerationError as error:
        print(f"Hiba: {error}" + (f" ({error.url})" if error.url else ""),
              file=sys.stderr)
        return 1
    ok = not doc.layout_issues
    print("Generált: " + "\n".join(report_lines(doc, draft, warnings)))
    try:
        write_receipt(RECEIPT_DIR, profile_id, doc, draft, warnings + doc.layout_issues)
    except OSError as error:
        print(f"      A nyugta nem írható: {error}")
        ok = False
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="a profil YAML-fájlja")
    parser.add_argument("folder_id", help="a cél Google Drive-mappa azonosítója")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="konfigurációs fájl (alapértelmezett: %(default)s)")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as error:  # config, profile, auth, API errors etc.
        print(f"Hiba: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
