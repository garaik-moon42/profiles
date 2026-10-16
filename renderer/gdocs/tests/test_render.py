import contextlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

from renderer.gdocs import render
from renderer.gdocs.tests.fakes import FakeSheets, row

VALID_CONFIG = "targetFolderId: f\ntemplateId: t\nspreadsheetId: s\n"
PROFILE = ("# yaml-language-server\n# DRAFT - pending\npersonalData:\n"
           "  firstName: {first}\n  lastName: {last}\n  contacts:\n"
           "    - type: mobile\n      value: '+36 1'\n")


class FakeGenerationError(Exception):
    def __init__(self, message, document_id=None, url=None):
        super().__init__(message)
        self.document_id, self.url = document_id, url


def fake_docfill(layout_issues=None, fail_for=None):
    calls = []

    def generate_document(drive, docs, *, template_id, folder_id, profile, email, mobile):
        personal = profile["personalData"]
        calls.append({"email": email, "mobile": mobile, "template": template_id})
        if fail_for == personal["lastName"]:
            raise FakeGenerationError("boom", "id9", "https://doc/9")
        doc_id = "doc-" + personal["lastName"]
        return types.SimpleNamespace(
            document_id=doc_id, name=f"{personal['firstName']} {personal['lastName']} - MOON42",
            url=f"https://doc/{doc_id}", parent_folder_ids=[folder_id],
            warnings=["w"], layout_issues=list(layout_issues or []))

    module = types.SimpleNamespace(generate_document=generate_document,
                                   GenerationError=FakeGenerationError)
    return module, calls


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.profiles = self.tmp / "profiles"
        self.profiles.mkdir()
        self.receipts = self.tmp / "receipts"
        self.receipts.mkdir()
        self.config = self.tmp / "config.yaml"
        self.config.write_text(VALID_CONFIG)
        self.add_profile("anna-kiss", "Anna", "Kiss")
        self.addCleanup(__import__("shutil").rmtree, self.tmp)

    def add_profile(self, pid, first, last):
        (self.profiles / f"{pid}.yaml").write_text(PROFILE.format(first=first, last=last))

    def run_main(self, args, sheets, docfill=None, authenticate=None):
        docfill = docfill or fake_docfill()[0]
        authenticate = authenticate or mock.Mock()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(render, "PROFILES_DIR", self.profiles))
            stack.enter_context(mock.patch.object(render, "RECEIPT_DIR", self.receipts))
            stack.enter_context(mock.patch.object(render, "_docfill", lambda: docfill))
            stack.enter_context(mock.patch.object(render.auth, "authenticate", authenticate))
            stack.enter_context(mock.patch.object(
                render.auth, "build_services", lambda c: ("drive", "docs", sheets)))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = render.main(["--config", str(self.config)] + args)
        return code, out.getvalue(), err.getvalue()

    def test_happy_path_writes_chip_and_receipt(self):
        sheets = FakeSheets([row("Kiss Anna", email="anna@gmail.com", mobile="+99")])
        docfill, calls = fake_docfill()
        code, out, _ = self.run_main([], sheets, docfill)
        self.assertEqual(code, 0)
        self.assertEqual(calls[0]["email"], "anna.kiss@moon42.com")
        self.assertEqual(calls[0]["mobile"], "+36 1")  # YAML wins
        self.assertEqual(len(sheets.updates), 1)
        receipt = json.loads((self.receipts / "anna-kiss.json").read_text())
        self.assertEqual((receipt["sheetRow"], receipt["draft"], receipt["previousDocuments"]),
                         (2, True, []))
        self.assertEqual(receipt["documentId"], "doc-Kiss")
        self.assertIn("https://doc/doc-Kiss", out)
        self.assertIn("[DRAFT]", out)

    def test_regeneration_appends_previous_document(self):
        (self.receipts / "anna-kiss.json").write_text(json.dumps(
            {"documentId": "old", "url": "https://old", "previousDocuments": [
                {"documentId": "older", "url": "https://older"}]}))
        self.run_main([], FakeSheets([row("Kiss Anna")]))
        receipt = json.loads((self.receipts / "anna-kiss.json").read_text())
        self.assertEqual([p["documentId"] for p in receipt["previousDocuments"]],
                         ["older", "old"])

    def test_filled_cell_changed_during_generation_no_write(self):
        sheets = FakeSheets([row("Kiss Anna")])
        docfill, _ = fake_docfill()
        inner = docfill.generate_document

        def generate_and_fill(*a, **k):
            result = inner(*a, **k)
            sheets.grid[1][5] = {"formattedValue": "typed by hand"}
            return result

        docfill.generate_document = generate_and_fill
        code, out, _ = self.run_main([], sheets, docfill)
        self.assertEqual(code, 1)
        self.assertEqual(sheets.updates, [])
        self.assertIn("megtelt", out)
        self.assertIn("https://doc/doc-Kiss", out)

    def test_name_changed_during_generation_no_write(self):
        sheets = FakeSheets([row("Kiss Anna")])
        docfill, _ = fake_docfill()
        inner = docfill.generate_document

        def generate_and_rename(*a, **k):
            result = inner(*a, **k)
            sheets.grid[1][0] = {"formattedValue": "Valaki Más"}
            return result

        docfill.generate_document = generate_and_rename
        code, out, _ = self.run_main([], sheets, docfill)
        self.assertEqual((code, sheets.updates), (1, []))
        self.assertIn("más név", out)

    def test_ineligible_rows_ignored_and_nothing_eligible_is_ok(self):
        sheets = FakeSheets([row("Kiss Anna", status="converted"),
                             row("Kiss Anna", profile="Doc", chip="https://x"),
                             row("Kiss Anna", profile="  ")])
        sheets.grid[3][1] = {"formattedValue": " In Progress "}
        docfill, calls = fake_docfill()
        code, _, _ = self.run_main([], sheets, docfill)
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)  # only the whitespace-only row (row 4)

    def test_unmatched_is_skipped_exit_0(self):
        code, out, _ = self.run_main([], FakeSheets([row("Nobody Here")]))
        self.assertEqual(code, 0)
        self.assertIn("Kihagyott", out)

    def test_duplicate_match_is_error(self):
        sheets = FakeSheets([row("Kiss Anna"), row("Anna Kiss")])
        docfill, calls = fake_docfill()
        code, out, _ = self.run_main([], sheets, docfill)
        self.assertEqual((code, calls, sheets.updates), (1, [], []))
        self.assertIn("Hibás", out)

    def test_layout_issue_exit_1_but_chip_written(self):
        sheets = FakeSheets([row("Kiss Anna")])
        code, out, _ = self.run_main([], sheets, fake_docfill(["sor törik, kézi döntés kell."])[0])
        self.assertEqual(code, 1)
        self.assertEqual(len(sheets.updates), 1)
        self.assertIn("kézi döntés kell", out)

    def test_candidate_failure_isolated(self):
        self.add_profile("bela-nagy", "Béla", "Nagy")
        sheets = FakeSheets([row("Kiss Anna"), row("Nagy Béla")])
        docfill, calls = fake_docfill(fail_for="Kiss")
        code, out, _ = self.run_main([], sheets, docfill)
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(sheets.updates), 1)  # only Béla written
        self.assertIn("https://doc/9", out)

    def test_broken_profiles_reported_exit_1(self):
        (self.profiles / "bad.yaml").write_text("personalData: [unclosed\n")
        (self.profiles / "nonstr.yaml").write_text(
            "personalData:\n  firstName: 5\n  lastName: X\n")
        (self.profiles / "binary.yaml").write_bytes(b"\xff\xfe\x00")
        for args in ([], ["--dry-run"]):
            code, out, _ = self.run_main(args, FakeSheets([]))
            self.assertEqual(code, 1)
            for pid in ("bad", "nonstr", "binary"):
                self.assertIn(pid, out)

    def test_failed_doc_gets_receipt(self):
        docfill, _ = fake_docfill(fail_for="Kiss")
        code, _, _ = self.run_main([], FakeSheets([row("Kiss Anna")]), docfill)
        receipt = json.loads((self.receipts / "anna-kiss.json").read_text())
        self.assertEqual((code, receipt["documentId"]), (1, "id9"))
        self.assertIn("boom", receipt["issues"][0])

    def test_draft_only_in_leading_comments(self):
        self.assertTrue(render.is_draft("# a\n# DRAFT x\nfoo: 1\n"))
        self.assertFalse(render.is_draft("# a\nfoo: 1\n# DRAFT x\n"))

    def test_dry_run_writes_nothing(self):
        sheets = FakeSheets([row("Kiss Anna"), row("Nobody Here")])
        docfill, calls = fake_docfill()
        code, out, _ = self.run_main(["--dry-run"], sheets, docfill)
        self.assertEqual((code, calls, sheets.updates), (0, [], []))
        self.assertEqual(list(self.receipts.iterdir()), [])
        self.assertIn("Anna Kiss - MOON42 [DRAFT]", out)
        self.assertIn("kihagyva", out)

    def test_bad_config_exits_before_any_api_call(self):
        for text in ("targetFolderId: f\nspreadsheetId: s\n",
                     "targetFolderId: f\ntemplateId: t\nspreadsheetId:\n"):
            self.config.write_text(text)
            authenticate = mock.Mock()
            code, _, err = self.run_main([], FakeSheets([]), authenticate=authenticate)
            self.assertEqual(code, 1)
            self.assertTrue(err.startswith("Hiba:"))
            authenticate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
