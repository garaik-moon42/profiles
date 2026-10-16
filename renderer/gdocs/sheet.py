"""Reading the 'Candidates' tab and the guarded write-back of the MOON42
Profile cell (FR-3, FR-15). The only cell this module ever writes is the
MOON42 Profile cell of one row."""

from dataclasses import dataclass

from renderer.gdocs.auth import execute

TAB = "Candidates"
HEADERS = ("Name", "Status", "Mobile", "Email", "MOON42 Profile")
CELL_FIELDS = ("values(formattedValue,hyperlink,chipRuns,"
               "textFormatRuns(format(link)))")
DOC_MIME_TYPE = "application/vnd.google-apps.kix"


class SheetError(Exception):
    """User-facing (Hungarian) sheet problem."""


@dataclass
class Row:
    number: int  # 1-based sheet row number
    name: str
    status: str
    mobile: str
    email: str
    profile_text: str
    profile_has_chip: bool  # chip, link or rich-text link present


def _column_letter(index):
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def _text(cell):
    return (cell or {}).get("formattedValue") or ""


def _has_chip(cell):
    cell = cell or {}
    return bool(cell.get("chipRuns") or cell.get("hyperlink")
                or any(run.get("format", {}).get("link")
                       for run in cell.get("textFormatRuns", [])))


def _grid(sheets, spreadsheet_id, cell_range):
    response = execute(sheets.spreadsheets().get(
        spreadsheetId=spreadsheet_id, ranges=[cell_range], includeGridData=True,
        fields=f"sheets(data(startRow,rowData({CELL_FIELDS})))"))
    sheet_list = response.get("sheets") or []
    data = sheet_list[0].get("data") if sheet_list else None
    if not data:
        return 0, []
    return data[0].get("startRow", 0), data[0].get("rowData") or []


def _columns(header_cells):
    names = [_text(cell).strip() for cell in header_cells]
    missing = [h for h in HEADERS if h not in names]
    if missing:
        raise SheetError("A „" + TAB + "” fülről hiányzó fejléc: "
                         + ", ".join(missing) + ".")
    return {h: names.index(h) for h in HEADERS}


def _row(columns, number, cells):
    def cell(header):
        index = columns[header]
        return cells[index] if index < len(cells) else None

    profile = cell("MOON42 Profile")
    return Row(number=number, name=_text(cell("Name")),
               status=_text(cell("Status")), mobile=_text(cell("Mobile")),
               email=_text(cell("Email")), profile_text=_text(profile),
               profile_has_chip=_has_chip(profile))


def read_candidates(sheets, spreadsheet_id):
    """Return (columns, rows) of the Candidates tab; rows skip the header."""
    try:
        start, row_data = _grid(sheets, spreadsheet_id, TAB)
    except Exception as error:
        if getattr(getattr(error, "resp", None), "status", None) == 400:
            raise SheetError(f"A „{TAB}” fül nem olvasható: {error}") from None
        raise
    if not row_data or start != 0:
        raise SheetError(f"A „{TAB}” fül üres vagy nem található.")
    columns = _columns(row_data[0].get("values") or [])
    rows = [_row(columns, i + 1, r.get("values") or [])
            for i, r in enumerate(row_data) if i > 0]
    return columns, rows


def _read_row(sheets, spreadsheet_id, columns, number):
    last = _column_letter(max(columns.values()))
    _, row_data = _grid(sheets, spreadsheet_id, f"{TAB}!A{number}:{last}{number}")
    cells = (row_data[0].get("values") or []) if row_data else []
    return _row(columns, number, cells)


def _update_cell(sheets, spreadsheet_id, sheet_id, columns, number, cell):
    return execute(sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"updateCells": {
            "start": {"sheetId": sheet_id, "rowIndex": number - 1,
                      "columnIndex": columns["MOON42 Profile"]},
            "rows": [{"values": [cell]}],
            "fields": "userEnteredValue,chipRuns,textFormatRuns",
        }}]}))


def _sheet_id(sheets, spreadsheet_id):
    response = execute(sheets.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))"))
    for sheet in response.get("sheets", []):
        if sheet["properties"]["title"] == TAB:
            return sheet["properties"]["sheetId"]
    raise SheetError(f"A „{TAB}” fül nem található.")


def write_profile_link(sheets, spreadsheet_id, columns, row, doc_name, doc_url):
    """Write the doc chip into the MOON42 Profile cell of `row` (a Row read
    earlier) if the sheet still has the same Name at that row number and the
    cell is still empty. Falls back to a hyperlink if chips are rejected.
    Returns (written, message); message is a Hungarian reason when not written
    and "hiperhivatkozás" when the fallback was used."""
    _, header = _grid(sheets, spreadsheet_id, f"{TAB}!A1:AZ1")
    try:
        current_columns = _columns((header[0].get("values") or []) if header else [])
    except SheetError as error:
        return False, f"a fejléc időközben megváltozott ({error})"
    if current_columns != columns:
        return False, "az oszlopok helye időközben megváltozott"
    current = _read_row(sheets, spreadsheet_id, columns, row.number)
    if current.name != row.name:
        return False, (f"a(z) {row.number}. sorban időközben más név áll "
                       f"(„{current.name}”)")
    if current.profile_has_chip or current.profile_text.strip():
        return False, f"a(z) {row.number}. sor MOON42 Profile cellája időközben megtelt"

    sheet_id = _sheet_id(sheets, spreadsheet_id)
    chip_cell = {
        "userEnteredValue": {"stringValue": "@"},
        "chipRuns": [{"startIndex": 0, "chip": {"richLinkProperties": {"uri": doc_url}}}],
    }
    try:
        _update_cell(sheets, spreadsheet_id, sheet_id, columns, row.number, chip_cell)
        return True, None
    except Exception as error:
        if getattr(getattr(error, "resp", None), "status", None) != 400:
            raise
    link_cell = {
        "userEnteredValue": {"stringValue": doc_name},
        "textFormatRuns": [{"startIndex": 0, "format": {"link": {"uri": doc_url}}}],
    }
    _update_cell(sheets, spreadsheet_id, sheet_id, columns, row.number, link_cell)
    return True, "hiperhivatkozás"
