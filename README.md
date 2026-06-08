# Ignis v Vulkan

Majhno namizno orodje za mesečni prenos aktivnosti iz Ignisovega Excel izvoza v Vulkan.

## Kaj program dela

- Odpre Ignisov Excel izvoz, na primer `Aktivnosti.xlsx`.
- Uporabi Vulkanov JSON seznam članov za povezovanje imen z `clanId`.
- Omogoča izbiro meseca za prenos.
- Pretvori Ignisove kategorije v Vulkanove vrste dela.
- Izračuna ure članov in jih zaokroži na cele oziroma polovične ure.
- Odpre Vulkan prek ponovno uporabljene prijavljene brskalniške seje.
- Pred ustvarjanjem vsake Vulkan aktivnosti lokalno prikaže pregled.
- Prikaže originalni opis iz Ignisa, da lahko uporabnik opazi dodatno napisane osebe.
- Ustvari Vulkan aktivnost in vrstice članov prek Vulkan POST zahtevkov.
- Lokalno beleži dokončane vrstice, zato se lahko prekinjen mesečni prenos nadaljuje.
- Zgodovino prenesenih vrstic shrani v `local_state/state.json`.

## Namestitev

Najprej naredi lokalno Python okolje in namesti odvisnosti:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.ms-playwright"
.\.venv\Scripts\python.exe -m playwright install chromium
```

Če ukaz `python` ni na voljo v poti, uporabi Python, ki ga običajno uporabljaš.

## Zagon

```powershell
.\.venv\Scripts\python.exe run.py
```

Pri prvem zagonu:

1. Izberi Ignisovo Excel datoteko.
2. Izberi Vulkanovo JSON datoteko članov.
3. Vnesi Vulkan URL. Domača stran je dovolj: `https://apl.gasilec.net/vulkan/home`.
4. Klikni `Start transfer`.
5. Po potrebi se prijavi v Vulkan v odprtem brskalniku.

Program shranjuje samo lokalno stanje seje/profila in napredek prenosa. Gesla ne shranjuje.

## Datoteka članov

V repozitoriju je samo primer datoteke članov:

```text
sample_vulkan_members.json
```

Ta datoteka vsebuje izmišljena imena in je namenjena samo temu, da lahko drugi vidijo obliko podatkov.
Program je ne bo uporabil za pravi prenos v Vulkan.

Prava datoteka z dejanskimi člani mora ostati samo na tvojem računalniku:

```text
vulkan_members.json
```

Ta datoteka je v `.gitignore`, zato se ne sme naložiti na GitHub.

## Opombe

- Preverjanje podvojenih aktivnosti v Vulkanu namenoma ni vključeno.
- Prenos opreme v prvi različici ni vključen.
- Člani, ki jih ni v Vulkanu, so prikazani in zabeleženi, nato pa preskočeni.
- Trenutni prenos uporablja Vulkan POST zahtevke prek prijavljene brskalniške seje, ne klikanja potrditvenih polj.
