# AARCH 1. år kalender

Denne mappe bygger hver nat en kalender med dine faser og 1. års datoer.
Faserne lægges i de huller, Moodle efterlader, og står som ledig tid.
Outlook abonnerer på resultatet, så det holder sig opdateret af sig selv.

## Opsætning (cirka 20 minutter, kun første gang)

### 1. Hent dit Moodle link
I Moodle: **Kalender**, så **Eksporter kalender**.
Vælg **Alle kurser** og **Seneste og næste 60 dage**, og klik **Hent kalender URL**.
Kopier linket. Det er personligt, så del det ikke med andre.

### 2. Opret konto og repository på GitHub
1. Opret en gratis konto på github.com.
2. Klik **New repository** (det grønne plus øverst til højre).
3. Navn: `aarch-kalender`. Vælg **Public** (nødvendigt for gratis udgivelse).
   Kun tidspunkter og fasenavne bliver offentlige. Moodle titler, lokaler og dit link gemmes ikke i koden.
4. Klik **Create repository**.

### 3. Læg filerne op
1. Pak zip filen ud på din Mac.
2. I Finder: tryk **cmd + shift + punktum** for at vise skjulte mapper. Mappen `.github` skal med.
3. På GitHub: klik **uploading an existing file** og træk alt indholdet af mappen ind
   (`.github`, `data`, `docs`, `config.json`, `generate.py`, `README.md`).
4. Klik **Commit changes**.

### 4. Gem Moodle linket som hemmelighed
**Settings**, så **Secrets and variables**, så **Actions**, så **New repository secret**.
Navn: `MOODLE_URL`. Værdi: dit Moodle link. Klik **Add secret**.

### 5. Slå udgivelse til
**Settings**, så **Pages**. Under Source vælg **Deploy from a branch**,
branch **main** og mappe **/docs**. Klik **Save**.

### 6. Kør første opdatering
Fanen **Actions**. Godkend workflows, hvis GitHub spørger.
Vælg **Opdater kalender** og klik **Run workflow**. Vent et minut, til den er grøn.

### 7. Abonner i Outlook
Slet først den kalender, du uploadede tidligere.
I Outlook på nettet: **Tilføj kalender**, så **Abonner fra internettet**, og indsæt:

    https://DITBRUGERNAVN.github.io/aarch-kalender/aarch.ics

Giv den navnet "AARCH 1. år" og klik **Importer**.

## Sådan virker det
* Hver nat ca. kl. 5 henter GitHub dit Moodle link og bygger kalenderen igen.
* Outlook på nettet henter abonnementer med nogle timers mellemrum, så ændringer kan tage op til et døgn om at dukke op.
* Regler for faserne:
  * starter når dagens første Moodle aftale slutter og slutter kl. 17
  * lægges kun i ledige huller, og ingen blok starter kl. 16 eller senere
  * huller omkring unitmøder skal være mindst 1 time, andre mindst 30 minutter
  * når Moodle har en "Afslutning" for fasen, stopper fasen dér
  * dage uden Moodle aftaler får 9 til 17
  * dage længere frem end Moodle har data for, vises som heldagsbånd mandag til fredag, indtil Moodle har aftalerne
* Gamle Moodle aftaler gemmes i `data/moodle_cache.json` (kun tider), så historikken bevares.

## Ændringer
Datoer, faser og regler står i `config.json`. Rediger filen direkte på GitHub
(blyantsikonet), gem, og kør **Opdater kalender** under Actions, hvis du ikke vil vente til natten.
