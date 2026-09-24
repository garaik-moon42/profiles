# Flat renderer

A YAML-profilból könnyen másolható, UTF-8 szövegfájlt készít. Minden sor egy
mező útvonalát és értékét tartalmazza, egy tabulátorral elválasztva, fejléc nélkül.
A [közös rendererszabályok](../README.md) erre a generátorra is érvényesek.

## Futtatás

Python 3 és PyYAML szükséges. A függőség telepítése és a futtatás a repo gyökeréből:

```bash
python3 -m pip install -r renderer/flat/requirements.txt
python3 renderer/flat/render.py profiles/kalindu-don-sekarage.yaml
```

Az eredmény: `target/flat/kalindu-don-sekarage.flat.txt` a repo gyökeréhez képest.
A program kiírja az elkészült fájl útvonalát. Más munkakönyvtárból is futtatható,
ha a program és a bemenet útvonalát ennek megfelelően adod meg.
Azonos bemeneti fájlnév esetén a korábbi kimenetet felülírja.

## Formátum

- Az objektumok mezőit pont választja el: `personalData.firstName`.
- Az objektumokat tartalmazó listákat nullától indexeli: `experience[0].company`.
- Az egyszerű értékek listája egy sorba kerül, vessző és szóköz választja el
  az elemeket: `Go, Java, Kotlin`.
- Megőrzi a mezők és listaelemek bemeneti sorrendjét.
- A `null` érték szövege `null`, a logikai értékeké `true` és `false`.
- Üres listánál a tab után üres érték szerepel; üres objektumnál `{}`.
- Az értékekben lévő sortöréseket és tabokat szóközre cseréli, hogy egy mező
  egy sorban maradjon és könnyen másolható legyen.
- A YAML-kommenteket, így a TODO-kat és levéltervezeteket nem jeleníti meg.

A formátum kézi másoláshoz készült; a vesszőket tartalmazó listaelemeket nem
idézőjelezi külön, ezért nem veszteségmentes adatcsere-formátum.

Hiányos munkapéldányok is renderelhetők: a program nem végez profil-sémavalidálást,
csak a fájlban szereplő adatokat írja ki. Hibás YAML, ismétlődő kulcs vagy
feldolgozási hiba esetén hibajelzéssel és nem nulla kilépési kóddal áll le.
