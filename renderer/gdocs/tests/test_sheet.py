import unittest
from unittest import mock

from googleapiclient.errors import HttpError

from renderer.gdocs import sheet
from renderer.gdocs.tests.fakes import FakeSheets, cell, row

URL = "https://docs.google.com/document/d/abc/edit"


class ReadTest(unittest.TestCase):
    def test_rows_and_chip_detection(self):
        fake = FakeSheets([row("Anna Kiss", mobile="+36 1", email="a@x.hu"),
                           row("Bela Nagy", profile="Doc", chip=URL)])
        columns, rows = sheet.read_candidates(fake, "sid")
        self.assertEqual(columns["MOON42 Profile"], 5)
        self.assertEqual([r.number for r in rows], [2, 3])
        self.assertEqual((rows[0].name, rows[0].mobile, rows[0].email),
                         ("Anna Kiss", "+36 1", "a@x.hu"))
        self.assertFalse(rows[0].profile_has_chip)
        self.assertTrue(rows[1].profile_has_chip)

    def test_text_link_counts_as_link(self):
        fake = FakeSheets([row("Anna Kiss")])
        fake.grid[1][5] = {"formattedValue": "Doc", "textFormatRuns": [
            {"startIndex": 0, "format": {"link": {"uri": URL}}}]}
        _, rows = sheet.read_candidates(fake, "sid")
        self.assertTrue(rows[0].profile_has_chip)

    def test_missing_header(self):
        fake = FakeSheets([])
        fake.grid[0][5] = cell("Other")
        with self.assertRaises(sheet.SheetError) as ctx:
            sheet.read_candidates(fake, "sid")
        self.assertIn("MOON42 Profile", str(ctx.exception))


class WriteBackTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeSheets([row("Anna Kiss")])
        self.columns, rows = sheet.read_candidates(self.fake, "sid")
        self.row = rows[0]

    def write(self):
        return sheet.write_profile_link(self.fake, "sid", self.columns, self.row,
                                        "Anna Kiss - MOON42", URL)

    def test_writes_chip_only_to_profile_cell(self):
        self.assertEqual(self.write(), (True, None))
        update = self.fake.updates[0]["requests"][0]["updateCells"]
        self.assertEqual(update["start"], {"sheetId": 7, "rowIndex": 1, "columnIndex": 5})
        chip = update["rows"][0]["values"][0]["chipRuns"][0]
        self.assertEqual(chip["chip"]["richLinkProperties"]["uri"], URL)
        self.assertEqual(len(self.fake.updates), 1)

    def test_no_write_when_cell_filled(self):
        self.fake.grid[1][5] = cell("Other", chip="https://x/y")
        written, message = self.write()
        self.assertFalse(written)
        self.assertIn("megtelt", message)
        self.assertEqual(self.fake.updates, [])

    def test_no_write_when_name_changed(self):
        self.fake.grid[1][0] = cell("Someone Else")
        written, message = self.write()
        self.assertFalse(written)
        self.assertIn("más név", message)
        self.assertEqual(self.fake.updates, [])

    def test_no_write_when_column_inserted(self):
        for line in self.fake.grid:
            line.insert(0, cell("new"))
        written, message = self.write()
        self.assertFalse(written)
        self.assertIn("oszlopok", message)
        self.assertEqual(self.fake.updates, [])

    def test_hyperlink_fallback_when_chip_rejected(self):
        original = self.fake.batchUpdate
        calls = []

        def reject_first(spreadsheetId, body):
            calls.append(body)
            if len(calls) == 1:
                error = HttpError(mock.Mock(status=400, reason="x"), b"{}")
                return mock.Mock(execute=mock.Mock(side_effect=error))
            return original(spreadsheetId, body)

        self.fake.batchUpdate = reject_first
        self.assertEqual(self.write(), (True, "hiperhivatkozás"))
        value = self.fake.updates[0]["requests"][0]["updateCells"]["rows"][0]["values"][0]
        self.assertEqual(value["textFormatRuns"][0]["format"]["link"]["uri"], URL)


if __name__ == "__main__":
    unittest.main()
