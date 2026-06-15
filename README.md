# Bonsai5D+

> **A [Blender](https://www.blender.org) / [Bonsai BIM](https://bonsaibim.org) add-on for 5D cost management** — price-list import, bill of quantities, rate analysis, labor-incidence reporting and PDF output — stored natively in the IFC file (`IfcCostSchedule` / `IfcCostItem`, no proprietary formats) and tailored to Italian public-procurement practice (D.Lgs. 36/2023). Full English description at the [end of this page](#summary-english).

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

### Cost Item Editor
Pannello centrale per editare una voce di computo `IfcCostItem` direttamente dalla sidebar. È composto da tre sub-panel:

**Identification** — Identification, Name e Description su singola riga con tooltip che mostra il testo completo. La Description supporta testi lunghi tramite il **Text Editor** integrato di Blender, aperto in una **finestra flottante** separata (la 3D View non viene mai sostituita).

**Rate Analysis** — Costruisce l'**analisi del prezzo** di una voce scomponendo il costo unitario in componenti elementari:

- **Categorie componenti:** Sub-Contract, Labor, Equipment, Material, Safety (+ NONE per valori liberi)
- **Campi per componente:** descrizione, quantità, unità di misura, prezzo unitario
- **Totali automatici:** costo tecnico, spese generali (%), utile d'impresa (%), arrotondamento → prezzo finale
- **Import da prezzario:** aggiunge direttamente una voce dal Rate List come componente collegato
- **Segnalazione aggiornamenti:** se il prezzo della tariffa sorgente è cambiato dall'ultima applicazione, il componente viene evidenziato con un bottone di aggiornamento rapido
- **Auto-load:** opzione per ricaricare automaticamente i dati quando cambia la voce attiva nel pannello Bonsai

**Struttura IFC scritta:** l'analisi prezzi viene serializzata come una struttura `IfcCostValue` annidata sull'`IfcCostItem`:
- un **`IfcCostValue` sommario** con `AppliedValue` = prezzo finale, `UnitBasis` = `IfcMeasureWithUnit(1.0, unità_voce)` e `ArithmeticOperator = ADD`
- i **componenti elementari** come sotto-entità in `Components`: ognuno con `Category` (es. "Labor"), `AppliedValue` = totale riga (qty × prezzo unitario), `UnitBasis` = `IfcMeasureWithUnit(qty, unità_componente)`
- **Spese generali, utile e arrotondamento** come ulteriori `Components` con `Category` = "Overhead", "Profit", "Rounding"

La quantità e l'unità di ogni componente sono recuperabili al round-trip. I riferimenti alla tariffa sorgente vengono salvati in `IfcCostValue.Description` nel formato `ref:[Identificazione](#ifc:STEP_ID)`. Le unità di misura riusano le `IfcSIUnit` del progetto (`mq`→`SQUARE_METRE`, ecc.) o creano `IfcConversionBasedUnit` per ore e minuti, minimizzando le entità user-defined nel file. Il marcatore `IfcCostItem.ObjectType = "RATE_ANALYSIS"` distingue le voci con analisi prezzi vera dalle voci prezzario che espongono solo incidenze di categoria.

**Quantities (libretto delle misure)** — Lettura e modifica di `IfcCostItem.CostQuantities` tramite un libretto delle misure interattivo. Ogni riga ha campi **NR × L × B × H** con parziale calcolato in tempo reale e totale complessivo a fondo pannello. Il tipo di quantità (Area, Volume, Lunghezza, Conteggio, Peso, Tempo) determina il sottotipo `IfcQuantity` scritto nel file. La formula viene salvata nell'attributo `Formula` (IFC4) con round-trip completo.

### BoQ → Schedule of Rates
Estrae le voci foglia di un **Bill of Quantities** (`IfcCostSchedule` di tipo `PRICEDBILLOFQUANTITIES` o `UNPRICEDBILLOFQUANTITIES`) e le trasferisce in uno **Schedule of Rates**, creandolo ex novo oppure aggiornando uno esistente.

Gestisce automaticamente:
- deduplicazione delle voci (stessa Identification + Name)
- rilevamento di conflitti (stesso codice, dati diversi)
- confronto puntuale tra BoQ e SoR con diff inline e risoluzione interattiva voce per voce
- report copiabile negli appunti in formato TSV (per LibreOffice Calc)

### Prints Manager
Esporta in PDF i documenti di costo direttamente dalla sidebar, senza passare per tool esterni. Il motore di rendering è [Typst](https://typst.app), già disponibile come dipendenza nell'estensione `typst_importer` di Blender. Il PDF generato viene aperto automaticamente al termine.

**Export Schedule to PDF** — Stampa il Cost Schedule attivo in formato PDF tramite `Ifc5DPdfWriter` (ifc5d / IfcOpenShell). Il dialogo permette di scegliere tipo di documento (Priced BoQ, Schedule of Rates, ecc.), visibilità di tariffe, descrizioni, quantità di dettaglio, pagina di riepilogo e copertina.

**Export Rate Analysis to PDF** — Stampa la **scheda analisi prezzi** della voce attiva (item pinnato nell'editor oppure item selezionato nel pannello Bonsai). I dati vengono letti **direttamente dall'IFC**, non dalla UI, quindi non è necessario aver caricato la voce nell'editor prima di esportare. Per ogni categoria di componenti (Opere Compiute, Manodopera, Noli, Materiali, Oneri per la Sicurezza) viene generato un riquadro con intestazione e subtotale separati. Il footer della scheda mostra: costo tecnico, spese generali (%), utile d'impresa (%), arrotondamento e prezzo finale.

**Export Labor Cost Breakdown to PDF** — Stampa il **quadro di incidenza della manodopera** del Cost Schedule attivo: stessa struttura del Bill of Quantities ma con due colonne di costo (costo totale e costo manodopera) e la percentuale di incidenza per ogni voce, più una pagina di riepilogo finale con l'incidenza per capitolo e il totale generale. I dati provengono dallo stesso estrattore `Ifc5DCsvWriter` del BoQ (colonna di categoria "Labor"); l'incidenza compare solo per voci con `IfcCostValue` di categoria Labor di primo livello.

**Export Sheets to PDF** — Converte gli sheet SVG prodotti da Bonsai Drawing in PDF, salvandoli accanto agli SVG originali. Se gli sheet sono ≤ 3 apre tutti i PDF generati; se sono più di 3 apre la cartella contenitore.

**Struttura IFC dei CostValues:** tutte le voci di costo (sia EPU importati da prezzario sia analisi prezzi) usano una struttura `IfcCostValue` annidata: un valore sommario con prezzo totale e unità di misura (`UnitBasis`), e i sotto-componenti con le incidenze di categoria in `Components` (`ArithmeticOperator = ADD`). Le voci prezzario con incidenze nulle hanno solo il valore sommario. Il marcatore `IfcCostItem.ObjectType = "RATE_ANALYSIS"` distingue le voci con vera analisi prezzi (struttura qty × prezzo unitario per componente) dalle voci prezzario che riportano solo incidenze monetarie aggregate.

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

### Da GitHub Releases
Scaricare il file `bonsai_5d_plus-X.Y.Z.zip` dalla [pagina Releases](https://github.com/carlopav/bonsai_5d_plus/releases) e installarlo da Blender tramite *Edit > Preferences > Add-ons > Install from disk*.

### Build da sorgente
```
python tools/build_release.py
```
Produce `dist/bonsai_5d_plus-X.Y.Z.zip` con la struttura corretta per Blender. La versione viene letta automaticamente da `__init__.py`.

### Per lo sviluppo (symlink)
```
mklink /J "%APPDATA%\Blender Foundation\Blender\<versione>\scripts\addons\bonsai_5d_plus" "<percorso_repo>\src\bonsai_5d_plus"
```
Abilitare l'addon in *Edit > Preferences > Add-ons* cercando **Bonsai5D+**.

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

[GPL-3.0](LICENSE) — Copyright (C) 2026 Carlo Pavan.

---

## Summary (English)

**Bonsai5D+** is a Blender addon extending [Bonsai BIM](https://bonsaibim.org) with cost management tools tailored to Italian public procurement regulations (D.Lgs. 36/2023). All data is stored natively in the IFC file using `IfcCostSchedule` and `IfcCostItem` — no proprietary formats.

**Modules:**

- **Rate List Importer** — imports Italian regional price lists (XML/XPWE formats: Veneto, Lombardia, Toscana, Liguria, Basilicata, SIX, XPWE/Primus) and exposes them as a browsable list in Blender's sidebar. Items can be assigned to cost items in one click.

- **Cost Item Editor** — three-panel editor for a single `IfcCostItem`:
  - *Identification*: single-line ID / Name / Description fields; full description visible in tooltip; long descriptions edited in a dedicated floating Text Editor window.
  - *Rate Analysis*: unit price breakdown into components (Sub-Contract, Labor, Equipment, Material, Safety) with overhead %, profit %, and rounding. Written as a **nested `IfcCostValue` structure**: one summary value carrying the final price and the item's unit of measure (`UnitBasis = IfcMeasureWithUnit(1.0, unit)`), with all components and overhead/profit/rounding entries in `Components` (`ArithmeticOperator = ADD`). Each component carries `Category`, `AppliedValue` (line total), and `UnitBasis` (qty + unit entity) for full round-trip. Source rate references are tracked in `Description` as `ref:[ID](#ifc:STEP_ID)` with automatic stale-rate detection. Unit entities reuse existing project `IfcSIUnit` instances (e.g. `SQUARE_METRE` for `mq`) or create `IfcConversionBasedUnit` for hours/minutes — minimising user-defined unit pollution in the file.
  - *Quantities (measurement book)*: interactive libretto-delle-misure table for `IfcCostItem.CostQuantities`. Each row has NR × L × B × H fields with live partial computation and a running total. Writes one `IfcQuantityXxx` per row using the IFC4 `Formula` attribute for the expression.

- **BoQ → Schedule of Rates** — extracts leaf items from a Bill of Quantities and transfers them to a Schedule of Rates (new or existing), with automatic deduplication, conflict detection, and an interactive per-item diff resolver.

- **Prints Manager** — PDF export for cost documents, powered by [Typst](https://typst.app):
  - *Export Schedule to PDF*: renders the active `IfcCostSchedule` to PDF via `Ifc5DPdfWriter` (ifc5d / IfcOpenShell) with configurable options (document type, rates visibility, quantity breakdown, summary page, cover).
  - *Export Rate Analysis to PDF*: generates a **scheda analisi prezzi** for the active cost item. Data is read **directly from the IFC file** (not from the UI state), so no prior loading in the Rate Analysis editor is required. Components are grouped by category (Sub-Contract, Labor, Equipment, Material, Safety) with a separate header and subtotal per group; the footer shows technical cost, overhead %, profit %, rounding, and final price.
  - *Export Labor Cost Breakdown to PDF*: a **labor-incidence schedule** for the active Cost Schedule — the Bill-of-Quantities layout with two cost columns (total cost and labor cost) and a per-row labor incidence %, plus a final summary page with the incidence per chapter and the general total. Uses the same `Ifc5DCsvWriter` extractor as the BoQ ("Labor" category column); the incidence only appears for items carrying a top-level Labor `IfcCostValue`.
  - *Export Sheets to PDF*: converts Bonsai Drawing SVG sheets to PDF, saved alongside the originals; opens generated files automatically.
  - **IFC structure:** all cost items (both imported price-list entries and rate-analysis items) use a nested `IfcCostValue` structure: a summary value with the total price and `UnitBasis` (item unit of measure), and monetary category sub-components in `Components` (`ArithmeticOperator = ADD`). Items with no category incidences carry only the summary value. `IfcCostItem.ObjectType = "RATE_ANALYSIS"` marks items with a genuine qty × unit-price breakdown, distinguishing them from prezzario entries that carry aggregate category incidences only.

- **Bulk Update Cost Schedule** — batch-updates unit prices in the active Cost Schedule from the loaded price list, with a preview before applying.

- **Cost Item Classification** — assigns classification codes (SOA, DM17, TOL) to IFC cost items and generates a financial summary by category with amounts and percentages. Classification systems are loaded automatically from IFC4X3 files in `src/data/classifications/`. The TOL system covers all 20 Tipologie Omogenee di Lavorazione defined in GU 31-12-2024 n.305.
