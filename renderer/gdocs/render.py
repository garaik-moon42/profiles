#!/usr/bin/env python3
"""Create a Google Docs document from a YAML profile."""

import argparse
import json
from pathlib import Path
import sys

import yaml

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ModuleNotFoundError as error:
    GOOGLE_IMPORT_ERROR = error
else:
    GOOGLE_IMPORT_ERROR = None


RENDERER_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = RENDERER_DIR.parents[1]
CONFIG_PATH = RENDERER_DIR / "config.yaml"
CREDENTIALS_PATH = RENDERER_DIR / "credentials.json"
OUTPUT_DIR = REPOSITORY_ROOT / "target" / "gdocs"
TOKEN_PATH = OUTPUT_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
GOOGLE_DOC_MIME_TYPE = "application/vnd.google-apps.document"


class UniqueKeyLoader(yaml.SafeLoader):
    """Load mappings without silently accepting duplicate keys."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise ValueError(f"Ismétlődő YAML-kulcs: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def load_yaml(path):
    with path.open(encoding="utf-8") as source:
        return yaml.load(source, Loader=UniqueKeyLoader)


def required_text(mapping, key, context):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Hiányzó vagy érvénytelen {context}.{key} érték.")
    return value.strip()


def load_inputs(profile_path):
    profile = load_yaml(profile_path)
    if not isinstance(profile, dict):
        raise ValueError("A profil gyökere YAML-objektum legyen.")

    personal_data = profile.get("personalData")
    first_name = required_text(personal_data, "firstName", "personalData")
    last_name = required_text(personal_data, "lastName", "personalData")

    config = load_yaml(CONFIG_PATH)
    folder_id = required_text(config, "targetFolderId", "config")
    return f"{first_name} {last_name} - MOON42", folder_id


def authenticate():
    credentials = None
    if TOKEN_PATH.exists():
        credentials = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    elif not credentials or not credentials.valid:
        if not CREDENTIALS_PATH.is_file():
            raise FileNotFoundError(
                f"Az OAuth klienskonfiguráció nem található: {CREDENTIALS_PATH}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        credentials = flow.run_local_server(port=0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")
    TOKEN_PATH.chmod(0o600)
    return credentials


def create_document(credentials, title, folder_id):
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    docs = build("docs", "v1", credentials=credentials, cache_discovery=False)

    document = (
        drive.files()
        .create(
            body={
                "name": title,
                "mimeType": GOOGLE_DOC_MIME_TYPE,
                "parents": [folder_id],
            },
            fields="id,name,parents,webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    text = "Hello World!\n"
    docs.documents().batchUpdate(
        documentId=document["id"],
        body={
            "requests": [
                {"insertText": {"location": {"index": 1}, "text": text}},
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": 1, "endIndex": 1 + len(text)},
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                        "fields": "namedStyleType",
                    }
                },
            ]
        },
    ).execute()
    return document


def write_receipt(profile_path, document):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{profile_path.stem}.json"
    output_path.write_text(
        json.dumps(
            {
                "documentId": document["id"],
                "name": document["name"],
                "url": document.get(
                    "webViewLink",
                    f"https://docs.google.com/document/d/{document['id']}/edit",
                ),
                "parentFolderIds": document.get("parents", []),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="A bemeneti YAML-profil útvonala")
    args = parser.parse_args()

    if GOOGLE_IMPORT_ERROR:
        print(
            "Hiányzó Google API-függőség. Telepítsd a requirements.txt csomagjait: "
            f"{GOOGLE_IMPORT_ERROR}",
            file=sys.stderr,
        )
        return 1

    try:
        title, folder_id = load_inputs(args.input)
        credentials = authenticate()
        document = create_document(credentials, title, folder_id)
        output_path = write_receipt(args.input, document)
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError, HttpError) as error:
        print(f"Hiba: {error}", file=sys.stderr)
        return 1

    url = document.get(
        "webViewLink", f"https://docs.google.com/document/d/{document['id']}/edit"
    )
    print(f"Google Docs dokumentum: {url}")
    print(f"Helyi kimenet: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
