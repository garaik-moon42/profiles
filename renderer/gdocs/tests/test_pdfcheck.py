import unittest
from pathlib import Path

from renderer.gdocs import pdfcheck
from renderer.gdocs.pdfcheck import RowSpec

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def word(text, x0, x1, top=100, bottom=112):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom}


ROW = RowSpec("Senior Developer / Acme Corp", ["Senior Developer", "Acme Corp", "01/2020 – Present"])


def good_words():
    # margin 36: center midpoint 297 = 36 + 261, right edge 589 = 36 + 553
    return [word("Senior", 36, 70), word("Developer", 74, 130),
            word("Acme", 270, 295, top=102, bottom=112), word("Corp", 299, 324, top=102, bottom=112),
            word("01/2020", 520, 560, top=102, bottom=112), word("–", 564, 570, top=102, bottom=112),
            word("Present", 574, 589.2, top=102, bottom=112)]


class AnalyzeRowsTests(unittest.TestCase):
    def test_clean_row_with_mixed_font_sizes(self):
        # tops differ (12 pt title vs 10 pt parts) but the baseline is shared
        issues, edges = pdfcheck.analyze_rows(good_words(), [ROW])
        self.assertEqual(issues, [])
        self.assertAlmostEqual(edges[0], 589.2)

    def test_wrapped_row(self):
        words = good_words()
        for w in words[-3:]:
            w["top"], w["bottom"] = 114, 126
        issues, edges = pdfcheck.analyze_rows(words, [ROW])
        self.assertEqual(len(issues), 1)
        self.assertIn("Senior Developer / Acme Corp", issues[0])
        self.assertIn("több sorba", issues[0])
        self.assertAlmostEqual(edges[0], 589.2)

    def test_touching_parts(self):
        words = good_words()
        words[2:4] = [word("Acme", 133, 160), word("Corp", 164, 190)]
        issues, _ = pdfcheck.analyze_rows(words, [ROW])
        self.assertEqual(len(issues), 1)
        self.assertIn("összeérnek", issues[0])

    def test_center_one_tab_too_few(self):
        words = good_words()
        # center part ended up on the 108 stop instead of 261
        words[2:4] = [word("Acme", 144, 169), word("Corp", 173, 198)]
        issues, _ = pdfcheck.analyze_rows(words, [ROW])
        self.assertEqual(len(issues), 1)
        self.assertIn("középső", issues[0])

    def test_center_pushed_right_with_gap(self):
        # long left part: the center part cannot be centered and follows it
        words = good_words()
        words[1] = word("Developer", 74, 250)
        words[2:4] = [word("Acme", 257, 300), word("Corp", 304, 350)]  # gap 7, midpoint +6.5
        self.assertEqual(pdfcheck.analyze_rows(words, [ROW])[0], [])

    def test_center_pushed_right_touching(self):
        words = good_words()
        words[1] = word("Developer", 74, 255)
        words[2:4] = [word("Acme", 257, 300), word("Corp", 304, 350)]  # gap 2
        issues, _ = pdfcheck.analyze_rows(words, [ROW])
        self.assertEqual(len(issues), 1)
        self.assertIn("összeérnek", issues[0])

    def test_row_without_left_part_is_still_aligned(self):
        # margin falls back to the page margin: center 28.35 + 261 = 289.35,
        # right 28.35 + 553 = 581.35
        words = [word("Acme", 277, 302), word("01/2020", 520, 560), word("–", 564, 570),
                 word("Present", 574, 575)]
        row = RowSpec("no role", [None, "Acme", "01/2020 – Present"])
        issues, _ = pdfcheck.analyze_rows(words, [row])
        self.assertEqual(len(issues), 1)
        self.assertIn("jobb szél", issues[0])
        words[-1]["x1"] = 581.0
        self.assertEqual(pdfcheck.analyze_rows(words, [row])[0], [])

    def test_row_without_text_is_skipped(self):
        issues, edges = pdfcheck.analyze_rows(good_words(), [RowSpec("empty", [None, " ", None]), ROW])
        self.assertEqual(issues, [])
        self.assertEqual(edges[0], None)

    def test_right_edge_misplaced(self):
        words = good_words()
        for w in words[-3:]:
            w["x0"] -= 40
            w["x1"] -= 40
        issues, _ = pdfcheck.analyze_rows(words, [ROW])
        self.assertEqual(len(issues), 1)
        self.assertIn("jobb szél", issues[0])

    def test_alignment_tolerance(self):
        words = good_words()
        for w in words[2:4]:
            w["x0"] += 2.5
            w["x1"] += 2.5
        self.assertEqual(pdfcheck.analyze_rows(words, [ROW])[0], [])

    def test_missing_row(self):
        issues, edges = pdfcheck.analyze_rows([word("x", 0, 5)], [ROW])
        self.assertIn("nem található", issues[0])
        self.assertEqual(edges, [None])

    def test_every_issue_asks_for_manual_decision(self):
        wrapped = good_words()
        wrapped[-1]["bottom"] += 20
        touching = good_words()
        touching[2:4] = [word("Acme", 133, 160), word("Corp", 164, 190)]
        misplaced = good_words()
        misplaced[2:4] = [word("Acme", 144, 169), word("Corp", 173, 198)]
        for words in ([word("x", 0, 5)], wrapped, touching, misplaced):
            for issue in pdfcheck.analyze_rows(words, [ROW])[0]:
                self.assertIn("kézi döntés kell", issue)

    def test_rows_in_order_and_optional_parts(self):
        words = good_words() + [word("Project", 36, 80, 200, 212), word("Budapest", 540, 589, 200, 212)]
        rows = [ROW, RowSpec("Project", ["Project", None, "Budapest"])]
        issues, edges = pdfcheck.analyze_rows(words, rows)
        self.assertEqual(issues, [])
        self.assertEqual(edges, [589.2, 589])

    def test_pages_do_not_merge(self):
        words = good_words()
        for w in words[-3:]:
            w["top"] += pdfcheck.PAGE_STRIDE
            w["bottom"] += pdfcheck.PAGE_STRIDE
        issues, _ = pdfcheck.analyze_rows(words, [ROW])
        self.assertIn("több sorba", issues[0])


@unittest.skipUnless((FIXTURES / "reference.pdf").exists() and (FIXTURES / "overlong.pdf").exists(),
                     "fixture PDFs (reference.pdf, overlong.pdf) not present")
class FixturePdfTests(unittest.TestCase):
    # AC-9: rows must be listed in tests/fixtures/rows.yaml once the fixtures exist.
    def test_fixtures(self):
        import yaml
        spec = yaml.safe_load((FIXTURES / "rows.yaml").read_text(encoding="utf-8"))
        rows = [RowSpec(r["label"], r["parts"]) for r in spec["rows"]]
        ok, _ = pdfcheck.check_pdf(FIXTURES / "reference.pdf", rows)
        self.assertEqual(ok, [])
        bad_rows = [RowSpec(r["label"], r["parts"]) for r in spec["overlongRows"]]
        bad, _ = pdfcheck.check_pdf(FIXTURES / "overlong.pdf", bad_rows)
        self.assertTrue(bad)


if __name__ == "__main__":
    unittest.main()
