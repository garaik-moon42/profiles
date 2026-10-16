# Rendererek

A rendererek a YAML-profilokból megjelenítésre vagy további feldolgozásra
alkalmas kimenetet készítenek. Minden renderer saját alkönyvtárban található.

## Közös szabályok

- Minden generátor parancssorból is futtatható program.
- Egy bemeneti fájl elérési útját kapja paraméterül, és ebből készíti el a kimenetet.
- A kimenetek a repo gyökerében található `target/<renderer neve>/` könyvtárba
  kerülnek, például `target/flat/` vagy `target/gdocs/` alá.
- A kimeneti könyvtár helye a futtatás munkakönyvtárától független.
- A generátor szükség esetén létrehozza a saját kimeneti könyvtárát.

## Generátorok

- [flat](flat/README.md): tabbal elválasztott útvonal–érték párok szövegfájlban.
- [gdocs](gdocs/README.md): MOON42 Google Docs-dokumentumok előállítása. Kivétel
  az „egy bemeneti fájl” szabály alól: a „_TESLA Candidates” táblázatból
  dolgozik, a profilokat a `profiles/` könyvtárból olvassa.
