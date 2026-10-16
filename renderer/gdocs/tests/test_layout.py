import unittest

from renderer.gdocs import layout
from renderer.gdocs.layout import Run


def fake_width(text, size, bold):
    # 0.5 em per character, bold 10% wider: easy to compute by hand.
    return len(text) * size * 0.5 * (1.1 if bold else 1.0)


class RowTabsTests(unittest.TestCase):
    def test_short_left_reaches_center_via_all_stops(self):
        # left 5 chars * 12 * .5 * 1.1 = 33 pt < 36: stops 36, 72, 108, 261 -> 4 tabs.
        left = [Run("Short", 12, True)]
        center = [Run("Company", 10)]  # 35 pt: starts at 243.5, fits
        date = [Run("01/2020 – Present", 10, True)]
        c, r, _ = layout.row_tabs(left, center, date, fake_width)
        self.assertEqual(c, 4)
        # center ends at 261 + 17.5 = 278.5 -> only the right stop (553) remains
        self.assertEqual(r, 1)

    def test_left_past_a_stop_uses_fewer_tabs(self):
        left = [Run("A" * 10, 12, True)]  # 66 pt: stops 72, 108, 261 -> 3
        c, r, _ = layout.row_tabs(left, [Run("X", 10)], [Run("d", 10)], fake_width)
        self.assertEqual(c, 3)

    def test_width_at_or_near_a_stop_still_takes_it(self):
        # Docs: "Founder/CTO" (12 pt bold) renders 71.994 pt wide and its tab
        # goes to the 72 stop; the metric may land a hair beyond it
        for left_width in (71.9, 71.95, 72.0, 72.05, 72.09):
            widths = {"L": left_width, "X": 5, " ": 3}
            c, _, _ = layout.row_tabs([Run("L")], [Run("X")], None, lambda t, size, b: widths[t])
            self.assertEqual(c, 3, left_width)  # 72, 108, 261

    def test_width_clearly_past_a_stop_skips_it(self):
        c, _, _ = layout.row_tabs([Run("A" * 12, 12), Run("x", 0.4)], [Run("X", 10)], None, fake_width)
        self.assertEqual(c, 2)  # 72.2 pt: 108, 261

    def test_kerning_matches_docs(self):
        try:
            width = layout.roboto_width("Founder/CTO", 12, True)
        except OSError as e:
            self.skipTest(f"font not available: {e}")
        self.assertAlmostEqual(width, 71.994, delta=0.05)  # measured in the Docs PDF export
        self.assertLess(layout.roboto_width("CT", 12, True),
                        layout.roboto_width("C", 12, True) + layout.roboto_width("T", 12, True))

    def test_project_row_without_center(self):
        left = [Run("Project", 12, True)]  # 46.2 pt
        c, r, _ = layout.row_tabs(left, None, [Run("Budapest", 10)], fake_width)
        self.assertIsNone(c)
        self.assertEqual(r, 4)  # 72, 108, 261, 553

    def test_long_left_past_center_stop(self):
        left = [Run("A" * 60, 12, True)]  # 396 pt: only the right stop remains
        _, r, _ = layout.row_tabs(left, None, [Run("d", 10)], fake_width)
        self.assertEqual(r, 1)

    def test_past_center_stop_center_part_lands_on_right_stop(self):
        left = [Run("A" * 40, 12, True)]  # 264 pt, past the center stop
        center = [Run("B" * 10, 10)]  # 50 pt
        date = [Run("d", 10)]
        c, r, _ = layout.row_tabs(left, center, date, fake_width)
        self.assertEqual(c, 1)  # the tab goes to the right stop (553), text ends there
        self.assertEqual(r, 1)  # nothing left beyond 553
        # same layout without center: the right part simply takes the next stop
        self.assertEqual(layout.row_tabs(left, None, date, fake_width), (None, 1, 0))

    def test_center_that_fits_needs_no_padding(self):
        # left 33 pt, center 35 pt starts at 243.5: far enough from the left part
        self.assertEqual(layout.row_tabs([Run("Short", 12, True)], [Run("Company", 10)],
                                         None, fake_width)[2], 0)

    def test_padding_when_center_cannot_be_centered(self):
        # left 198 pt (12 pt bold, space 6.6 pt); center 200 pt would start at
        # 161, so it follows the tab directly: one space gives a 6.6 pt gap
        left = [Run("A" * 30, 12, True)]
        center = [Run("B" * 40, 10)]
        c, r, spaces = layout.row_tabs(left, center, [Run("d", 10)], fake_width)
        self.assertEqual((c, spaces), (1, 1))
        self.assertEqual(r, 1)

    def test_padding_when_centered_text_comes_too_close(self):
        # left 30 * 5 = 150 pt (10 pt regular, space 5 pt); center 216 pt is
        # centered at 153..369, only 3 pt from the left part. Spaces widen the
        # centered block: 1 space -> text at 155.5 (5.5 pt), 2 -> 160 (10 pt)
        left = [Run("A" * 30, 10)]
        center = [Run("B" * 43, 10), Run("x", 2)]  # 215 + 1 = 216 pt
        _, _, spaces = layout.row_tabs(left, center, None, fake_width)
        self.assertEqual(spaces, 2)

    def test_no_parts(self):
        self.assertEqual(layout.row_tabs([Run("x")], None, None, fake_width), (None, None, 0))

    def test_runs_width_sums_sizes_and_weights(self):
        runs = [Run("ab", 12, True), Run("cd", 10)]
        self.assertAlmostEqual(layout.runs_width(runs, fake_width), 13.2 + 10)


class FontTests(unittest.TestCase):
    def test_pinned_fonts_declared(self):
        for bold in (False, True):
            name, url, sha = layout.FONTS[bold]
            self.assertTrue(url.startswith("https://") and "v2.138" in url)
            self.assertEqual(len(sha), 64)

    def test_font_metrics_sanity(self):
        # Needs the cached font; fetch_font downloads it on first use.
        try:
            w = layout.roboto_width("Hello", 10, False)
            wb = layout.roboto_width("Hello", 10, True)
        except OSError as e:
            self.skipTest(f"font not available: {e}")
        self.assertTrue(15 < w < 40)
        self.assertGreater(wb, w)
        self.assertAlmostEqual(layout.roboto_width("Hello", 20, False), 2 * w)


if __name__ == "__main__":
    unittest.main()
