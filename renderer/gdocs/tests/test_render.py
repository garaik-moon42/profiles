import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from renderer.gdocs import render
from renderer.gdocs.tests.test_tesla_candidates import PROFILE, fake_docfill

CONFIG = "templateId: t\n"


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp)
        self.receipts = self.tmp / "receipts"
        self.config = self.tmp / "config.yaml"
        self.config.write_text(CONFIG)
        self.profile = self.tmp / "anna-kiss.yaml"
        self.profile.write_text(PROFILE.format(first="Anna", last="Kiss"))

    def run_main(self, args, docfill=None, authenticate=None):
        docfill = docfill or fake_docfill()[0]
        authenticate = authenticate or mock.Mock()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(render, "RECEIPT_DIR", self.receipts))
            stack.enter_context(mock.patch.object(render, "_docfill", lambda: docfill))
            stack.enter_context(mock.patch.object(render.auth, "authenticate", authenticate))
            stack.enter_context(mock.patch.object(
                render.auth, "build_services", lambda c: ("drive", "docs", "sheets")))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = render.main(args + ["--config", str(self.config)])
        return code, out.getvalue(), err.getvalue()

    def receipt(self):
        return json.loads((self.receipts / "anna-kiss.json").read_text())

    def test_generates_into_given_folder_with_receipt(self):
        docfill, calls = fake_docfill()
        code, out, _ = self.run_main([str(self.profile), " folder-1 "], docfill)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [{"email": "anna.kiss@moon42.com", "mobile": "+36 1",
                                  "template": "t"}])
        receipt = self.receipt()
        self.assertEqual((receipt["documentId"], receipt["parentFolderIds"], receipt["draft"]),
                         ("doc-Kiss", ["folder-1"], True))
        self.assertNotIn("sheetRow", receipt)
        self.assertEqual(receipt["issues"], ["w"])
        self.assertIn("https://doc/doc-Kiss [DRAFT]", out)
        self.assertIn("Figyelmeztetés: w", out)

    def test_regeneration_appends_previous_document(self):
        self.receipts.mkdir()
        (self.receipts / "anna-kiss.json").write_text(json.dumps(
            {"documentId": "old", "url": "https://old", "sheetRow": 2}))
        self.run_main([str(self.profile), "f"])
        self.assertEqual(self.receipt()["previousDocuments"],
                         [{"documentId": "old", "url": "https://old"}])

    def test_layout_issue_exit_1(self):
        code, out, _ = self.run_main([str(self.profile), "f"],
                                     fake_docfill(["sor törik, kézi döntés kell."])[0])
        self.assertEqual(code, 1)
        self.assertIn("Tördelési probléma: sor törik", out)

    def test_generation_failure_exit_1_with_receipt(self):
        code, _, err = self.run_main([str(self.profile), "f"], fake_docfill(fail_for="Kiss")[0])
        self.assertEqual(code, 1)
        self.assertIn("boom (https://doc/9)", err)
        self.assertEqual(self.receipt()["documentId"], "id9")

    def test_bad_input_exits_before_any_api_call(self):
        broken = self.tmp / "broken.yaml"
        broken.write_text("personalData:\n  firstName: 5\n  lastName: X\n")
        cases = [([str(broken), "f"], CONFIG), ([str(self.tmp / "none.yaml"), "f"], CONFIG),
                 ([str(self.profile), " "], CONFIG), ([str(self.profile), "f"], "templateId:\n")]
        for args, config in cases:
            with self.subTest(args=args, config=config):
                self.config.write_text(config)
                authenticate = mock.Mock()
                code, _, err = self.run_main(args, authenticate=authenticate)
                self.assertEqual(code, 1)
                self.assertTrue(err.startswith("Hiba:"))
                authenticate.assert_not_called()

    def test_draft_only_in_leading_comments(self):
        self.assertTrue(render.is_draft("# a\n# DRAFT x\nfoo: 1\n"))
        self.assertFalse(render.is_draft("# a\nfoo: 1\n# DRAFT x\n"))


if __name__ == "__main__":
    unittest.main()
