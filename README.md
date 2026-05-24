# Bonsai5D+

Estensione per [Bonsai BIM](https://bonsaibim.org) che aggiunge strumenti di **computo metrico estimativo e contabilità dei lavori** in conformità con le prassi degli appalti pubblici italiani (Codice dei Contratti Pubblici, D.Lgs. 36/2023).

Bonsai5D+ opera direttamente sul file IFC, sfruttando le entità `IfcCostSchedule` e `IfcCostItem` come struttura dati nativa. Non introduce formati proprietari: tutto ciò che viene creato o modificato resta leggibile da qualsiasi software IFC-compatibile.

---

## Funzionalità

### Rate List Importer
Importa prezzari regionali italiani in formato XML o XPWE e li rende disponibili come lista navigabile nella sidebar di Blender.

Formati supportati:
- **XPWE** (Primus e compatibili)
- **SIX** (formato DEI)
- Regione **Veneto** / Friuli-Venezia Giulia
- Regione **Lombardia**
- Regione **Toscana** (usato anche da Calabria, Campania, Sardegna)
- Regione **Liguria**
- Regione **Basilicata**
- **IfcCostSchedule** — carica come sorgente tariffe un qualsiasi Schedule of Rates già presente nel progetto IFC corrente

Le voci del prezzario possono essere assegnate alle voci di computo (`IfcCostItem`) con un clic, creando un nuovo item o aggiornando quello attivo, con ripartizione automatica delle componenti (manodopera, noli, materiali, sicurezza).

### Rate Analysis
Costruisce l'**analisi del prezzo** per una singola voce di computo, scomponendo il costo unitario nelle componenti elementari (Sub-Contract, Labor, Equipment, Material, Safety), applicando percentuali di spese generali e utile d'impresa e calcolando il prezzo finale arrotondato.

I dati vengono scritti nel file IFC come `IfcCostValue` con categoria e struttura round-trip: è possibile riaprire un'analisi salvata, modificarla e riscriverla. I riferimenti alle tariffe sorgente vengono tracciati tramite l'ID IFC, con segnalazione automatica se il valore della tariffa è cambiato dall'ultima applicazione.

La voce può essere editata nei campi Identification, Name e Description direttamente dal pannello. La Description supporta testi lunghi tramite il **Text Editor** integrato di Blender (word wrap attivo), con anteprima multiriga nel pannello.

### BoQ → Schedule of Rates
Estrae le voci foglia di un **Bill of Quantities** (`IfcCostSchedule` di tipo `PRICEDBILLOFQUANTITIES` o `UNPRICEDBILLOFQUANTITIES`) e le trasferisce in uno **Schedule of Rates**, creandolo ex novo oppure aggiornando uno esistente.

Gestisce automaticamente:
- deduplicazione delle voci (stessa Identification + Name)
- rilevamento di conflitti (stesso codice, dati diversi)
- confronto puntuale tra BoQ e SoR con diff inline e risoluzione interattiva voce per voce
- report copiabile negli appunti in formato TSV (per LibreOffice Calc)

### Bulk Update Cost Schedule
Aggiorna in blocco i valori unitari del Cost Schedule attivo leggendo le tariffe dal prezzario caricato, con anteprima delle modifiche prima di applicarle.

### Cost Item Classification
Assegna codici di classificazione alle voci di costo IFC e produce un **riepilogo economico per categoria** con importi assoluti e percentuali sul totale del Cost Schedule attivo.

Sistemi di classificazione inclusi (file IFC4X3 in `src/data/classifications/`):
- **SOA** — categorie di qualificazione (D.Lgs. 36/2023 Allegato II.12)
- **DM17** — classi e categorie tariffarie (DM 17 giugno 2016, Tavola Z-1)
- **TOL** — Tipologie Omogenee di Lavorazione (D.Lgs. 36/2023 Art. 60, Tabella A.1, GU 31-12-2024 n.305) — 20 categorie con declaratorie complete

I sistemi di classificazione vengono caricati automaticamente all'avvio leggendo tutti i file `.ifc` presenti in `src/data/classifications/`. Per aggiungere un nuovo sistema è sufficiente depositare il file nella cartella.

---

## Installazione

### Per lo sviluppo (symlink)
```
mklink /J "%APPDATA%\Blender Foundation\Blender\<versione>\scripts\addons\bonsai_5d_plus" "<percorso_repo>\src"
```
Abilitare l'addon in *Edit > Preferences > Add-ons* cercando **Bonsai5D+**.

### Release
Zippare il contenuto della cartella `src/` (non la cartella stessa). Il file `.zip` può essere installato direttamente da Blender tramite *Edit > Preferences > Add-ons > Install*.

### Rigenerare i file di classificazione
I file IFC in `src/data/classifications/` sono già inclusi nel repository. Per rigenerarli (ad esempio dopo aver modificato le categorie):
```
blender.exe --background --python tools/generate_classifications.py
```

---

## Dipendenze

- [Bonsai BIM](https://bonsaibim.org) (addon Blender)
- [ifcopenshell](https://ifcopenshell.org) (incluso in Bonsai)
- Blender 4.0 o superiore

---

## Licenza

Da definire.

---

## Summary (English)

**Bonsai5D+** is a Blender addon extending [Bonsai BIM](https://bonsaibim.org) with cost management tools tailored to Italian public procurement regulations (D.Lgs. 36/2023). All data is stored natively in the IFC file using `IfcCostSchedule` and `IfcCostItem` — no proprietary formats.

**Modules:**

- **Rate List Importer** — imports Italian regional price lists (XML/XPWE formats: Veneto, Lombardia, Toscana, Liguria, Basilicata, SIX, XPWE/Primus) and exposes them as a browsable list in Blender's sidebar. Items can be assigned to cost items in one click.

- **Rate Analysis** — builds a unit price breakdown for a single cost item, splitting the cost into components (Sub-Contract, Labor, Equipment, Material, Safety) and applying overhead and profit percentages. Data is written to IFC as `IfcCostValue` entries with full round-trip support. Long descriptions are edited via Blender's built-in Text Editor with word wrap.

- **BoQ → Schedule of Rates** — extracts leaf items from a Bill of Quantities and transfers them to a Schedule of Rates (new or existing), with automatic deduplication, conflict detection, and an interactive per-item diff resolver.

- **Bulk Update Cost Schedule** — batch-updates unit prices in the active Cost Schedule from the loaded price list, with a preview before applying.

- **Cost Item Classification** — assigns classification codes (SOA, DM17, TOL) to IFC cost items and generates a financial summary by category with amounts and percentages. Classification systems are loaded automatically from IFC4X3 files in `src/data/classifications/`. The TOL system covers all 20 Tipologie Omogenee di Lavorazione defined in GU 31-12-2024 n.305.
