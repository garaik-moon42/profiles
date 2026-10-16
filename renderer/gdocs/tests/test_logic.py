import unittest
from pathlib import Path

import yaml

from renderer.gdocs import logic

PROFILES_DIR = Path(__file__).resolve().parents[3] / "profiles"


def load_profiles():
    out = []
    for path in sorted(PROFILES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))["personalData"]
        out.append((path.stem, data["firstName"], data["lastName"]))
    return out


class DateTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(logic.format_date("2021/03"), "03/2021")
        self.assertEqual(logic.format_date("2021"), "2021")
        self.assertEqual(logic.format_date(None), "Present")

    def test_range(self):
        self.assertEqual(logic.format_date_range("2019/05", "2021/12"), "05/2019 – 12/2021")
        self.assertEqual(logic.format_date_range("2019/05", None), "05/2019 – Present")
        self.assertEqual(logic.format_date_range("2015", "2019"), "2015 – 2019")
        self.assertEqual(logic.format_date_range(None, "2019"), "2019")
        self.assertEqual(logic.format_date_range(None, None), "")

    def test_missing_end_differs_from_null_end(self):
        self.assertEqual(logic.format_date_range("2019/05"), "05/2019")
        self.assertEqual(logic.format_date_range("2019/05", logic.MISSING), "05/2019")
        self.assertEqual(logic.format_date_range("2019/05", None), "05/2019 – Present")
        self.assertEqual(logic.format_date_range(None, logic.MISSING), "")
        self.assertEqual(logic.format_date_range(None), "")

    def test_join_parts_drops_separators(self):
        self.assertEqual(logic.join_parts(["BSc", "ELTE"], ", "), "BSc, ELTE")
        self.assertEqual(logic.join_parts(["BSc", None], ", "), "BSc")
        self.assertEqual(logic.join_parts([None, "ELTE", ""], "\t"), "ELTE")
        self.assertEqual(logic.join_parts([None, None], " – "), "")


class EmailTests(unittest.TestCase):
    def test_derived(self):
        self.assertEqual(logic.moon42_email("Bence", "Berényi"),
                         ("bence.berenyi@moon42.com", None))

    def test_sheet_precedence(self):
        email, warning = logic.moon42_email("Bence", "Berényi", "  Bence.B@MOON42.com ")
        self.assertEqual(email, "Bence.B@MOON42.com")
        self.assertIsNone(warning)

    def test_foreign_sheet_email_ignored(self):
        email, _ = logic.moon42_email("Bence", "Berényi", "bence@gmail.com")
        self.assertEqual(email, "bence.berenyi@moon42.com")

    def test_multi_token_warning(self):
        email, warning = logic.moon42_email("Ádám Zoltán", "Sisák")
        self.assertEqual(email, "adam.sisak@moon42.com")
        self.assertIn("ellenőrizd a címet", warning)

    def test_dotted_and_multi_token_last_name(self):
        email, warning = logic.moon42_email("W.K.S. Miyuruhansi", "Sarathchandra")
        self.assertEqual(email, "wks.sarathchandra@moon42.com")
        self.assertTrue(warning)
        _, warning = logic.moon42_email("Anna", "Kiss Nagy")
        self.assertTrue(warning)
        _, warning = logic.moon42_email("Anna", "Kiss-Nagy")
        self.assertIsNone(warning)

    def test_sheet_email_no_warning(self):
        _, warning = logic.moon42_email("Ádám Zoltán", "Sisák", "a.s@moon42.com")
        self.assertIsNone(warning)


class MobileTests(unittest.TestCase):
    contacts = [{"type": "phone", "value": "111"}, {"type": "mobile", "value": "+36 70 513 0214"}]

    def test_mobile_wins(self):
        self.assertEqual(logic.pick_mobile(self.contacts, "999"), "+36 70 513 0214")

    def test_phone_fallback(self):
        self.assertEqual(logic.pick_mobile(self.contacts[:1], "999"), "111")

    def test_sheet_fallback_verbatim(self):
        self.assertEqual(logic.pick_mobile([{"type": "email", "value": "a@b.c"}], "06 30 1"), "06 30 1")
        self.assertEqual(logic.pick_mobile(None, "06 30 1"), "06 30 1")

    def test_none(self):
        self.assertIsNone(logic.pick_mobile([], "  "))
        self.assertIsNone(logic.pick_mobile([], None))


class EligibilityTests(unittest.TestCase):
    def test_status_variants(self):
        for status in ("in progress", " In Progress ", "IN PROGRESS"):
            self.assertTrue(logic.is_eligible(status, ""), status)
        for status in ("done", "in-progress", "", None, "in progress now"):
            self.assertFalse(logic.is_eligible(status, ""), status)

    def test_cell_emptiness(self):
        self.assertTrue(logic.is_eligible("in progress", None))
        self.assertTrue(logic.is_eligible("in progress", "  \n "))
        self.assertFalse(logic.is_eligible("in progress", "https://docs.google.com/x"))
        self.assertFalse(logic.is_eligible("in progress", "", profile_cell_has_chip=True))


# Sheet names (surname-first as in the sheet, and English order) per profile,
# plus rows intentionally without a YAML profile.
UNMATCHED = ["Hrubi", "Polena", "Robár", "Fekete", "Hrubi Tamás"]


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.profiles = load_profiles()

    def test_there_are_profiles(self):
        self.assertGreaterEqual(len(self.profiles), 14)

    def test_every_profile_matches_both_orders(self):
        for pid, first, last in self.profiles:
            for name in (f"{last} {first}", f"{first} {last}", f"{last} {first.split()[0]}",
                         f"  {last.upper()} {first.lower()} "):
                with self.subTest(profile=pid, name=name):
                    result = logic.match_rows([(1, name)], self.profiles)[1]
                    self.assertEqual((result.status, result.profile_id), ("matched", pid))

    def test_unmatched_rows_are_skipped(self):
        for name in UNMATCHED:
            with self.subTest(name=name):
                result = logic.match_rows([(1, name)], self.profiles)[1]
                self.assertEqual(result.status, "skipped")
                self.assertIsNone(result.profile_id)

    def test_empty_name(self):
        self.assertEqual(logic.match_rows([(1, " ")], self.profiles)[1].status, "skipped")

    def test_partial_overlap_warns_with_candidates(self):
        result = logic.match_rows([(1, "Nagy Péter")], self.profiles)[1]
        self.assertEqual(result.status, "skipped")
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("daniel-nagy", result.warnings[0])

    def test_multiple_matches_skipped(self):
        profiles = [("a", "Kiss", "Anna"), ("b", "Kiss", "Béla Anna")]
        result = logic.match_rows([(1, "Anna")], profiles)[1]
        self.assertEqual(result.status, "skipped")
        self.assertIn("a", result.reason)
        self.assertIn("b", result.reason)

    def test_two_rows_same_profile_are_errors(self):
        results = logic.match_rows([(3, "Berényi Bence"), (7, "Bence Berényi"), (9, "Hrubi")],
                                   self.profiles)
        self.assertEqual(results[3].status, "error")
        self.assertEqual(results[7].status, "error")
        self.assertEqual(results[9].status, "skipped")

    def test_tokenization(self):
        self.assertEqual(logic.name_tokens("W.K.S. Miyu-Ruhansi"), {"w", "k", "s", "miyu", "ruhansi"})
        self.assertEqual(logic.name_tokens("Szilágyi Gábor"), {"szilagyi", "gabor"})


# Real sheet "Name" column (as given by the lead).
SHEET_ZERO_MATCH = ["Hrubi András", "Péter Polena", "Robár Róbert", "Fekete Zoltán"]
SHEET_MATCHED = [
    "Chamith Udayanga", "Berényi Bence", "Demény Richárd", "Kelemen Kristóf",
    "Keszthelyi Attila", "Nagy Dániel", "Sisák Ádám", "Szalai Marcell",
    "Szilágyi Gábor", "Zsebe András", "Kalindu Don Sekarage", "Umar Firdausi",
    "Miyuruhansi Sarathchandra", "Hasitha Wijesooriya",
]
SHEET_NOT_IN_PROGRESS = [
    "Bátorligeti Ferenc", "Stomfai Zoltán", "Rónaszéki Péter", "Győry Marcell",
    "Miklós Kristyán", "Nagy Zsolt", "Kátai Gergely", "Gáspár Richárd",
    "Lágler Arnold", "Ravasz Gergő", "Miklós József", "Sipos Gábor", "Samu Bálint",
    "Molnár Krisztián", "Dudás Balázs", "Barabás Krisztián", "Beihuber Zoltán",
    "Norbert Süle", "Világos Zsolt", "Zoltán Murvai", "Péter Gergye", "Bálint Aracsi",
]


class SheetNamesTests(unittest.TestCase):
    def setUp(self):
        self.profiles = load_profiles()

    def run_all(self, names):
        return logic.match_rows(list(enumerate(names)), self.profiles)

    def test_in_progress_rows(self):
        results = self.run_all(SHEET_MATCHED + SHEET_ZERO_MATCH)
        matched = [results[i] for i in range(len(SHEET_MATCHED))]
        self.assertTrue(all(r.status == "matched" for r in matched))
        self.assertEqual(sorted(r.profile_id for r in matched),
                         sorted(pid for pid, _, _ in self.profiles))
        for i in range(len(SHEET_MATCHED), len(SHEET_MATCHED) + len(SHEET_ZERO_MATCH)):
            self.assertEqual(results[i].status, "skipped")
            self.assertEqual(results[i].reason, "Nincs illeszkedő profil.")

    def test_not_in_progress_rows_never_match_exactly_one(self):
        # even if such a row were eligible, it must not pair with a wrong profile
        for name, result in zip(SHEET_NOT_IN_PROGRESS, self.run_all(SHEET_NOT_IN_PROGRESS).values()):
            with self.subTest(name=name):
                self.assertEqual(result.status, "skipped")


class SkillSplitTests(unittest.TestCase):
    def test_cloud_devops_split(self):
        technical = {
            "devOpsAndCloud": ["Git", "Docker", "AWS", "AWS Lambda", "Azure DevOps", "GCP",
                               "Google Cloud Platform", "Terraform"],
            "toolsAndTechnologies": ["REST API"],
            "operatingSystems": ["Linux"],
            "developmentMethodologies": ["Scrum"],
            "specializedDomains": ["eSIM"],
            "testingAndQA": ["Jest"],
            "programmingLanguages": ["Go"],
        }
        split = logic.split_skills(technical)
        self.assertEqual(split["cloud"], ["AWS", "GCP", "Google Cloud Platform"])
        self.assertEqual(split["devops"], ["Git", "Docker", "AWS Lambda", "Azure DevOps", "Terraform"])
        self.assertEqual(split["other"], ["REST API", "Linux", "Scrum", "eSIM"])
        self.assertEqual(split["testing"], ["Jest"])
        self.assertEqual(split["programming"], ["Go"])
        self.assertEqual(split["databases"], [])
        self.assertEqual(split["ai"], [])

    def test_real_profile(self):
        data = yaml.safe_load((PROFILES_DIR / "bence-berenyi.yaml").read_text(encoding="utf-8"))
        split = logic.split_skills(data["skills"]["technical"])
        self.assertEqual(split["cloud"], ["AWS"])
        self.assertEqual(split["devops"], ["Git", "Docker", "Kubernetes", "CI/CD", "Terraform"])
        self.assertEqual(split["other"], [
            "REST API", "Cloud-native microservice architecture", "Responsive design",
            "eSIM services", "Classified ad portals", "Large-scale data migration"])


if __name__ == "__main__":
    unittest.main()
