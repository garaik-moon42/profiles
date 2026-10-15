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

## Tapasztalatok a MOON42-sablon kézi kitöltéséből

Egy agent a `profiles/bence-berenyi.yaml` alapján kézzel töltötte ki a
„_TEMPLATE - MOON42” Google Docs-sablon egy másolatát (2026-10-15). Az alábbi
megfeleltetést a felhasználó erre a profilra hagyta jóvá; a generátor
kiindulópontjaként szolgálhat.

### Megfeleltetés

| Sablonelem | Profiladat |
| --- | --- |
| Név, titulus | `firstName lastName`, `title` |
| Bemutatkozás | `introduction` harmadik személyben, névmás nélkül („Bence is…”) |
| Languages | `personalData.languages` |
| Programming, Databases, Testing, AI, Cloud | a megfelelő `skills.technical` kategória (Cloud: a felhőszolgáltatók) |
| Frameworks | a teljes `frameworksAndLibraries`; a Libraries sor törlődik |
| DevOps / IaC | `devOpsAndCloud` a felhőszolgáltatók nélkül |
| Other | `toolsAndTechnologies`, `developmentMethodologies`, `specializedDomains` |
| Soft skills | `skills.soft` |
| Pozíciósor | `role`, `company`, `mm/yyyy – mm/yyyy` (folyamatban: `Present`) |
| Projektsor | projektnév és `location`; projektdátum nincs, a helyszín jobbra igazítva |
| Description | minden `responsibilities` elem külön bullet |
| Tech stack | `techStack`; ha nincs, a bullet törlődik |
| Education | **`name`,** `institution` ⇥ dátumok (csak év esetén csak év) |
| Certificates | új H2-szakasz az Education után, az Education-bullet stílusával: **`name`,** `organization` ⇥ `date` |
| Personal Interests | üres `interests` esetén a szakasz törlődik |
| Contact | MOON42-es e-mail (`keresztnev.vezeteknev@moon42.com`, ékezetek nélkül) és a mobilszám; a többi elérhetőség kimarad |

Az üres Skills-sorok törlődnek.

### Technikai tanulságok

- A sablon szerkezete fix indexekkel címezhető. A stílus megtartásához a cserét
  a régi szöveg első karaktere után kell beszúrni, majd a régi szöveget törölni;
  a `replaceAllText` a csereszöveg egészére az első illesztett karakter stílusát
  alkalmazza.
- A pozíció- és projektsor tabstopjai (36, 72, 108 pt, középre 261 pt, jobbra
  553 pt) miatt a tabok száma a szöveg szélességétől függ; hosszú cég- vagy
  projektnévnél a szöveg összeér vagy a dátum új sorba törik. Ezt csak a
  renderelt PDF mutatja meg, ezért a generálás után vizuális ellenőrzés kell.
- A Drive-connector PDF-exportja és a Docs-connector `update_doc` hívása
  működött; a teljes kitöltés egyetlen, revízióval védett batch volt.
