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
        c, r = layout.row_tabs(left, center, date, fake_width)
        self.assertEqual(c, 4)
        # center ends at 261 + 17.5 = 278.5 -> only the right stop (553) remains
        self.assertEqual(r, 1)

    def test_left_past_a_stop_uses_fewer_tabs(self):
        left = [Run("A" * 10, 12, True)]  # 66 pt: stops 72, 108, 261 -> 3
        c, r = layout.row_tabs(left, [Run("X", 10)], [Run("d", 10)], fake_width)
        self.assertEqual(c, 3)

    def test_left_exactly_on_stop_goes_to_next(self):
        left = [Run("A" * 14, 10), Run("AA", 2)]  # 70 + 2 = 72 pt: exactly on the 72 stop
        self.assertEqual(layout.runs_width(left, fake_width), 72)
        c, _ = layout.row_tabs(left, [Run("X", 10)], None, fake_width)
        self.assertEqual(c, 2)  # 108, 261 (the 72 stop is not reused)

    def test_project_row_without_center(self):
        left = [Run("Project", 12, True)]  # 46.2 pt
        c, r = layout.row_tabs(left, None, [Run("Budapest", 10)], fake_width)
        self.assertIsNone(c)
        self.assertEqual(r, 4)  # 72, 108, 261, 553

    def test_long_left_past_center_stop(self):
        left = [Run("A" * 60, 12, True)]  # 396 pt: only the right stop remains
        _, r = layout.row_tabs(left, None, [Run("d", 10)], fake_width)
        self.assertEqual(r, 1)

    def test_past_center_stop_center_part_lands_on_right_stop(self):
        left = [Run("A" * 40, 12, True)]  # 264 pt, past the center stop
        center = [Run("B" * 10, 10)]  # 50 pt
        date = [Run("d", 10)]
        c, r = layout.row_tabs(left, center, date, fake_width)
        self.assertEqual(c, 1)  # the tab goes to the right stop (553), text ends there
        self.assertEqual(r, 1)  # nothing left beyond 553
        # same layout without center: the right part simply takes the next stop
        self.assertEqual(layout.row_tabs(left, None, date, fake_width), (None, 1))

    def test_no_parts(self):
        self.assertEqual(layout.row_tabs([Run("x")], None, None, fake_width), (None, None))

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
