# Poročilo projekta: Orodje za prenos aktivnosti iz Ignisa v Vulkan

## 1. Uvod

Ta projekt je namizno orodje, ki pomaga pri mesečnem prenosu gasilskih aktivnosti iz sistema Ignis v sistem Vulkan. Ignis se uporablja kot izvorni sistem, ker omogoča izvoz aktivnosti v Excelovo datoteko. Vulkan je ciljni sistem, v katerega se vpisujejo aktivnosti, ure in sodelujoči člani organizacije.

Glavni cilj projekta je zmanjšati ročno prepisovanje, preprečiti napake pri tipkanju in pohitriti mesečni prenos aktivnosti. Program kljub avtomatizaciji uporabniku še vedno omogoča pregled vsake aktivnosti pred oddajo.

## 2. Opis problema

Pred izdelavo tega orodja je bil prenos aktivnosti večinoma ročen. Uporabnik je moral prebrati vsako aktivnost v Ignisu, izbrati ustrezno vrsto dela v Vulkanu, vnesti datum in naslov, izračunati trajanje, poiskati člane v Vulkanu in vse skupaj shraniti.

Tak postopek je bil počasen in dovzeten za napake, ker:

- se aktivnosti prenašajo mesečno in jih je lahko veliko,
- Ignis in Vulkan uporabljata različna imena kategorij,
- nekateri člani iz Ignisa ne obstajajo v Vulkanu,
- Vulkan sam ne prepreči podvojenih vnosov,
- avtomatizacija spletnega vmesnika ni bila zanesljiva, ker je Vulkan dinamična spletna aplikacija.

## 3. Končna rešitev

Končna različica uporablja namizno aplikacijo v Pythonu s knjižnico Tkinter. Namesto klikanja po obrazcih in potrditvenih poljih v Vulkanu program uporablja Vulkanove HTTP POST zahtevke prek že prijavljene brskalniške seje.

Uporabnik vsako aktivnost pred pošiljanjem še vedno pregleda lokalno. V preglednem oknu lahko:

- popravi naslov aktivnosti,
- spremeni vrsto dela prek spustnega seznama,
- vidi originalni opis iz Ignisa,
- vidi trajanje aktivnosti,
- vidi vse zaznane člane,
- odkljuka člane, ki naj se ne oddajo,
- vidi člane, ki jih ni v Vulkanu, označene z modro barvo.

Če kategorija iz Ignisa ni prepoznana, je vrstica v seznamu označena z rdečo barvo. Aktivnosti v tem primeru ni mogoče oddati, dokler uporabnik ne izbere veljavne vrste dela v Vulkanu.

## 4. Delovanje programa

1. Uporabnik izbere Excelov izvoz iz Ignisa.
2. Uporabnik izbere mesec in leto za prenos.
3. Program prebere Excelove vrstice in izbere aktivnosti za izbrani mesec.
4. Kategorije iz Ignisa se pretvorijo v vrste dela v Vulkanu.
5. Program izračuna trajanje aktivnosti in ure zaokroži na cele oziroma polovične ure.
6. Sodelujoči se izluščijo iz besedila v stolpcu za sodelujoče.
7. Program imena članov poveže z Vulkanovimi `clanId` vrednostmi iz lokalne datoteke `vulkan_members.json`.
8. Za vsako aktivnost se prikaže pregledno okno.
9. Po potrditvi program pošlje POST zahtevek za ustvarjanje aktivnosti v Vulkanu.
10. Nato pošlje še POST zahtevek za vsakega ujemajočega se člana.
11. Uspešno prenesene vrstice se shranijo v lokalno zgodovino, da jih je mogoče pri naslednjem zagonu preskočiti.

## 5. Datoteke, potrebne za delovanje glavnega programa

Za normalno uporabo glavnega orodja so potrebne te datoteke in mape:

- `run.py` - zažene namizno aplikacijo.
- `ignis_vulkan/__init__.py` - označuje mapo kot Python paket.
- `ignis_vulkan/app.py` - namizni uporabniški vmesnik Tkinter.
- `ignis_vulkan/api.py` - pošiljanje Vulkan POST zahtevkov.
- `ignis_vulkan/history.py` - lokalne nastavitve in zgodovina prenesenih vrstic.
- `ignis_vulkan/members.py` - nalaganje članov in povezovanje imen z `clanId`.
- `ignis_vulkan/models.py` - skupne podatkovne strukture.
- `ignis_vulkan/transform.py` - branje Excela, pretvorba kategorij, trajanje in razčlenjevanje sodelujočih.
- `vulkan_members.json` - zasebni seznam Vulkan članov in njihovih ID-jev; ta datoteka ostane samo na uporabnikovem računalniku.
- `sample_vulkan_members.json` - javni primer oblike datoteke članov z izmišljenimi imeni.
- `.venv/` - lokalno Python okolje z nameščenimi knjižnicami.
- `.ms-playwright/` - lokalni brskalnik, ki ga uporablja Playwright.
- `pyproject.toml` - opis projekta in odvisnosti.
- `local_state/state.json` - lokalna zgodovina dokončanih vrstic in nastavitev, ko je program že uporabljen.

Uporabnik poleg teh datotek potrebuje še Excelov izvoz iz Ignisa, ki ga izbere v aplikaciji.

## 6. Datoteke, ki niso potrebne za normalno uporabo

Razvojne, testne in raziskovalne datoteke so premaknjene v mapo `extra_files/`. Mednje spadajo:

- testne skripte,
- poskusi podvojenih POST zahtevkov,
- pomočnik za zajem Vulkan zahtevkov,
- zajeti dnevniki zahtevkov,
- avtomatizirani testi,
- stara avtomatizacija klikanja po spletnem vmesniku,
- Python predpomnilnik in gradbene metapodatkovne datoteke.
- zasebni podatki, kot so pravi člani v `vulkan_members.json`.

Te datoteke so uporabne za razvojno zgodovino in razhroščevanje, niso pa potrebne za običajen mesečni prenos aktivnosti.

## 7. Varnostni mehanizmi

Program vsebuje več varnostnih mehanizmov:

- vsaka aktivnost se pred oddajo pregleda,
- neznane kategorije ni mogoče oddati,
- člani, ki jih ni v Vulkanu, so prikazani modro in se preskočijo,
- uspešno prenesene vrstice se zabeležijo lokalno,
- program ne shranjuje gesel,
- uporablja obstoječo prijavljeno brskalniško sejo.

Pomembna omejitev je, da Vulkan sam dovoljuje podvojene aktivnosti. Zato naj bo možnost za preskok lokalno že prenesenih vrstic običajno vklopljena.

## 8. Uporabljene tehnologije

- Python
- Tkinter za namizni uporabniški vmesnik
- OpenPyXL za branje Excelovih datotek
- Playwright za uporabo prijavljene Vulkan brskalniške seje
- JSON za podatke o članih in lokalno stanje
- Vulkan HTTP POST končne točke za ustvarjanje aktivnosti in vpis članov

## 9. Zaključek

Končno orodje spremeni ponavljajoč se ročni postopek v pregledan polavtomatski potek dela. Uporabnik še vedno nadzoruje vsako aktivnost, program pa odstrani večino ročnega tipkanja in iskanja članov. Največja izboljšava je bil prehod iz nezanesljive avtomatizacije spletnega vmesnika na Vulkanov lastni format zahtevkov, kar je prenos naredilo zanesljivejši.
