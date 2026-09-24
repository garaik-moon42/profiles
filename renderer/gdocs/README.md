# Google Docs renderer

Ez a dokumentum a Google Docs-generátor terveinek és a később meghozott
döntéseknek a gyűjtőhelye. A jelenlegi első változat egy „Hello World!”
dokumentummal ellenőrzi a teljes API-kapcsolatot és OAuth 2.0 folyamatot.

## Cél

A repóban tárolt YAML-formátumú szakmai profilokból Google Docs-dokumentumot
előállítani, amely nyomtatható és PDF-be exportálható.

## Elhelyezés

A `renderer/` könyvtár alatt több generátor is létezhet egymás mellett,
mindegyik saját alkönyvtárban. Az első renderer a Google Docs-dokumentumokat
előállító `gdocs`, amelynek tervei és megvalósítása ebbe a könyvtárba kerülnek.

## Kiindulópont

- A [közös rendererszabályok](../README.md) szerint parancssorból is futtatható
  program, amely egy bemeneti fájlparamétert kap.
- Bemenet: a repó YAML-formátumú szakmai profiljai.
- Adatmodell: a [profil séma](../../schemas/profile.schema.json) szerinti 1.0-s verzió.
- Kimenet: Google Docs-dokumentum, nyomtatásra és PDF-exportálásra alkalmas elrendezéssel.
- A helyi kimeneti nyugta a repo gyökerében lévő `target/gdocs/` könyvtárba kerül.
- A profiladatok szerkesztési szabályait a [repo útmutatója](../../README.md) rögzíti.

## Konfiguráció

A renderer beállításait a mellette található [`config.yaml`](config.yaml) fájl
tartalmazza. A `targetFolderId` értékébe annak a Google Drive-mappának az
azonosítója kerül, amelyben a generált dokumentumokat létre kell hozni:

```yaml
targetFolderId: "1AbCdEfGhIjKlMnOpQrStUvWxYz"
```

Az azonosító a mappa URL-jének `/folders/` utáni része. A hiányzó, üres vagy
`null` értéket a generátor hibának tekinti. A fájlba hitelesítési adat vagy
privát kulcs nem kerülhet.

## OAuth 2.0 beállítása

1. Hozz létre vagy válassz ki egy projektet a Google Cloud Console-ban.
2. Engedélyezd a Google Docs API-t és a Google Drive API-t.
3. Állítsd be az OAuth consent screent, majd hozz létre egy **Desktop app**
   típusú OAuth client ID-t.
4. Töltsd le a kliens JSON-fájlját, és mentsd
   `renderer/gdocs/credentials.json` néven.

A `credentials.json` és az első sikeres belépés után létrejövő
`target/gdocs/token.json` hitelesítési adatot tartalmaz, ezért egyik sem kerül
verziókezelésbe. A renderer csak a `drive.file` scope-ot kéri: az általa
létrehozott fájlokhoz fér hozzá, nem a felhasználó teljes Drive-tartalmához.

## Futtatás

Virtuális környezet létrehozása és a függőségek telepítése:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r renderer/gdocs/requirements.txt
```

A renderer egy profilfájlt kap paraméterül:

```bash
.venv/bin/python renderer/gdocs/render.py profiles/athukoralage-chamith-udayanga.yaml
```

Az első futtatás megnyitja a Google OAuth jóváhagyási folyamatát. A program a
profilból olvassa ki a dokumentum címét, majd létrehozza azt a konfigurált Drive
mappában. A jelenlegi változat `Hello World!` szöveget ír bele Heading 1
stílussal. A dokumentum azonosítóját és URL-jét a
`target/gdocs/<profilazonosító>.json` nyugtafájlba menti.

## Később kidolgozandó tervek

- A dokumentum megjelenése, szerkezete és oldaltördelése.
- A megjelenítendő profiladatok és az opcionális szakaszok kezelése.
- A hiányos, munkapéldányként jelölt profilok kezelése.
- A végleges hitelesítési mód és üzemeltetési környezet.
- A nyomtatás és a PDF-exportálás munkafolyamata.

Ezek nyitott tervezési témák; konkrét technológiai vagy működési döntés még nem született.
