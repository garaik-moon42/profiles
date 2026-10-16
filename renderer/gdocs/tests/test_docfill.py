import tempfile
import unittest
from pathlib import Path
from unittest import mock

from renderer.gdocs import docfill
from renderer.gdocs.docfill import Para, Region


def width(text, size, bold):
    return len(text) * size * 0.5


FONTS = {key: (12 if key == "pos.title" else 10, key.endswith(("title", "company", "date", "dash")))
         for key in ("pos.title", "pos.company", "pos.date", "pos.dash", "proj.name", "proj.location")}


def profile(**overrides):
    base = {
        "personalData": {"firstName": "Anna", "lastName": "Kovács", "title": "Engineer",
                         "introduction": "I build things.",
                         "languages": ["Hungarian (native)", "English"]},
        "skills": {"technical": {"programmingLanguages": ["Go"],
                                 "frameworksAndLibraries": ["React"],
                                 "devOpsAndCloud": ["Docker", "AWS"]},
                   "soft": ["Mentoring"]},
        "experience": [{"role": "Dev", "company": "Acme Corporation Ltd", "companyShortName": "Acme",
                        "start": "2020/01", "end": None,
                        "projects": [{"name": "Shop", "location": "Budapest",
                                      "responsibilities": ["Built it."], "techStack": ["Go", "React"]},
                                     {"name": "Tool", "responsibilities": ["Fixed it."]}]}],
        "education": [{"name": "BSc", "institution": "BME", "start": "2010", "end": "2014"}],
        "certificates": [],
        "interests": [],
    }
    base.update(overrides)
    return base


def plan(prof, mobile="+36 1", email="anna.kovacs@moon42.com"):
    return docfill.content_plan(prof, email, mobile, FONTS, width)


def texts(paras):
    return ["".join(t for t, _ in p.runs) for p in paras]


class DateRunsTests(unittest.TestCase):
    def test_position_range_has_separate_dash_run(self):
        self.assertEqual(docfill.date_runs("01/2020 – Present", "d", "x", "d"),
                         [("01/2020 ", "d"), ("– ", "x"), ("Present", "d")])

    def test_education_range_dash_and_end_share_a_run(self):
        self.assertEqual(docfill.date_runs("2010 – 2014", "d", "x", "x"),
                         [("2010 ", "d"), ("– 2014", "x")])

    def test_single_date_and_empty(self):
        self.assertEqual(docfill.date_runs("2010", "d", "x", "x"), [("2010", "d")])
        self.assertEqual(docfill.date_runs("", "d", "x", "x"), [])


class TabbedRowTests(unittest.TestCase):
    def test_tabs_from_layout(self):
        runs = docfill.tabbed_row([("Dev", "pos.title")], [("Acme", "pos.company")],
                                  [("01/2020", "pos.date")], FONTS, width)
        # "Dev" is 18 pt wide: 36, 72, 108 and the center stop 261 lie ahead
        self.assertEqual(runs, [("Dev", "pos.title"), ("\t\t\t\t", "pos.title"),
                                ("Acme", "pos.company"), ("\t", "pos.company"),
                                ("01/2020", "pos.date")])

    def test_padding_spaces_follow_the_center_tab(self):
        # left 180 pt, center 200 pt cannot be centered: one 6 pt space as gap
        runs = docfill.tabbed_row([("A" * 30, "pos.title")], [("B" * 40, "pos.company")], [],
                                  FONTS, width)
        self.assertEqual(runs[1], ("\t ", "pos.title"))

    def test_missing_center(self):
        runs = docfill.tabbed_row([("Shop", "proj.name")], [], [("Budapest", "proj.location")],
                                  FONTS, width)
        self.assertEqual([t for t, _ in runs], ["Shop", "\t\t\t\t\t", "Budapest"])

    def test_left_only(self):
        self.assertEqual(docfill.tabbed_row([("Tool", "proj.name")], [], [], FONTS, width),
                         [("Tool", "proj.name")])


class ContentPlanTests(unittest.TestCase):
    def test_intro_fallback_warns(self):
        result, _, warnings = plan(profile())
        self.assertEqual(texts(result["intro"]), ["I build things."])
        self.assertEqual(len(warnings), 1)

    def test_third_person_intro(self):
        prof = profile()
        prof["personalData"]["introductionThirdPerson"] = "Anna builds\nthings."
        result, _, warnings = plan(prof)
        self.assertEqual(texts(result["intro"]), ["Anna builds things."])
        self.assertEqual(warnings, [])

    def test_skill_rows(self):
        result, _, _ = plan(profile())
        self.assertEqual(texts(result["skills"]), [
            "Languages\tHungarian (native), English", "Programming\tGo",
            "Frameworks\tReact", "DevOps / IaC\tDocker", "Cloud\tAWS", "Soft skills\tMentoring"])

    def test_work_paragraphs_and_rows(self):
        result, rows, _ = plan(profile())
        work = result["work"]
        self.assertEqual([p.kind for p in work], [None, None, "bullet", "bullet", None, "bullet"])
        self.assertEqual(texts(work)[0].replace("\t", " ").split(), ["Dev", "Acme", "01/2020", "–", "Present"])
        self.assertEqual(texts(work)[3], "Tech stack: Go, React")
        self.assertEqual(texts(work)[4], "Tool")
        self.assertEqual([r.parts for r in rows], [["Dev", "Acme", "01/2020 – Present"],
                                                   ["Shop", None, "Budapest"],
                                                   ["Tool", None, None]])

    def test_education_missing_parts_drop_separators(self):
        prof = profile(education=[{"name": "BSc", "start": "2010"}, {"name": "MSc", "institution": "ELTE"}])
        result, _, _ = plan(prof)
        self.assertEqual(texts(result["education"]), ["BSc\t2010", "MSc, ELTE"])
        prof = profile(education=[{"name": "BSc", "institution": "BME", "start": "2010/09", "end": None}])
        self.assertEqual(texts(plan(prof)[0]["education"]), ["BSc, BME\t09/2010 – Present"])

    def test_certificates_and_interests(self):
        prof = profile(certificates=[{"name": "CKA", "organization": "LF", "date": "2021/05"}],
                       interests=[{"name": "Chess", "description": "Plays online."}, {"name": "Running"}])
        result, _, _ = plan(prof)
        self.assertEqual(texts(result["certificates"]), ["CKA, LF\t05/2021"])
        self.assertEqual(result["interests"][0].runs,
                         [("Chess:", "interest.name"), (" Plays online.", "interest.detail")])
        self.assertEqual(texts(result["interests"]), ["Chess: Plays online.", "Running"])

    def test_row_without_text_is_left_out(self):
        prof = profile(experience=[{"projects": [{"responsibilities": ["Did it."]}]},
                                   {"company": "Acme", "start": "2020"}])
        result, rows, _ = plan(prof)
        self.assertEqual([r.parts for r in rows], [[None, "Acme", "2020"]])
        self.assertEqual(texts(result["work"])[0], "Did it.")

    def test_contact_without_mobile(self):
        result, _, _ = plan(profile(), mobile=None)
        self.assertEqual(texts(result["contact"]), ["Email\tanna.kovacs@moon42.com"])


def region_text(requests):
    return [r["insertText"]["text"] for r in requests if "insertText" in r]


class RegionRequestsTests(unittest.TestCase):
    STYLES = {"a": {"bold": True}, "b": {}}

    def test_paragraphs_replace_the_region(self):
        region = Region(10, 30, [Para([("Ab", "a"), ("\tc", "b")]), Para([("d", "b")], "bullet")])
        requests = docfill.region_requests(region, self.STYLES, {})
        self.assertEqual(requests[0], {"insertText": {"location": {"index": 10}, "text": "Ab\tc\nd\n"}})
        styled = [(r["updateTextStyle"]["range"]["startIndex"], r["updateTextStyle"]["range"]["endIndex"])
                  for r in requests if "updateTextStyle" in r]
        # the paragraph mark takes the last run's style
        self.assertEqual(styled, [(10, 12), (12, 14), (14, 15), (15, 16), (16, 17)])
        self.assertIn({"createParagraphBullets": {"range": {"startIndex": 15, "endIndex": 17},
                                                  "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}}, requests)
        self.assertEqual(requests[-1], {"deleteContentRange": {"range": {"startIndex": 17, "endIndex": 37}}})

    def test_indices_count_utf16_code_units(self):
        # U+1F600 is two UTF-16 code units in the Docs API
        region = Region(10, 12, [Para([("a\U0001F600", "a"), ("b", "b")])])
        requests = docfill.region_requests(region, self.STYLES, {})
        styled = [(r["updateTextStyle"]["range"]["startIndex"], r["updateTextStyle"]["range"]["endIndex"])
                  for r in requests if "updateTextStyle" in r]
        self.assertEqual(styled, [(10, 13), (13, 14), (14, 15)])
        self.assertEqual(requests[-1], {"deleteContentRange": {"range": {"startIndex": 15, "endIndex": 17}}})

    def test_inline_keeps_the_paragraph_mark(self):
        requests = docfill.region_requests(Region(5, 9, [Para([("Name", "a")])], inline=True),
                                           self.STYLES, {})
        self.assertEqual(region_text(requests), ["Name"])
        self.assertEqual(requests[-1], {"deleteContentRange": {"range": {"startIndex": 9, "endIndex": 13}}})

    def test_empty_region_only_deletes(self):
        self.assertEqual(docfill.region_requests(Region(5, 9), self.STYLES, {}),
                         [{"deleteContentRange": {"range": {"startIndex": 5, "endIndex": 9}}}])

    def test_heading_conversion(self):
        requests = docfill.region_requests(Region(5, 9, [Para([("Certificates", "b")], "heading")]),
                                           self.STYLES, {"namedStyleType": "HEADING_2"})
        self.assertIn({"deleteParagraphBullets": {"range": {"startIndex": 5, "endIndex": 18}}}, requests)
        self.assertIn({"updateParagraphStyle": {"range": {"startIndex": 5, "endIndex": 18},
                                                "paragraphStyle": {"namedStyleType": "HEADING_2"},
                                                "fields": "*"}}, requests)


# --- A synthetic copy of the template -----------------------------------------

def template_document():
    """Minimal document with the template's placeholder texts and structure."""
    index = 1
    cells, body = [], []

    def paragraph(runs, style="NORMAL_TEXT"):
        nonlocal index
        elements = []
        for text, text_style in runs:
            elements.append({"startIndex": index, "endIndex": index + len(text),
                             "textRun": {"content": text, "textStyle": text_style}})
            index += len(text)
        return {"startIndex": elements[0]["startIndex"], "endIndex": index,
                "paragraph": {"elements": elements, "paragraphStyle": {"namedStyleType": style}}}

    bold, plain, yellow = {"bold": True}, {}, {"backgroundColor": {"color": {"rgbColor": {"red": 1, "green": 1}}}}
    for text in ("Tivadar Template\n", "Senior .Net Developer\n"):
        cells.append(paragraph([(text, {"fontSize": {"magnitude": 24, "unit": "PT"}})]))
    body.append({"table": {"tableRows": [{"tableCells": [{"content": [c]} for c in cells]}]}})
    body.append(paragraph([("TODO: Short brief introduction\n", plain)]))
    body.append(paragraph([("Skills\n", plain)], "HEADING_2"))
    body.append(paragraph([("Languages", bold), ("\tEnglish (fluent)\n", plain)]))
    body.append(paragraph([("Libraries", bold), ("\t\n", plain)]))
    body.append(paragraph([("Soft skills", bold), ("\t", plain), ("TODO\n", yellow)]))
    body.append(paragraph([("Work Experience\n", plain)], "HEADING_2"))
    body.append(paragraph([("Position\t\t\t", {"bold": True, "fontSize": {"magnitude": 12, "unit": "PT"}}),
                           ("Company #1 Name", bold), ("\t", plain), ("mm/yyyy ", bold),
                           ("– ", {"bold": True, "weightedFontFamily": {"fontFamily": "Arial"}}),
                           ("Present\n", bold)]))
    body.append(paragraph([("Project #1 Name\t\t", plain), ("Location\n", plain)]))
    body.append(paragraph([("Description\n", plain)]))
    body.append(paragraph([("Tech stack: \n", plain)]))
    body.append(paragraph([("E", plain), ("ducation\n", plain)], "HEADING_2"))
    body.append(paragraph([("Degree, ", bold), ("Institute\t", plain), ("mm/yyyy ", bold),
                           ("– mm/yyyy\n", bold)]))
    body.append(paragraph([("Personal Interests\n", plain)], "HEADING_2"))
    body.append(paragraph([("Activity:", yellow), (" Why do you enjoy it?\n", yellow)]))
    body.append(paragraph([("Contact Information\n", plain)], "HEADING_2"))
    body.append(paragraph([("Email", bold), ("\ttivadar.template@moon42.com\n", plain)]))
    body.append(paragraph([("Mobile", bold), ("\t+36301234567\n", plain)]))
    body.append(paragraph([("\n", plain)]))
    return {"body": {"content": body}}


def apply(document, requests):
    """Apply insertText/deleteContentRange to the document's plain text."""
    text = "\0"  # index 0 (section break)
    for element in document["body"]["content"]:
        parts = [element] if "paragraph" in element else [
            p for row in element["table"]["tableRows"] for c in row["tableCells"] for p in c["content"]]
        for part in parts:
            text += docfill._text(part)
    for request in requests:
        if "insertText" in request:
            at = request["insertText"]["location"]["index"]
            text = text[:at] + request["insertText"]["text"] + text[at:]
        elif "deleteContentRange" in request:
            rng = request["deleteContentRange"]["range"]
            text = text[:rng["startIndex"]] + text[rng["endIndex"]:]
    return text[1:]


class BuildRequestsTests(unittest.TestCase):
    def test_fills_the_template(self):
        prof = profile(certificates=[{"name": "CKA", "organization": "LF", "date": "2021"}],
                       interests=[{"name": "Chess", "description": "Plays online."}])
        requests, rows, _ = docfill.build_requests(template_document(), prof,
                                                   "anna.kovacs@moon42.com", None, width)
        text = apply(template_document(), requests)
        lines = [" ".join(line.split()) for line in text.split("\n")]
        self.assertEqual(lines, [
            "Anna Kovács", "Engineer", "I build things.", "Skills",
            "Languages Hungarian (native), English", "Programming Go", "Frameworks React",
            "DevOps / IaC Docker", "Cloud AWS", "Soft skills Mentoring", "Work Experience",
            "Dev Acme 01/2020 – Present", "Shop Budapest", "Built it.", "Tech stack: Go, React",
            "Tool", "Fixed it.", "Education", "BSc, BME 2010 – 2014", "Certificates", "CKA, LF 2021",
            "Personal Interests", "Chess: Plays online.", "Contact Information",
            "Email anna.kovacs@moon42.com", "", ""])
        self.assertEqual(len(rows), 3)
        styles = [r["updateTextStyle"]["textStyle"] for r in requests if "updateTextStyle" in r]
        self.assertFalse(any("backgroundColor" in s for s in styles))

    def test_empty_sections_are_deleted_and_certificates_take_the_education_heading(self):
        prof = profile(education=[], certificates=[{"name": "CKA", "organization": "LF", "date": "2021"}],
                       experience=[])
        text = apply(template_document(),
                     docfill.build_requests(template_document(), prof, "a@moon42.com", "+36", width)[0])
        lines = [" ".join(line.split()) for line in text.split("\n")]
        self.assertNotIn("Work Experience", lines)
        self.assertNotIn("Personal Interests", lines)
        self.assertNotIn("Education", lines)
        self.assertEqual(lines[lines.index("Certificates") + 1], "CKA, LF 2021")
        self.assertIn("Mobile +36", lines)

    def test_unexpected_template(self):
        document = template_document()
        document["body"]["content"].pop(1)  # the intro paragraph
        with self.assertRaises(docfill.GenerationError):
            docfill.build_requests(document, profile(), "a@moon42.com", None, width)


# --- generate_document with fake services -------------------------------------

class Request:
    def __init__(self, calls, name, kwargs, result):
        calls.append((name, kwargs))
        self.result = result

    def execute(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeApi:
    """drive.files() / docs.documents(): every method records its call and
    returns the configured result (an exception is raised on execute)."""

    def __init__(self, results):
        self.calls, self.results = [], results

    def files(self):
        return self

    documents = files

    def __getattr__(self, name):
        return lambda **kwargs: Request(self.calls, name, kwargs, self.results[name])


class GenerateDocumentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patches = [mock.patch.object(docfill, "PDF_DIR", Path(directory.name)),
                   mock.patch.object(docfill.layout, "roboto_width", width)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        document = template_document()
        document["revisionId"] = "rev-1"
        self.drive = FakeApi({"copy": {"id": "doc-1", "webViewLink": "https://doc/1", "parents": ["folder"]},
                              "export": b"%PDF"})
        self.docs = FakeApi({"get": document, "batchUpdate": {}})

    def generate(self):
        return docfill.generate_document(self.drive, self.docs, template_id="tpl", folder_id="folder",
                                         profile=profile(), email="anna.kovacs@moon42.com", mobile=None)

    def test_template_only_copied_and_one_guarded_batch(self):
        with mock.patch.object(docfill.pdfcheck, "check_pdf", return_value=([], [])):
            result = self.generate()
        self.assertEqual((result.document_id, result.url, result.parent_folder_ids, result.layout_issues),
                         ("doc-1", "https://doc/1", ["folder"], []))
        self.assertEqual(result.name, "Anna Kovács - MOON42")
        uses = [(name, kwargs) for api in (self.drive, self.docs) for name, kwargs in api.calls
                if "tpl" in repr(kwargs)]
        self.assertEqual([name for name, _ in uses], ["copy"])
        self.assertEqual(uses[0][1]["fileId"], "tpl")
        self.assertEqual(uses[0][1]["body"], {"name": "Anna Kovács - MOON42", "parents": ["folder"]})
        batches = [kwargs for name, kwargs in self.docs.calls if name == "batchUpdate"]
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["documentId"], "doc-1")
        self.assertEqual(batches[0]["body"]["writeControl"], {"requiredRevisionId": "rev-1"})

    def test_failure_after_copy_carries_the_document(self):
        self.docs.results["batchUpdate"] = RuntimeError("boom")
        with self.assertRaises(docfill.GenerationError) as caught:
            self.generate()
        self.assertEqual((caught.exception.document_id, caught.exception.url), ("doc-1", "https://doc/1"))
        self.assertIn("boom", str(caught.exception))

    def test_failed_pdf_check_is_a_layout_issue(self):
        self.drive.results["export"] = RuntimeError("export down")
        result = self.generate()
        self.assertEqual(len(result.layout_issues), 1)
        self.assertIn("export down", result.layout_issues[0])
        self.assertIn("kézi döntés kell", result.layout_issues[0])


if __name__ == "__main__":
    unittest.main()
