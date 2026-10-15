# Ötlet: MOON42 Google Docs-profil generálása YAML-ból

## Háttér

A `renderer/gdocs` jelenleg csak egy „Hello World!” dokumentumot hoz létre.
2026-10-15-én egy agent kézzel, a Google Docs connectorral kitöltötte Berényi
Bence MOON42-profilját a `profiles/bence-berenyi.yaml` alapján
([eredmény](https://docs.google.com/document/d/1d8zfI1AEJjU2mx82ekGDIJhwEVQMq-B9YYzAIW9Z8Yg/edit)).
A kísérlet működött, de profilonként lassú, és a tördelési hibák minden
profilnál újra előjönnek. A maradék kb. 12 profilt ezért generátorral szeretném
elkészíteni, nem kézzel.

## Mit szeretnék

A `renderer/gdocs/render.py profiles/<id>.yaml` parancs készítsen kész,
kézi utómunka nélkül átadható MOON42-profilt Google Docsban:

- A „_TEMPLATE - MOON42” sablon
  (`1MdRqUIGpKxIVUKjNMxMoj6jOi7P5p6ch-GQwQQfdTf4`) másolatából induljon, és a
  dokumentum neve `{firstName} {lastName} - MOON42` legyen. A sablont soha nem
  módosíthatja.
- A kitöltés a `renderer/gdocs/README.md` „Tapasztalatok a MOON42-sablon kézi
  kitöltéséből” szakaszában rögzített megfeleltetést kövesse. Ez a kézi
  kísérletben jóváhagyott leképezés, a generátornak ugyanazt az eredményt kell
  adnia.
- A sablon formázása (stílusok, színek, betűméretek, felsorolások, tabstopok)
  maradjon meg. A felesleges pozíció-, projekt- és Skills-sorok törlődjenek, a
  hiányzók a meglévő blokkok mintájára jöjjenek létre.
- Ne maradjon benne sablonszöveg, sárga kiemelés vagy „TODO”.
- Dátumok: `mm/yyyy`, folyamatban `Present`; csak évet tartalmazó dátumból ne
  legyen kitalált hónap.
- Csak a YAML-ben szereplő tartalom kerülhet bele. A bemutatkozás harmadik
  személyű átírása a kézi kísérletben szerkesztői lépés volt; a generátornál el
  kell dönteni, hogyan kezeljük (lásd nyitott kérdések).
- A futás a meglévő közös rendererszabályokat kövesse (`renderer/README.md`):
  egy bemeneti fájl, nyugta a `target/gdocs/` alá.

## Amit a kézi kísérletből tudunk

- A sablon fix szerkezetű, indexekkel címezhető. A stílusmegtartó csere
  bevált: a régi szöveg első karaktere után beszúrni, majd a régit törölni.
  A teljes kitöltés egyetlen, revízióval védett `batchUpdate` volt.
- A pozíció- és projektsorok tabstopokkal igazítanak (36, 72, 108 pt, középre
  261 pt, jobbra 553 pt). Hosszú pozíció-, cég- vagy projektnévnél a szöveg
  összeér, vagy a dátum új sorba törik. Ezt csak a renderelt PDF mutatta meg; a
  kísérletben kézzel kellett tabot, szóközt és rövidebb cégnevet beállítani.
- A PDF-export (Drive API) működik, alkalmas vizuális ellenőrzésre.
- Az e-mail mindig a MOON42-es cím: `keresztnev.vezeteknev@moon42.com`,
  ékezetek nélkül, akkor is, ha a YAML-ben más cím szerepel.

## Elvárt eredmény

- Berényi Bence profiljára a generált dokumentum tartalmában és megjelenésében
  egyezzen a kézzel készítettel.
- A többi profilra is fusson le hiba nélkül, és a kimenet tördelése legyen
  rendben (vagy a generátor jelezze egyértelműen, hol kell kézi döntés).

## Nyitott kérdések a spechez

- **Hitelesítés:** a renderer most csak `drive.file` scope-ot kér, ami nem fér
  hozzá a sablonhoz, mert azt nem az alkalmazás hozta létre. Szélesebb scope
  kell, vagy más megoldás?
- **Célmappa:** a `config.yaml` `targetFolderId` mappája vagy a „MOON42
  Profiles” mappa (`149J47yBwm5ZAh5Yp4HKzb57I9VIErERL`)?
- **Újrafuttatás:** ha a profilhoz már van dokumentum (pl. a nyugtában vagy a
  „_TESLA Candidates” táblázatban), frissítse azt, vagy mindig újat hozzon létre?
  Kézzel már létrehozott, üres sablonmásolatok is vannak.
- **Tördelés:** a tabok számát a generátor becsülje (szövegszélesség-mérés),
  vagy legyen egyszerűbb, robusztus elrendezés? Kell-e automatikus PDF-ellenőrzés?
- **Szerkesztői szöveg:** a bemutatkozás harmadik személyű változata hol
  készüljön (új YAML-mező, renderelési szabály, kézi lépés)? Hosszú cégneveknél
  ki dönt a rövidítésről?
- **Munkapéldányok:** mi történjen a TODO-kat tartalmazó, nem végleges
  profilokkal?
- **Táblázat:** a generátor frissítse-e a „_TESLA Candidates” táblázat MOON42
  Profile oszlopát, vagy az kívül esik a feladaton?
