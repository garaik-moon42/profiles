"""Fake Sheets service shared by the sheet and render tests."""

import re

HEADER = ["Name", "Status", "Role", "Mobile", "Email", "MOON42 Profile"]


def cell(text="", chip=None):
    result = {"formattedValue": text} if text else {}
    if chip:
        result["chipRuns"] = [{"chip": {"richLinkProperties": {"uri": chip}}}]
    return result


def row(name, status="in progress", mobile="", email="", profile=None, chip=None):
    return [cell(name), cell(status), cell("x"), cell(mobile), cell(email),
            cell(profile or "", chip)]


class _Request:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class FakeSheets:
    """Grid rows are lists of cell dicts; row 0 is the header."""

    def __init__(self, rows):
        self.grid = [[cell(h) for h in HEADER]] + rows
        self.updates = []

    def spreadsheets(self):
        return self

    def get(self, **kwargs):
        def run():
            if "ranges" not in kwargs:
                return {"sheets": [{"properties": {"sheetId": 7, "title": "Candidates"}}]}
            match = re.fullmatch(r"Candidates!A(\d+):[A-Z]+\d+", kwargs["ranges"][0])
            if match:
                number = int(match.group(1))
                data = {"startRow": number - 1,
                        "rowData": [{"values": self.grid[number - 1]}]}
            else:
                data = {"rowData": [{"values": r} for r in self.grid]}
            return {"sheets": [{"data": [data]}]}
        return _Request(run)

    def batchUpdate(self, spreadsheetId, body):
        def run():
            self.updates.append(body)
            update = body["requests"][0]["updateCells"]
            value = update["rows"][0]["values"][0]
            new = {"formattedValue": value["userEnteredValue"]["stringValue"]}
            if "chipRuns" in value:
                new["chipRuns"] = value["chipRuns"]
            self.grid[update["start"]["rowIndex"]][update["start"]["columnIndex"]] = new
            return {}
        return _Request(run)
