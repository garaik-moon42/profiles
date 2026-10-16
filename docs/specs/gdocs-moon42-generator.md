# MOON42 Google Docs-profilgenerátor
Status: approved
Source: docs/ideas/gdocs-moon42-generator.md
Decision log: docs/specs/gdocs-moon42-generator.decisions.md

## Goal

A `renderer/gdocs/tesla_candidates.py` a „_TESLA Candidates” táblázat alapján egy
futásban elkészíti a soron következő jelöltek MOON42-profilját Google Docsban,
a „_TEMPLATE - MOON42” sablon másolatából, a YAML-profil tartalmával, kézi
utómunka nélkül átadható formában, majd a doksit beírja a táblázatba. Ahol a
tördelés kézi döntést igényel, ezt egyértelműen jelzi. A dokumentumot a
`renderer/gdocs/render.py` alap generátor állítja elő, amely önállóan is
futtatható egy profilfájlra és egy tetszőleges Drive-mappára.

## Users & Use Cases

- **Felhasználó:** a jelölteket kezelő munkatárs (egyetlen felhasználó, saját
  Google-fiókkal, helyi gépen futtatva).
- **UC-1 – Új profilok:** a felhasználó új jelöltet vesz fel „in progress”
  státusszal, üres MOON42 Profile cellával, és elkészül a YAML-profil. A
  futtatás után a cellában a kész doksi chipje áll.
- **UC-2 – Újragenerálás:** a felhasználó kitörli egy jelölt MOON42 Profile
  celláját (pl. a YAML javítása után); a következő futás új doksit készít. A
  régi doksit a felhasználó maga kezeli.
- **UC-3 – Előnézet:** `--dry-run` megmutatja, kiknek készülne doksi, és
  melyik YAML-ből, írás nélkül.
- **UC-4 – Egy profil tetszőleges mappába:** a felhasználó egy YAML-profilból
  a táblázattól függetlenül készít doksit egy általa megadott Drive-mappába
  (pl. tesztmappába).

## Scope

**In:**
- Táblázatvezérelt kötegelt futás, `--dry-run` mód.
- Egyfájlos alap generátor (`render.py <profil.yaml> <mappaazonosító>`),
  amelyet a táblázatvezérelt futás is használ.
- Sablonmásolás a célmappába, kitöltés a jóváhagyott megfeleltetés szerint.
- Tabszámítás fontmetrikával, automatikus PDF-alapú tördelésellenőrzés.
- A MOON42 Profile cella kitöltése Drive file chippel.
- Két opcionális sémamező (`personalData.introductionThirdPerson`,
  `experience[].companyShortName`), és ezek kitöltése Bence YAML-jében a kézi
  referencia alapján.
- OAuth-scope-bővítés, `config.yaml` bővítése, README-k frissítése.
- Unit tesztek a determinisztikus logikára.

**Out:**
- Meglévő doksik frissítése vagy törlése (a régi és a kézzel létrehozott üres
  sablonmásolatokat a felhasználó kezeli).
- A táblázat bármely más cellájának, a Status oszlopnak és a „Log” fülnek a
  módosítása.
- Hiányzó YAML-adatok pótlása, a harmadik személyű bemutatkozás és a rövid
  cégnevek megírása (más profiloknál ez szerkesztői feladat a YAML-ben).
- PDF mint leszállítandó kimenet (a PDF csak ellenőrzésre szolgál).
- A `flat` és a LaTeX renderer változtatása.
- Futtatás szerveren, ütemezve vagy CI-ban.

## Affected Areas

- `renderer/gdocs/render.py` – újraírás (jelenleg „Hello World” doksit hoz
  létre): az egyfájlos alap generátor. Szükség szerint további modulok a
  `renderer/gdocs/` alatt.
- `renderer/gdocs/tesla_candidates.py` – a táblázatvezérelt generátor.
- `renderer/gdocs/config.yaml` – `targetFolderId` a „MOON42 Profiles”
  mappára; új kulcsok: `templateId`, `spreadsheetId`.
- `renderer/gdocs/requirements.txt` – PDF-szövegkinyerő és fontmetrika-függőség.
- `renderer/gdocs/README.md`, `renderer/README.md` – futtatás, scope-ok,
  konfiguráció; a TESLA Candidates generátor kivétel az „egy bemeneti fájl”
  szabály alól.
- `schemas/profile.schema.json` – két opcionális mező.
- `profiles/bence-berenyi.yaml` – az új mezők kitöltése a referencia alapján.
- Új: `renderer/gdocs/tests/` (stdlib `unittest`).

## Functional Requirements

### Futtatás és konfiguráció
- **FR-1:** Indítás: `.venv/bin/python renderer/gdocs/tesla_candidates.py
  [--dry-run] [--config <path>]`. Bemeneti fájlparamétert nem kap. A `--config`
  alapértéke `renderer/gdocs/config.yaml`; más fájllal (pl. teszt-táblázat és
  -mappa) ugyanazok a szabályok érvényesek. A konfiguráció kötelező kulcsai:
  `targetFolderId`, `templateId`, `spreadsheetId`. Hiányzó, üres vagy `null`
  érték: `Hiba: …`, exit 1, semmilyen API-írás nélkül. Az egyfájlos módot az
  FR-22 írja le.
- **FR-2:** OAuth-scope-ok: `drive.file`, `drive.readonly`, `spreadsheets`. Ha
  a mentett token scope-jai ettől eltérnek, a program új jóváhagyást kér (a
  régi token nem okozhat hibát). A build első munkacsomagja élesben
  ellenőrzi, hogy `drive.readonly` mellett a sablon másolható-e; ha nem, a
  build megáll, és a felhasználó dönt (automatikus váltás a teljes `drive`
  scope-ra nincs).

### Táblázat mint munkasor
- **FR-3:** A program a táblázat „Candidates” fülét olvassa, az oszlopokat a
  fejléc neve alapján azonosítja (`Name`, `Status`, `Mobile`, `Email`,
  `MOON42 Profile`). Hiányzó fejléc: `Hiba: …`, exit 1.
- **FR-4:** Jogosult sor: a `Status` trimmelve, kis- és nagybetűtől függetlenül
  `in progress`, és a `MOON42 Profile` cella üres vagy csak szóközt tartalmaz
  (chip, link vagy szöveg esetén nem üres). Minden más sort figyelmen kívül
  hagy.
- **FR-5:** Sor–profil párosítás: a `profiles/*.yaml` közül az a profil
  illeszkedik, amelynek `firstName` + `lastName` tokenjei (ékezet- és
  kisbetű-függetlenül, szóközök, pontok és kötőjelek mentén bontva)
  tartalmazzák a sor `Name` értékének minden tokenjét. Pontosan egy illeszkedés
  → az a profil; nulla vagy több → a sor kihagyva, az összesítő okkal együtt
  jelzi. Teljes illeszkedés híján, de legalább egy közös tokennél az összesítő
  figyelmeztet, és felsorolja a jelölt profilokat. Ha két jogosult sor
  ugyanarra a profilra illeszkedik, mindkettő hibaként kimarad (exit 1).
- **FR-6:** `--dry-run`: kiírja a jogosult sorokat (sorszám, név), a párosított
  profilazonosítót vagy a kihagyás okát, a leendő doksinevet és a DRAFT
  jelölést. Semmit nem hoz létre, nem ír a Drive-ra, a táblázatba és a
  `target/` alá (a token kivételével).

### Dokumentum előállítása
- **FR-7:** Jelöltenként a sablon másolata jön létre a `targetFolderId`
  mappában `{firstName} {lastName} - MOON42` néven (a YAML teljes nevével). A
  sablont a program csak olvassa és másolja.
- **FR-8:** A kitöltés a `renderer/gdocs/README.md` „Megfeleltetés” táblázatát
  követi; ez normatív. Kiegészítések és pontosítások:
  - Bemutatkozás: `personalData.introductionThirdPerson`, ha van; különben az
    `introduction` változatlanul, figyelmeztetéssel az összesítőben.
  - Pozíciósor cége: `experience[].companyShortName`, ha van; különben a
    `company`.
  - E-mail: a sor `Email` értéke, ha `@moon42.com`-ra végződik; különben
    `<firstName első tokenje>.<lastName>@moon42.com`, kisbetűvel, ékezet
    nélkül, a betűkön kívüli karakterek elhagyásával. Származtatott címnél,
    ha a `firstName` vagy a `lastName` több tokenből áll vagy pontot
    tartalmaz, az összesítő és a nyugta figyelmeztet („ellenőrizd a
    címet”); a valódi címet a felhasználó a táblázat Email oszlopába írja.
  - Mobil: a YAML `mobile` típusú elérhetősége, ennek híján a `phone`
    típusú; ha egyik sincs, a sor `Mobile` értéke (formázott értékként
    olvasva); ha az sincs, a Mobile sor törlődik. Ha a YAML-ben és a
    táblázatban is van szám, a YAML nyer. Az érték szó szerint kerül át,
    normalizálás nélkül.
  - Certificates: új H2 „Certificates” szakasz közvetlenül az Education után,
    az Education címsorának és bulletjének stílusával klónozva; üres
    `certificates` esetén elmarad.
- **FR-9:** Dátumok: `YYYY/MM` → `mm/yyyy`; `YYYY` → `yyyy` (kitalált hónap
  nélkül); `end: null` → `Present`. Tartomány: `<start> – <end>`.
  Hiányzó rész (pl. Education-sorban `institution`, `start` vagy `end`) a
  hozzá tartozó elválasztóval (vessző, tab, gondolatjel) együtt marad el;
  lógó írásjel nem maradhat. A generátor nem validál a sémára, azt rendereli,
  ami a YAML-ben van.
- **FR-10:** Szerkezet: a sablon formázása (stílusok, színek, betűméretek,
  felsorolások, tabstopok) megmarad. A felesleges pozíció-, projekt-, bullet-,
  Skills- és szakaszelemek törlődnek, a hiányzók a meglévő blokk mintájára
  (azonos stílussal) jönnek létre. Üres opcionális adat → a sor vagy szakasz
  törlődik a megfeleltetés szerint.
- **FR-11:** A kész doksiban nem marad sablonszöveg, sárga kiemelés és „TODO”.
  A YAML-kommentek (DRAFT-fejléc, TODO-k) sosem kerülnek a doksiba.
- **FR-12:** Draft profilok (`# DRAFT` fejléc) ugyanúgy renderelődnek; a
  doksi neve nem kap utótagot, a DRAFT jelölés csak az összesítőben és a
  nyugtában (`draft: true`) jelenik meg.

### Tördelés
- **FR-13:** A pozíció- és projektsorok tabjainak számát a program a sablon
  fontjának metrikáival mért szövegszélességből számolja, a sablon tabstopjai
  (36, 72, 108 pt; középre 261 pt; jobbra 553 pt) szerint, a 12 pt félkövér
  és a 10 pt normál/félkövér futásokat külön metrikával. A metrikához használt
  Roboto-fájlok rögzítettek (fix letöltési URL + sha256 a kódban). Automatikus
  korrekciós kör nincs: a tabszámítás egyszer fut, utána ellenőrzés és
  jelentés.
- **FR-14:** Kitöltés után a program PDF-be exportálja a doksit, és
  ellenőrzi, hogy minden pozíció- és projektsor egy sorban maradt, és a
  szövegrészek nem érnek össze. Hiba esetén a doksi és a chip megmarad, az
  összesítő soronként listázza a problémát („kézi döntés kell”), és a futás
  exit 1-gyel zárul.

### Visszaírás és kimenet
- **FR-15:** Sikeres generálás után a program újraolvassa a sort, és csak
  akkor ír a `MOON42 Profile` cellába, ha ugyanazon a sorszámon még ugyanaz a
  `Name` áll, és a cella még üres (a sort nem keresi újra): a doksira mutató
  Drive file chipet (ha a Sheets API ezt nem engedi, hiperhivatkozást a doksi
  nevével). Más cellát nem ír. Ha a név eltér vagy a cella időközben megtelt,
  nem ír, és az összesítő jelzi a doksi URL-jével.
- **FR-16:** A jelöltek feldolgozása egymástól független: egy jelölt hibája
  (nincs vagy több illeszkedő YAML, hibás YAML, API-hiba) után a futás
  folytatódik. Hibás jelöltnél nincs táblázatírás; a már létrejött doksi
  megmarad, és az összesítő az URL-jét is közli.
- **FR-17:** Nyugta jelöltenként: `target/gdocs/<profilazonosító>.json`
  (`documentId`, `name`, `url`, `parentFolderIds`, `sheetRow` (csak a
  táblázatvezérelt futásnál), `draft`,
  `issues`: figyelmeztetések és tördelési problémák, `previousDocuments`:
  a korábbi generálások `documentId` + `url` párjai, újrageneráláskor
  bővítve). A problémákat későbbi futás nem jelenti újra. Futási
  összesítő a stdout-ra: generált / kihagyott / hibás jelöltek okkal és
  URL-lel, figyelmeztetések, tördelési problémák.
- **FR-18:** Exit kód: 0, ha minden jogosult jelölt hibátlanul és tördelési
  probléma nélkül elkészült (vagy nem volt jogosult jelölt); 1 egyébként.
  Párosítatlan sor kihagyása önmagában nem hiba (lásd Key Decisions).

### Séma és dokumentáció
- **FR-19:** A `schemas/profile.schema.json` két opcionális string mezőt kap:
  `personalData.introductionThirdPerson`, `experience[].companyShortName`. A
  `schemaVersion` marad `1.0` (visszafelé kompatibilis bővítés).
- **FR-20:** `profiles/bence-berenyi.yaml` megkapja a kézi referencia
  bemutatkozását (`introductionThirdPerson`, szó szerint a referenciából) és a
  Jofogas-pozíció rövid cégnevét (`companyShortName: Jofogas.hu /
  Hasznaltauto.hu`); a másik két pozíció a referenciában is teljes néven áll.
- **FR-21:** A `renderer/gdocs/README.md` leírja a futtatást, a `--dry-run`-t,
  a scope-okat, a konfigurációt és a tördelési jelentést; a „Hello World”
  szöveg és az elavult tervek kikerülnek. A `renderer/README.md` jelzi, hogy a
  TESLA Candidates generátor a táblázatból dolgozik.

### Egyfájlos mód (alap generátor)
- **FR-22:** Indítás: `.venv/bin/python renderer/gdocs/render.py
  <profil.yaml> <mappaazonosító> [--config <path>]`. Egy profilból egy doksit
  készít a megadott Drive-mappába az FR-7–FR-14 szerint; a táblázatot nem
  olvassa és nem írja. A konfigurációból csak a `templateId` kötelező; a
  scope-ok és a token azonosak a táblázatvezérelt futáséval. E-mail: a névből
  származtatott `@moon42.com`-cím; mobil: a YAML `mobile`, ennek híján `phone`
  elérhetősége. Nyugta az FR-17 szerint, `sheetRow` nélkül; a stdout a doksi
  URL-jét, a DRAFT jelölést, a figyelmeztetéseket és a tördelési problémákat
  tartalmazza. Exit 1 hibás profil, konfiguráció vagy üres mappaazonosító
  (API-hívás nélkül), sikertelen generálás, tördelési probléma vagy sikertelen
  nyugtaírás esetén; egyébként 0.
- **FR-23:** A táblázatvezérelt generátor minden párosított sorra az alap
  generátor függvényét hívja (`targetFolderId`, a sor `Email` és `Mobile`
  értéke, sorszám); a generálás logikája csak az alap generátorban van.

## Non-Functional Requirements

- **NFR-1 – Sablonvédelem:** a sablonra csak olvasó és másoló hívás mehet.
- **NFR-2 – Atomikus kitöltés:** a doksi tartalmi kitöltése revízióval védett
  (`requiredRevisionId`) `batchUpdate`-tel történik.
- **NFR-3 – Titkok:** `credentials.json` és `token.json` a helyükön marad,
  gitignored; konfigurációba, logba, nyugtába nem kerül hitelesítési adat.
- **NFR-4 – Üzenetek:** a felhasználói üzenetek magyarok, a hibák a meglévő
  `Hiba: …` formában a stderr-re mennek.
- **NFR-5 – Újrapróbálás:** 429/5xx válasznál hívásonként legfeljebb 5
  próbálkozás exponenciális visszalépéssel (összesen kb. 60 s). A `--dry-run`
  ugyanazt a tokent és scope-készletet használja, mint a normál futás.
- **NFR-6 – Függőségek:** csak a `renderer/gdocs/requirements.txt`-ben,
  verziótartománnyal; tesztkeretrendszer a stdlib `unittest`.
- **NFR-7 – Kód:** a tiszta logika (dátum, e-mail, párosítás, jogosultság,
  skill-kategóriák szétválasztása, tabszámítás, PDF-sorelemzés) API nélkül,
  unit tesztelhetően különül el.

## Key Decisions

- **Táblázatvezérelt kötegelt futás** — a táblázat a munkasor; a „csak
  üres cella” szabály teszi idempotenssé az újrafuttatást. Elvetve: egyfájlos
  CLI (az ötletfájl és a `renderer/README.md` szabálya; a felhasználói döntés
  felülírja), mindig új doksi.
- **Alap generátor + táblázatvezérelt generátor** (2026-10-16) — a
  generátor két belépési pontra vált: az egyfájlos `render.py` bármely
  mappába generál, a `tesla_candidates.py` ezt hívja, így nincs funkcionális
  duplikáció. Ez visszahozza az eredetileg elvetett egyfájlos CLI-t, a
  táblázatvezérelt futás változatlan marad.
- **Sor–YAML párosítás tokenrészhalmazzal** — minden mostani sort helyesen
  párosít, új oszlop nélkül. Elvetve: profilazonosító-oszlop a táblázatban.
- **Párosítatlan sor nem hiba** — a táblázatban vannak YAML nélküli „in
  progress” jelöltek (pl. még nincs profiljuk); ezek kihagyása a normál állapot,
  az összesítő listázza őket.
- **Scope-ok: `drive.file` + `drive.readonly` + `spreadsheets`** — a sablon
  olvasása és a táblázat írása mást nem enged. Ha a másolás így nem megy, a
  build megáll, és a felhasználó dönt; nincs automatikus fallback a teljes
  `drive` scope-ra.
- **Tesztkörnyezet `--config`-gal** — a fejlesztési és AC-7 futások a táblázat
  másolatán és egy tesztmappán mennek; élesben csak a végső elfogadás.
  Elvetve: tesztelés az éles táblázaton (elvesznének a kézi chipek).
- **Draftok névutótag nélkül** — az átadásról a felhasználó dönt; a jelölés a
  nyugtában és az összesítőben van. Elvetve: „- DRAFT” utótag.
- **Elérhetőség a táblázatból is** — a mobil YAML-hiány esetén és a
  `@moon42.com` e-mail a táblázatból jön; tudatos kivétel a „csak
  YAML-tartalom” szabály alól, a forrás a felhasználó saját adata.
- **Fontmetrikás tabszámítás + PDF-ellenőrzés** — csak ez adja a referenciával
  egyező megjelenést. Elvetve: egyetlen jobbra igazított tab (eltér a
  referenciától), karakterszám-heurisztika (nem észleli a hibát).
- **Szerkesztői szöveg opcionális sémamezőkben** — a tartalom a YAML-ben marad,
  determinisztikus. Elvetve: gdocs-override fájl (két helyen élő adat),
  szabály- vagy LLM-alapú átírás (törékeny, fizetős, nem determinisztikus).
- **Draftok is renderelődnek** — a felhasználó döntése; a hiányzó adat sora
  törlődik.
- Stack, futtatás, nyugtahely, hibaformátum: mint a projektben.

## Constraints

- Python 3, a repo gyökerében lévő `.venv`; Fedora, felhasználói térben.
- A sablon (`1MdRqUIGpKxIVUKjNMxMoj6jOi7P5p6ch-GQwQQfdTf4`) soha nem módosul.
- Táblázat: `1dz4PE6uPZiUcCC6J7xuM7INf8GLvTcuXQft49MISWDk`, „Candidates” fül;
  a felhasználó párhuzamosan szerkeszti.
- Célmappa: „MOON42 Profiles” (`149J47yBwm5ZAh5Yp4HKzb57I9VIErERL`).
- Kézi referencia: Bence Berényi doksija
  (`1d8zfI1AEJjU2mx82ekGDIJhwEVQMq-B9YYzAIW9Z8Yg`).
- Sablon: Letter oldalméret, Roboto (törzs 10 pt, pozíciócím 12 pt félkövér),
  pozíció- és projektsor tabstopjai: középre ~261 pt, jobbra ~553 pt. A
  fontmetrikához a Roboto szabadon letölthető (Google Fonts); a font a
  `target/` alatt cache-elhető, a repóba nem kerül.
- Éles futás a valódi táblázaton és mappán csak a felhasználó jóváhagyásával;
  a cellák kiürítése a felhasználó lépése, előtte a régi chipek URL-jei
  mentésre kerülnek. Fejlesztés és AC-7: a táblázat másolata és egy tesztmappa
  (a felhasználó hozza létre, vagy az agent a jóváhagyásával), a teszt-konfig
  a `target/` alatt (gitignored).
- Az OAuth consent screen módja (Internal vagy External/Testing) még nincs
  rögzítve; External/Testing módban a refresh token 7 nap után lejár, ezt a
  README-nek jeleznie kell.

## Acceptance Criteria

- **AC-1 (dry-run):** `tesla_candidates.py --dry-run` a mostani táblázatra kilistázza a
  jogosult sorokat, párosításukat vagy a kihagyás okát; utána a táblázat
  értékei és a célmappa fájllistája változatlan, a `target/gdocs/` alatt nincs
  új nyugta.
- **AC-2 (referencia, tartalom):** Bence celláját kiürítve a futás új doksit
  hoz létre a célmappában „Bence Berényi - MOON42” néven, amelynek szöveges
  exportja megegyezik a kézi referencia szöveges exportjával, a whitespace-futások
  (tabok, szóközök) egyetlen szóközre normalizálása után. (A referenciában a
  tabigazítás kézi szóközökkel készült, ezt a generátornak nem kell szó szerint
  másolnia.)
- **AC-3 (referencia, megjelenés):** a generált és a referencia doksi
  PDF-exportja: azonos oldalszám és szakaszsorrend; minden pozíció- és
  projektsor egy sorban (PDF-ellenőrzés); a dátumok jobb széle a referenciához
  képest ±2 pt-on belül. A maradékot (betűtípus és -méret, színek,
  felsorolások) egy friss kontextusú verifier agent ítéli egyezőnek.
- **AC-4 (sablon):** a sablon `modifiedTime`-ja és revíziója a futás előtt és
  után azonos.
- **AC-5 (visszaírás):** Bence `MOON42 Profile` cellájában a generált doksira
  mutató file chip áll; a táblázat minden más cellája változatlan.
- **AC-6 (idempotencia):** azonnali második futás nem hoz létre doksit, nem ír
  a táblázatba, exit 0.
- **AC-7 (összes profil):** a teszt-táblázatban (az éles másolata) a 13
  párosítható „in progress” jelölt celláját kiürítve a futás mindegyikhez doksit készít; egyikben sincs sablonszöveg,
  sárga kiemelés vagy „TODO” (Docs API-s ellenőrzés); a YAML nélküli sorok
  (pl. Hrubi, Polena, Robár, Fekete) kihagyottként szerepelnek az
  összesítőben, celláik változatlanok; a draftok DRAFT jelölést kapnak; a
  tördelési problémák (ha vannak) soronként listázva, az exit kód FR-18 szerint.
- **AC-8 (párhuzamos szerkesztés):** ha a cella a generálás és a visszaírás
  között megtelik (unit teszt Sheets-hamisítvánnyal), a program nem írja felül,
  és jelzi.
- **AC-9 (tördelésellenőrzés):** a PDF-sorelemző egy szándékosan túl hosszú
  cégnevű fixture-PDF-en jelzi a hibás sort, a referencia PDF-en nem jelez.
- **AC-10 (unit tesztek):** `python -m unittest discover renderer/gdocs/tests`
  zöld, és lefedi: dátumformázás (`YYYY/MM`, `YYYY`, `null`), e-mail
  (`Berényi Bence` → `bence.berenyi@moon42.com`, táblázatbeli `@moon42.com`
  elsőbbsége, figyelmeztetés többtagú vagy pontos névnél), mobil-fallback, jogosultság (szóközös cella, státusz-variánsok),
  párosítás (a táblázat minden mostani nevére, nulla és több illeszkedés),
  Cloud/DevOps szétválasztás, tabszámítás.
- **AC-11 (séma):** Bence YAML-je és az összes nem-draft profil érvényes a
  bővített sémára (`jsonschema`-ellenőrzés egyszeri futtatással), és a `flat`
  renderer Bence profiljára hiba nélkül lefut.
- **AC-12 (konfiguráció és scope):** hiányzó `templateId` vagy
  `spreadsheetId` esetén `Hiba: …`, exit 1, API-hívás nélkül; régi
  (`drive.file`-only) tokennel a program új jóváhagyást kér, nem hibával áll
  le.
- **AC-13 (egyfájlos mód):** `render.py <profil.yaml> <tesztmappa>` a
  tesztmappába hozza létre a doksit, a táblázat változatlan, a nyugtában nincs
  `sheetRow`, exit 0; hibás profil vagy üres mappaazonosító esetén `Hiba: …`,
  exit 1, API-hívás nélkül. A táblázatvezérelt futás unit tesztjei
  változatlan elvárásokkal zöldek.

## Open Questions

(nincs)
