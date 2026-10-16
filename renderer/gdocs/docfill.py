"""Fill a copy of the "_TEMPLATE - MOON42" document from a profile
(FR-7 … FR-14).

The Docs API cannot copy paragraphs or set tab stops, so every new paragraph
is created by inserting text at the start of a template paragraph of the
right kind: the inserted paragraphs inherit its paragraph style, tab stops
and bullet. Each template region (e.g. the skill rows) is replaced like
this: insert the new paragraphs at its start, apply the template's text
styles to every run, then delete the old paragraphs. Work Experience needs
any number of row/bullet alternations, so all of its paragraphs come from
the position row and its bullets are created with createParagraphBullets
(rendered identically to the template's bullets); the Certificates heading
is a split Education bullet turned into a copy of the Education heading.
The whole fill is one batchUpdate guarded by the copy's revision (NFR-2).
"""

from dataclasses import dataclass, field
from pathlib import Path

from renderer.gdocs import layout, logic, pdfcheck
from renderer.gdocs.auth import OUTPUT_DIR, execute

PDF_DIR = OUTPUT_DIR / "pdf"
SKILLS, WORK, EDUCATION, INTERESTS, CONTACT = (
    "Skills", "Work Experience", "Education", "Personal Interests", "Contact Information")
HEADINGS = (SKILLS, WORK, EDUCATION, INTERESTS, CONTACT)
# Template skill rows in order (the Libraries row is always deleted).
SKILL_ROWS = (("Languages", "languages"), ("Programming", "programming"),
              ("Databases", "databases"), ("Frameworks", "frameworks"),
              ("Testing", "testing"), ("DevOps / IaC", "devops"), ("AI", "ai"),
              ("Cloud", "cloud"), ("Other", "other"), ("Soft skills", "soft"))
DASH = " – "


@dataclass
class GeneratedDoc:
    document_id: str
    name: str
    url: str
    parent_folder_ids: list[str]
    warnings: list[str]
    layout_issues: list[str]


class GenerationError(Exception):
    """Hungarian message; document_id/url are set if the copy already exists."""

    def __init__(self, message, document_id=None, url=None):
        super().__init__(message)
        self.document_id = document_id
        self.url = url


@dataclass
class Para:
    """A new paragraph: runs of (text, style key); the paragraph mark takes
    the last run's style. kind: None (inherit), "bullet" or "heading"."""
    runs: list
    kind: str = None


@dataclass
class Region:
    """Template range [start, end) replaced by `paras`. `inline` replaces the
    text of a single paragraph and keeps its paragraph mark."""
    start: int
    end: int
    paras: list = field(default_factory=list)
    inline: bool = False


# --- Template structure --------------------------------------------------------

def _text(element):
    return "".join(r.get("textRun", {}).get("content", "")
                   for r in element["paragraph"]["elements"])


def _run_style(element, needle):
    for run in element["paragraph"]["elements"]:
        text_run = run.get("textRun", {})
        if needle in text_run.get("content", ""):
            return dict(text_run.get("textStyle", {}))
    raise ValueError(f"a(z) „{needle}” mintaszöveg nem található")


def _find(elements, needle):
    for element in elements:
        if needle in _text(element):
            return element
    raise ValueError(f"a(z) „{needle}” mintaszöveg nem található")


def parse_template(document):
    """Locate the template's paragraphs and sample text styles.
    Returns (anchors, sections, styles, heading_style): anchors are the name,
    title and intro paragraphs plus the headings and the final paragraph;
    sections maps each heading to its paragraphs."""
    body = document["body"]["content"]
    cells = [p for el in body if "table" in el
             for row in el["table"]["tableRows"] for cell in row["tableCells"]
             for p in cell["content"] if "paragraph" in p]
    paragraphs = [el for el in body if "paragraph" in el]
    anchors = {"name": _find(cells, "Tivadar Template"),
               "title": _find(cells, "Senior .Net Developer"),
               "intro": _find(paragraphs, "TODO: Short brief introduction"),
               "last": paragraphs[-1]}
    sections, current = {}, None
    for element in paragraphs[:-1]:
        text = _text(element).strip()
        if (element["paragraph"]["paragraphStyle"].get("namedStyleType") == "HEADING_2"
                and text in HEADINGS):
            current = text
            anchors[text] = element
            sections[text] = []
        elif current:
            sections[current].append(element)
    missing = [h for h in HEADINGS if not sections.get(h)]
    if missing:
        raise ValueError("hiányzó vagy üres szakasz: " + ", ".join(missing))

    skill = sections[SKILLS][0]
    work, education = sections[WORK], sections[EDUCATION]
    interest, contact = sections[INTERESTS][0], sections[CONTACT][0]
    position, project = work[0], _find(work, "Project")
    degree = _find(education, "Degree")
    styles = {
        "name": _run_style(anchors["name"], "Tivadar"),
        "title": _run_style(anchors["title"], "Senior"),
        "intro": _run_style(anchors["intro"], "TODO"),
        "skill.label": _run_style(skill, "Languages"),
        "skill.value": _run_style(skill, "English"),
        "pos.title": _run_style(position, "Position"),
        "pos.company": _run_style(position, "Company"),
        "pos.date": _run_style(position, "mm/yyyy"),
        "pos.dash": _run_style(position, "–"),
        "proj.name": _run_style(project, "Project"),
        "proj.location": _run_style(project, "Location"),
        "bullet": _run_style(_find(work, "Description"), "Description"),
        "edu.name": _run_style(degree, "Degree"),
        "edu.detail": _run_style(degree, "Institute"),
        "edu.date": _run_style(degree, "mm/yyyy"),
        "edu.dash": _run_style(degree, "–"),
        "heading": _run_style(anchors[EDUCATION], "E"),
        # the template marks the placeholder with a yellow highlight (FR-11)
        "interest.name": _without_highlight(_run_style(interest, "Activity")),
        "interest.detail": _without_highlight(_run_style(interest, "Why")),
        "contact.label": _run_style(contact, "Email"),
        "contact.value": _run_style(contact, "tivadar"),
    }
    heading_style = {k: v for k, v in anchors[EDUCATION]["paragraph"]["paragraphStyle"].items()
                     if k not in ("tabStops", "headingId")}
    return anchors, sections, styles, heading_style


def _without_highlight(style):
    style.pop("backgroundColor", None)
    return style


def run_fonts(styles):
    """(size, bold) per style key, for the tab computation (FR-13)."""
    return {key: (style.get("fontSize", {}).get("magnitude", 10), bool(style.get("bold")))
            for key, style in styles.items()}


# --- Content (pure) ------------------------------------------------------------

def _clean(value):
    """Collapse whitespace (YAML block scalars may contain newlines)."""
    return " ".join(str(value).split()) if value is not None else ""


def _joined(items):
    return ", ".join(_clean(i) for i in items or [] if _clean(i))


def date_runs(text, start_key, dash_key, end_key):
    """Runs of a formatted range: '<start> ' / '– ' / '<end>' with the
    template's run split (the dash has its own style)."""
    if DASH not in text:
        return [(text, start_key)] if text else []
    start, end = text.split(DASH, 1)
    if dash_key == end_key:
        return [(start + " ", start_key), ("– " + end, dash_key)]
    return [(start + " ", start_key), ("– ", dash_key), (end, end_key)]


def tabbed_row(left, center, right, fonts, width_fn):
    """Runs of `left <tabs> center <tabs> right`, the tab counts and the
    center padding spaces from layout.row_tabs; tabs and padding take the
    style of the preceding part (the one row_tabs measures the space in)."""
    def measured(runs):
        return [layout.Run(text, *fonts[key]) for text, key in runs]

    center_tabs, right_tabs, spaces = layout.row_tabs(
        measured(left), measured(center) or None, measured(right) or None, width_fn)
    runs = list(left)
    for part, tabs, pad in ((center, center_tabs, spaces), (right, right_tabs, 0)):
        if part:
            runs.append(("\t" * tabs + " " * pad, runs[-1][1] if runs else part[0][1]))
            runs.extend(part)
    return runs


def content_plan(profile, email, mobile, fonts, width_fn=layout.roboto_width):
    """The new paragraphs per template part, the PDF row specs and warnings.
    Returns (plan, rows, warnings); plan keys: name, title, intro, skills,
    work, education, certificates, interests, contact."""
    personal = profile.get("personalData") or {}
    warnings = []
    intro = _clean(personal.get("introductionThirdPerson"))
    if not intro:
        intro = _clean(personal.get("introduction"))
        warnings.append("Nincs personalData.introductionThirdPerson: a bemutatkozás az "
                        "introduction szövege változatlanul, ellenőrizd (harmadik személy).")

    skills = profile.get("skills") or {}
    values = logic.split_skills(skills.get("technical") or {})
    values["languages"] = personal.get("languages")
    values["soft"] = skills.get("soft")
    skill_paras = [Para([(label, "skill.label"), ("\t" + _joined(values[key]), "skill.value")])
                   for label, key in SKILL_ROWS if _joined(values[key])]

    work, rows = [], []

    def add_row(label, left, center, right):
        """A position/project row and its PDF spec; a row without text is
        left out entirely."""
        if not (left or center or right):
            return
        work.append(Para(tabbed_row(left, center, right, fonts, width_fn)))
        rows.append(pdfcheck.RowSpec(label, [
            "".join(t for t, _ in part) or None for part in (left, center, right)]))

    for job in profile.get("experience") or []:
        role = _clean(job.get("role"))
        company = _clean(job.get("companyShortName") or job.get("company"))
        dates = logic.format_date_range(job.get("start"), job.get("end", logic.MISSING))
        add_row(f"Pozíció: {role} – {company}",
                [(role, "pos.title")] if role else [],
                [(company, "pos.company")] if company else [],
                date_runs(dates, "pos.date", "pos.dash", "pos.date"))
        for project in job.get("projects") or []:
            name, location = _clean(project.get("name")), _clean(project.get("location"))
            add_row(f"Projekt: {name or location}",
                    [(name, "proj.name")] if name else [], [],
                    [(location, "proj.location")] if location else [])
            bullets = [_clean(r) for r in project.get("responsibilities") or [] if _clean(r)]
            if _joined(project.get("techStack")):
                bullets.append("Tech stack: " + _joined(project.get("techStack")))
            work.extend(Para([(text, "bullet")], "bullet") for text in bullets)

    def labelled(name, detail, prefix, separator, detail_prefix=""):
        """'**name<separator>**<detail_prefix>detail'; a missing part drops
        with its separator."""
        name, detail = _clean(name), _clean(detail)
        if name and detail:
            return [(name + separator, f"{prefix}.name"),
                    (detail_prefix + detail, f"{prefix}.detail")]
        return ([(name, f"{prefix}.name")] if name
                else [(detail, f"{prefix}.detail")] if detail else [])

    education = []
    for degree in profile.get("education") or []:
        dates = logic.format_date_range(degree.get("start"), degree.get("end", logic.MISSING))
        education.append(Para(_row_with_tab(
            labelled(degree.get("name"), degree.get("institution"), "edu", ", "),
            date_runs(dates, "edu.date", "edu.dash", "edu.dash"))))
    certificates = []
    for cert in profile.get("certificates") or []:
        date = logic.format_date(cert["date"]) if cert.get("date") else ""
        certificates.append(Para(_row_with_tab(
            labelled(cert.get("name"), cert.get("organization"), "edu", ", "),
            [(date, "edu.date")] if date else [])))
    # the template's "Activity:" keeps the colon in the bold run
    interests = [Para(labelled(i.get("name"), i.get("description"), "interest", ":", " "))
                 for i in profile.get("interests") or [] if isinstance(i, dict)]
    interests = [p for p in interests if p.runs]

    contact = [Para([("Email", "contact.label"), ("\t" + email, "contact.value")])]
    if mobile:
        contact.append(Para([("Mobile", "contact.label"), ("\t" + str(mobile), "contact.value")]))

    plan = {
        "name": [Para([(f"{_clean(personal.get('firstName'))} "
                        f"{_clean(personal.get('lastName'))}".strip(), "name")])],
        "title": [Para([(_clean(personal.get("title")), "title")])],
        "intro": [Para([(intro, "intro")])],
        "skills": skill_paras, "work": work, "education": education,
        "certificates": certificates, "interests": interests, "contact": contact,
    }
    return plan, rows, warnings


def _row_with_tab(left, right):
    """Education/certificate row: the right-aligned part after one tab, which
    joins the preceding run (as in the template)."""
    runs = [list(r) for r in left]
    if right:
        if runs:
            runs[-1][0] += "\t"
        else:
            runs = [["\t", right[0][1]]]
        runs.extend(list(r) for r in right)
    return [tuple(r) for r in runs]


# --- Requests (pure) -----------------------------------------------------------

def regions(anchors, sections, plan):
    """Template regions and their replacement paragraphs (FR-8, FR-10). An
    empty section is deleted together with its heading."""
    def span(elements):
        return elements[0]["startIndex"], elements[-1]["endIndex"]

    def inline(key):
        element = anchors[key]
        return Region(element["startIndex"], element["endIndex"] - 1, plan[key], inline=True)

    result = [inline("name"), inline("title"), inline("intro")]
    for heading, paras in ((SKILLS, plan["skills"]), (WORK, plan["work"]),
                           (INTERESTS, plan["interests"]), (CONTACT, plan["contact"])):
        start, end = span(sections[heading])
        if not paras:
            start = anchors[heading]["startIndex"]
        result.append(Region(start, end, paras))

    start, end = span(sections[EDUCATION])
    education, certificates = plan["education"], plan["certificates"]
    if education and certificates:
        heading = Para([("Certificates", "heading")], "heading")
        result.append(Region(start, end, education + [heading] + certificates))
    elif certificates:  # the Education heading becomes the Certificates heading
        result.append(Region(anchors[EDUCATION]["startIndex"], anchors[EDUCATION]["endIndex"] - 1,
                             [Para([("Certificates", "heading")])], inline=True))
        result.append(Region(start, end, certificates))
    else:
        result.append(Region(start if education else anchors[EDUCATION]["startIndex"],
                             end, education))
    return result


def _units(text):
    """Length in UTF-16 code units, the unit of Docs API indices."""
    return len(text.encode("utf-16-le")) // 2


def region_requests(region, styles, heading_style):
    """insertText at the region start, the template text style on every run
    (the paragraph mark takes the last run's style), bullet/heading
    conversion, then deletion of the old content."""
    requests, index, text = [], region.start, ""
    for number, para in enumerate(region.paras):
        para_start = index
        runs = [(t, k) for t, k in para.runs if t]
        mark = not region.inline or number < len(region.paras) - 1
        if mark:
            runs.append(("\n", para.runs[-1][1] if para.runs else None))
        for run_text, key in runs:
            if key is not None:
                requests.append({"updateTextStyle": {
                    "range": {"startIndex": index, "endIndex": index + _units(run_text)},
                    "textStyle": styles[key], "fields": "*"}})
            text += run_text
            index += _units(run_text)
        paragraph_range = {"startIndex": para_start, "endIndex": index}
        if para.kind == "bullet":
            requests.append({"createParagraphBullets": {
                "range": paragraph_range, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
        elif para.kind == "heading":
            requests.append({"deleteParagraphBullets": {"range": paragraph_range}})
            requests.append({"updateParagraphStyle": {
                "range": paragraph_range, "paragraphStyle": heading_style, "fields": "*"}})
    if text:
        requests.insert(0, {"insertText": {"location": {"index": region.start}, "text": text}})
    if region.end > region.start:
        requests.append({"deleteContentRange": {"range": {
            "startIndex": region.start + _units(text), "endIndex": region.end + _units(text)}}})
    return requests


def build_requests(document, profile, email, mobile, width_fn=None):
    """All fill requests for a fresh template copy, processed from the end of
    the document so that earlier indices stay valid. Returns
    (requests, row_specs, warnings); width_fn defaults to the Roboto metrics."""
    try:
        anchors, sections, styles, heading_style = parse_template(document)
    except ValueError as error:
        raise GenerationError(f"A sablon szerkezete eltér a várttól: {error}.") from error
    plan, rows, warnings = content_plan(profile, email, mobile, run_fonts(styles),
                                           width_fn or layout.roboto_width)
    requests = []
    for region in sorted(regions(anchors, sections, plan), key=lambda r: r.start, reverse=True):
        requests.extend(region_requests(region, styles, heading_style))
    return requests, rows, warnings


# --- API -----------------------------------------------------------------------

def generate_document(drive, docs, *, template_id, folder_id, profile, email, mobile):
    """Copy the template into `folder_id`, fill it, export it as PDF and check
    the position/project rows (FR-7 … FR-14). Only files.copy touches the
    template (NFR-1)."""
    personal = profile["personalData"]
    name = f"{personal['firstName']} {personal['lastName']} - MOON42"
    try:
        copy = execute(drive.files().copy(
            fileId=template_id, body={"name": name, "parents": [folder_id]},
            fields="id,name,webViewLink,parents", supportsAllDrives=True))
    except Exception as error:
        raise GenerationError(f"A sablon másolása sikertelen ({name}): {error}") from error
    document_id = copy["id"]
    url = copy.get("webViewLink") or f"https://docs.google.com/document/d/{document_id}/edit"
    try:
        document = execute(docs.documents().get(documentId=document_id))
        requests, rows, warnings = build_requests(document, profile, email, mobile)
        execute(docs.documents().batchUpdate(documentId=document_id, body={
            "requests": requests,
            "writeControl": {"requiredRevisionId": document["revisionId"]}}))
    except Exception as error:
        raise GenerationError(f"A dokumentum kitöltése sikertelen ({name}): {error}",
                              document_id, url) from error
    try:  # the filled document stays even if the check fails (FR-14)
        pdf_path = export_pdf(drive, document_id, PDF_DIR / f"{name}.pdf")
        layout_issues, _ = pdfcheck.check_pdf(pdf_path, rows)
    except Exception as error:
        layout_issues = [f"A tördelés PDF-ellenőrzése nem futott le ({error}), "
                         f"{pdfcheck.HINT}."]
    return GeneratedDoc(document_id, name, url, copy.get("parents", [folder_id]),
                        warnings, layout_issues)


def export_pdf(drive, document_id, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(execute(drive.files().export(fileId=document_id,
                                                  mimeType="application/pdf")))
    return path
