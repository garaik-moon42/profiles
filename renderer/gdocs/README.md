# Google Docs renderer

A generátor a „_TESLA Candidates” Google Sheets-táblázat „Candidates” fülje
alapján, a repóban tárolt YAML-profilokból MOON42-formátumú Google
Docs-dokumentumot készít a „_TEMPLATE - MOON42” sablon másolatából. A
dokumentum nyomtatható és PDF-be exportálható.

## Kiindulópont

- A [közös rendererszabályoktól](../README.md) eltérően nem egy bemeneti
  fájlt kap: a táblázat a munkasor, a profilokat a `profiles/` könyvtárból
  olvassa.
- Adatmodell: a [profil séma](../../schemas/profile.schema.json) szerinti 1.0-s verzió.
- A kimenetek a repo gyökerében lévő `target/gdocs/` alá kerülnek.
- A profiladatok szerkesztési szabályait a [repo útmutatója](../../README.md) rögzíti.

## Futtatás

Virtuális környezet létrehozása és a függőségek telepítése:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r renderer/gdocs/requirements.txt
```

Futtatás (bemeneti fájl nélkül):

```bash
.venv/bin/python renderer/gdocs/render.py [--dry-run] [--config <útvonal>]
```

- `--dry-run`: csak listáz. Kiírja a jogosult sorokat, a hozzájuk illesztett
  profilt és a létrejövő dokumentum nevét (a `[DRAFT]` jelölésű profilokat
  jelölve), a kihagyott sorokat és a figyelmeztetéseket; nem hoz létre
  dokumentumot, és nem ír a táblázatba, sem nyugtát.
- `--config <útvonal>`: másik konfigurációs fájl az alapértelmezett
  [`config.yaml`](config.yaml) helyett, például tesztfuttatáshoz a `target/`
  alatt (más mappával és táblázattal).

Az első futtatás megnyitja a Google OAuth jóváhagyási folyamatát.

## A táblázat mint munkasor

A „Candidates” fül fejlécének tartalmaznia kell a `Name`, `Status`, `Mobile`,
`Email` és `MOON42 Profile` oszlopot; hiányzó fejléc hibát okoz.

- **Jogosult sor:** a `Status` értéke „in progress” (a szélső szóközök és a
  kis/nagybetű nem számít), és a `MOON42 Profile` cella üres (nincs szöveg, chip vagy link).
- **Újragenerálás:** a sor `MOON42 Profile` cellájának kiürítése után a
  következő futtatás újra elkészíti a dokumentumot. A korábbi dokumentum nem
  törlődik; az azonosítója a nyugta `previousDocuments` listájába kerül.
- **Sor–profil illesztés:** a `Name` cella szavai (ékezet-, kis/nagybetű-
  érzéketlenül, szóköz, pont és kötőjel mentén szétvágva) mind szerepelnek a
  profil `firstName` és `lastName` szavai között. Pontosan egy profil
  illeszkedhet.
- **Kihagyott sor (nem hiba):** üres név, nincs illeszkedő profil, vagy több
  profil illeszkedik; részleges névegyezésnél figyelmeztetés sorolja fel a
  jelölt profilokat.
- **Hiba:** ha több jogosult sor illeszkedik ugyanarra a profilra, mindegyik
  hibás; hibás (nem olvasható) profilfájl is hiba.
- **Visszaírás:** siker után a program a sor `MOON42 Profile` cellájába írja a
  dokumentum Drive-chipjét. Írás előtt újraolvassa a fejlécet és a sort: ha az
  oszlopok elmozdultak, a sorban más név áll, vagy a cella közben megtelt,
  nem ír, és ezt jelzi. Ha a chip írását a Sheets elutasítja, hiperhivatkozás
  kerül a cellába. Más cellát a program nem módosít.

## Konfiguráció

A [`config.yaml`](config.yaml) három kötelező kulcsot tartalmaz; a hiányzó vagy
üres érték hiba:

- `targetFolderId`: a Drive-mappa azonosítója („MOON42 Profiles”), ahová a
  dokumentumok kerülnek (az URL `/folders/` utáni része).
- `templateId`: a MOON42-sablon azonosítója. A sablonra csak olvasó és másoló
  hívás megy, soha nem módosul.
- `spreadsheetId`: a jelölteket nyilvántartó táblázat azonosítója.

A fájlba hitelesítési adat nem kerülhet.

## OAuth 2.0 beállítása

1. Hozz létre vagy válassz ki egy projektet a Google Cloud Console-ban.
2. Engedélyezd a Google Docs, a Google Drive és a Google Sheets API-t.
3. Állítsd be az OAuth consent screent, majd hozz létre egy **Desktop app**
   típusú OAuth client ID-t.
4. Töltsd le a kliens JSON-fájlját, és mentsd
   `renderer/gdocs/credentials.json` néven.

A `credentials.json` és a belépés után létrejövő `target/gdocs/token.json`
hitelesítési adatot tartalmaz, ezért egyik sem kerül verziókezelésbe.

**Scope-ok:**

- `drive.file`: a renderer által létrehozott (másolt) fájlok olvasása és írása;
- `drive.readonly`: a (nem a renderer által létrehozott) sablon és táblázat olvasása;
- `spreadsheets`: a táblázat olvasása és a `MOON42 Profile` cella írása.

Ha a mentett token scope-listája eltér a fentitől (pl. a scope-ok változtak),
vagy a refresh token lejárt vagy visszavonták, a program új jóváhagyást kér
(böngészős belépés). External/Testing consent módban a refresh token 7 nap
után lejár, ezért legfeljebb hetente új belépés kell; Internal módban vagy
publikált alkalmazásnál ez nem áll fenn.

## Kimenetek

- **Nyugta:** `target/gdocs/<profilazonosító>.json`; mezői: `documentId`,
  `name`, `url`, `parentFolderIds`, `sheetRow`, `draft`, `issues` (figyelmeztetések,
  tördelési és táblázatírási problémák), `previousDocuments` (a korábbi
  futtatásokból származó `documentId`/`url` párok). Hibás kitöltésnél is
  készül nyugta, ha a másolat már létezik.
- **PDF:** `target/gdocs/pdf/<Keresztnév Vezetéknév> - MOON42.pdf`, a tördelés
  ellenőrzéséhez exportált példány.
- **Dokumentumnév:** `<firstName> <lastName> - MOON42`, a `config.yaml`-ban
  megadott mappában.
- **Stdout:** összesítő a jogosult sorok számáról, majd „Generált”,
  „Kihagyott” és „Hibás” lista (dokumentum-URL-ek, figyelmeztetések,
  tördelési problémák).
- **Kilépési kód:** `0`, ha nincs hibás sor és nincs probléma; `1`, ha bármely
  sor hibás, a visszaírás vagy a nyugta sikertelen, tördelési probléma van,
  vagy a futás hibával állt le (konfiguráció, hitelesítés, API). Dry-run
  esetén `1` hibás profil vagy hibás illesztés esetén.

### Tördelési jelentés

A generálás után a program PDF-be exportálja a dokumentumot, és ellenőrzi a
pozíció- és projektsorokat. Ha egy sor szövege nem található a PDF-ben, több
sorba tört, a részei között a távolság 6 pt-nál kisebb, vagy a középre/jobbra
igazított rész eltér a tabstoptól, a sor „kézi döntés kell” megjegyzéssel
„Tördelési probléma”-ként szerepel az stdoutban és a nyugta `issues`
mezőjében. A dokumentum ilyenkor is megmarad; a sort kézzel kell javítani. Ha
maga az ellenőrzés nem futott le, ez is problémaként jelenik meg.

## Megfeleltetés

| Sablonelem | Profiladat |
| --- | --- |
| Név, titulus | `firstName lastName`, `title` |
| Bemutatkozás | `personalData.introductionThirdPerson`; ha hiányzik, az `introduction` változatlanul, figyelmeztetéssel |
| Languages | `personalData.languages` |
| Programming, Databases, Testing, AI, Cloud | a megfelelő `skills.technical` kategória (Cloud: a felhőszolgáltatók) |
| Frameworks | a teljes `frameworksAndLibraries`; a Libraries sor törlődik |
| DevOps / IaC | `devOpsAndCloud` a felhőszolgáltatók nélkül |
| Other | `toolsAndTechnologies`, `operatingSystems`, `developmentMethodologies`, `specializedDomains` |
| Soft skills | `skills.soft` |
| Pozíciósor | `role`, `companyShortName` (hiányában `company`), `mm/yyyy – mm/yyyy` (folyamatban: `Present`) |
| Projektsor | projektnév és `location`; projektdátum nincs, a helyszín jobbra igazítva |
| Description | minden `responsibilities` elem külön bullet |
| Tech stack | `techStack`; ha nincs, a bullet törlődik |
| Education | **`name`,** `institution` ⇥ dátumok (csak év esetén csak év) |
| Certificates | új H2-szakasz az Education után (oktatás nélkül az Education címsor lesz „Certificates”), az Education-bullet stílusával: **`name`,** `organization` ⇥ `date` |
| Personal Interests | üres `interests` esetén a szakasz törlődik |
| Contact | e-mail és mobilszám (lent); a többi elérhetőség kimarad |

Az üres Skills-sorok törlődnek.

**E-mail:** ha a táblázat `Email` cellája `@moon42.com`-ra végződik, az kerül
a dokumentumba; különben a program származtatja:
`keresztnev.vezeteknev@moon42.com` (a `firstName` első szava, ékezetek
nélkül). Összetett vagy pontot tartalmazó névnél figyelmeztetés kéri a cím
ellenőrzését.

**Mobil:** a YAML `contacts` listájának `mobile` eleme, ennek hiányában a
`phone`, ennek hiányában a táblázat `Mobile` cellája (változatlanul); ha
egyik sincs, a Mobile sor törlődik.

## Technikai tanulságok

- A teljes kitöltés egyetlen `batchUpdate`, `requiredRevisionId`-val védve a
  másolat betöltött revíziójára; így a dokumentum vagy teljesen kitöltött,
  vagy a hiba jelenik meg (a másolat ilyenkor megmarad, URL-jével jelezve).
- A Docs API nem tud tabstopot írni vagy bekezdést másolni, ezért minden új
  sor a sablon megfelelő bekezdésének elejére beszúrt szövegként készül, és
  örökli annak bekezdésstílusát és tabstopjait. Kivételek: a Work
  Experience bulletjei `createParagraphBullets`-szel készülnek, a
  Certificates címsor pedig `updateParagraphStyle`-lal kapja az Education
  címsor stílusát. A régi tartalom
  törlése és a szövegstílusok alkalmazása ugyanebben a batchben történik. A
  kérések a dokumentum végétől az eleje felé haladnak, hogy a korábbi indexek
  érvényesek maradjanak.
- A pozíció- és projektsor tabstopjai (36, 72, 108 pt, középre 261 pt, jobbra
  553 pt) miatt a tabok száma a szöveg szélességétől függ. A tabok számát és
  a középső rész elé tett kitöltő szóközöket a program a rögzített
  (2.138-as, sha256-tal ellenőrzött, `target/gdocs/fonts/` alatt gyorsítótárazott)
  Roboto-metrikából számolja; kerning nélkül, ezért a PDF-ellenőrzés marad az
  utolsó szó.
- A szövegcsere a régi szöveg első karaktere stílusát hordozza; ezért a
  generátor minden futáshoz a sablonból kiolvasott stílust állítja be
  explicit módon a beszúrt szövegekre.
- A Sheets fájlchipje `@` helykitöltő szövegként és `chipRuns` mezővel
  írható; ha ezt a Sheets elutasítja, hiperhivatkozás a tartalék.
- Az API-hívások 429-es és 5xx hibánál legfeljebb 5 kísérlettel, növekvő
  várakozással újrapróbálkoznak.
