# Bonsai5D+

> **A [Blender](https://www.blender.org) / [Bonsai BIM](https://bonsaibim.org) add-on for 5D cost management** — price-list import, bill of quantities, rate analysis, labor-incidence reporting and PDF output — stored natively in the IFC file (`IfcCostSchedule` / `IfcCostItem`, no proprietary formats) and tailored to Italian public-procurement practice (D.Lgs. 36/2023). Full English description at the [end of this page](#summary-english).

Estensione per [Bonsai BIM](https://bonsaibim.org) che aggiunge strumenti di **computo metrico estimativo e contabilità dei lavori** in conformità con le prassi degli appalti pubblici italiani (Codice dei Contratti Pubblici, D.Lgs. 36/2023).

Bonsai5D+ opera direttamente sul file IFC, sfruttando le entità `IfcCostSchedule` e `IfcCostItem` come struttura dati nativa. Non introduce formati proprietari: tutto ciò che viene creato o modificato resta leggibile da qualsiasi software IFC-compatibile.

---

## Funzionalità

L'ordine qui sotto rispecchia l'ordine dei pannelli nella sidebar (*Bonsai5D+*).

### Cost Item Editor
Pannello centrale per editare una voce di computo `IfcCostItem` direttamente dalla sidebar, con caricamento manuale (bottone "Load Item Data") o automatico (toggle "Auto Load" collegato alla voce attiva nel pannello Bonsai nativo). È composto da tre sub-panel.

**Identification** — Identification, Name e Description su singola riga con tooltip che mostra il testo completo. La Description supporta testi lunghi tramite il **Text Editor** integrato di Blender, aperto in una **finestra flottante** separata (la 3D View non viene mai sostituita).

**Cost Values** — tre modalità alternative per il prezzo della voce, ciascuna con un **gate esplicito**: se lo stato IFC corrente della voce non corrisponde alla modalità selezionata, viene mostrato solo un bottone che lo dichiara ("Clear cost values and…"), così l'utente sa sempre quale delle tre è effettivamente applicata.

- **Sum** — la voce somma i costi delle sue voci figlie (`IfcCostValue.Category = "*"`). Nessun dato da editare.
- **Fixed** — un prezzo piatto, con lista **editabile inline** (categoria, nome, valore per riga) e un'**unica unità di misura condivisa** per l'intera voce. Il selettore unità è dinamico: propone prima le unità comuni (mq, mc, m, kg, t, h, cad), poi qualunque unità già dichiarata nel progetto (`IfcProject.UnitsInContext`) o già usata altrove nello schedule, riducendo il rischio di unità duplicate/incoerenti; `Custom…` resta disponibile per testo libero.
- **Rate Analysis** — costruisce l'**analisi del prezzo** scomponendo il costo unitario in componenti elementari (Sub-Contract, Labor, Equipment, Material, Safety + NONE per valori liberi), ciascuno con descrizione, quantità, unità di misura, prezzo unitario. Totali automatici: costo tecnico, spese generali (%), utile d'impresa (%), arrotondamento → prezzo finale. Un componente può essere importato direttamente da una voce del Rate List; se il prezzo della tariffa sorgente cambia dopo l'applicazione, il componente viene evidenziato con un bottone di aggiornamento rapido.

  **Struttura IFC scritta** (Rate Analysis): un **`IfcCostValue` sommario** con `AppliedValue` = prezzo finale, `UnitBasis` = `IfcMeasureWithUnit(1.0, unità_voce)`, `ArithmeticOperator = ADD`; i **componenti elementari** come sotto-entità in `Components` (ognuno con `Category`, `AppliedValue` = qty × prezzo unitario, `UnitBasis` = qty + unità); **spese generali, utile e arrotondamento** come ulteriori `Components` (`Category` = "Overhead"/"Profit"/"Rounding"). I riferimenti alla tariffa sorgente sono salvati in `IfcCostValue.Description` come `ref:[Identificazione](#ifc:STEP_ID)`. Il marcatore `IfcCostItem.ObjectType = "RATE_ANALYSIS"` distingue le voci con analisi prezzi vera dalle voci prezzario che espongono solo incidenze di categoria.

**Tariffe condivise (rate linking)** — un'analisi prezzi/EPU può **controllare** una o più voci in altri schedule (`IfcRelAssignsToControl`), così un aggiornamento di prezzo si propaga senza dover editare ogni computo. Header dedicato in cima al pannello:
- voce **controllata** da una tariffa: stato sync (✓/✗), "Load Controlling Item" per aprire la tariffa sorgente, "Resync from rate" (solo se fuori sync), "Unlink from Rate" (scollega mantenendo i valori correnti), "Make Unique" (scollega copiando prima Nome/Descrizione), "Duplicate Rate" (clona la tariffa e ricollega la voce alla copia, per farla divergere senza toccare l'originale)
- voce che **controlla** altre voci: conteggio + stato sync, "Propagate now…" (dialogo con anteprima delle voci coinvolte, propaga nome/descrizione/valori) e "Resync values" (ricondivide solo i valori, silenzioso)
- strumenti a livello di intero schedule (Audit / Resync all) sono nel **Toolbox**, vedi sotto

**Quantities (libretto delle misure)** — Lettura e modifica di `IfcCostItem.CostQuantities` tramite un libretto delle misure interattivo. Ogni riga ha campi **NR × L × B × H** con parziale calcolato in tempo reale e totale complessivo a fondo pannello. Il tipo di quantità (Area, Volume, Lunghezza, Conteggio, Peso, Tempo) determina il sottotipo `IfcQuantity` scritto nel file; la formula viene salvata nell'attributo `Formula` (IFC4) con round-trip completo. Il bottone **"Import from IFC"** legge il tipo di quantità attivo dai set di quantità (`Qto_*`/`BaseQuantities`) degli elementi IFC attualmente selezionati nella viewport e aggiunge una riga per ogni corrispondenza trovata (snapshot, non un link vivo: l'Apply riscrive sempre tutte le `CostQuantities` della voce).

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

### Cost Item Classification
Assegna codici di classificazione alle voci di costo IFC e produce un **riepilogo economico per categoria** con importi assoluti e percentuali sul totale del Cost Schedule attivo, esportabile in **CSV** con un clic.

Sistemi di classificazione inclusi (file IFC4X3 in `src/data/classifications/`):
- **SOA** — categorie di qualificazione (D.Lgs. 36/2023 Allegato II.12)
- **DM17** — classi e categorie tariffarie (DM 17 giugno 2016, Tavola Z-1)
- **TOL** — Tipologie Omogenee di Lavorazione (D.Lgs. 36/2023 Art. 60, Tabella A.1, GU 31-12-2024 n.305) — 20 categorie con declaratorie complete

I sistemi di classificazione vengono caricati automaticamente all'avvio leggendo tutti i file `.ifc` presenti in `src/data/classifications/`. Per aggiungere un nuovo sistema è sufficiente depositare il file nella cartella.

### Tenders Manager
Gestisce il confronto tra offerte di gara a partire da un Bill of Quantities base:

- **Create Tender Schedule** — duplica il BoQ sorgente come nuovo `IfcCostSchedule` (`PredefinedType = TENDER`) intestato a un'impresa offerente, con prezzo pieno oppure a **sconto percentuale** (con possibilità di escludere una voce, es. gli oneri di sicurezza, dallo sconto)
- **Offered Prices** — dialogo con lista di tutte le voci foglia del tender per inserire/editare i prezzi offerti riga per riga, con totale offerta in tempo reale
- **Bid Comparison** — tabella di confronto tra il computo base e tutti i tender creati: totale offerto, scostamento assoluto e percentuale rispetto alla base, evidenziazione dell'offerta più bassa; esportabile negli appunti come **TSV** con il dettaglio voce per voce

### Prints Manager
Esporta i documenti di costo direttamente dalla sidebar, senza passare per tool esterni. Il rendering PDF usa [Typst](https://typst.app), già disponibile come dipendenza nell'estensione `typst_importer` di Blender; i file generati vengono aperti automaticamente al termine.

**Export Schedule to PDF** — Stampa il Cost Schedule attivo in formato PDF tramite `Ifc5DPdfWriter` (ifc5d / IfcOpenShell). Il dialogo permette di scegliere tipo di documento (Priced BoQ, Schedule of Rates, ecc.), visibilità di tariffe, descrizioni, quantità di dettaglio, pagina di riepilogo e copertina.

**Export Schedule to ODS** — Stessa esportazione ma in formato **OpenDocument Spreadsheet**, con formule di calcolo live (non solo valori statici): stesse opzioni del PDF (tipo documento, rinumerazione gerarchica, profondità struttura, colonna Identification nella Description, ecc.), utile per continuare a lavorare sul computo in LibreOffice Calc.

**Export Rate Analysis to PDF** — Stampa la **scheda analisi prezzi** della voce attiva (item pinnato nell'editor oppure item selezionato nel pannello Bonsai). I dati vengono letti **direttamente dall'IFC**, non dalla UI, quindi non è necessario aver caricato la voce nell'editor prima di esportare. Per ogni categoria di componenti (Opere Compiute, Manodopera, Noli, Materiali, Oneri per la Sicurezza) viene generato un riquadro con intestazione e subtotale separati. Il footer della scheda mostra: costo tecnico, spese generali (%), utile d'impresa (%), arrotondamento e prezzo finale. **Export All Rate Analyses to PDF** esporta in un unico PDF tutte le voci con analisi prezzi presenti nello schedule attivo.

**Export Labor Cost Breakdown to PDF** — Stampa il **quadro di incidenza della manodopera** del Cost Schedule attivo: stessa struttura del Bill of Quantities ma con due colonne di costo (costo totale e costo manodopera) e la percentuale di incidenza per ogni voce, più una pagina di riepilogo finale con l'incidenza per capitolo e il totale generale. I dati provengono dallo stesso estrattore `Ifc5DCsvWriter` del BoQ (colonna di categoria "Labor"); l'incidenza compare solo per voci con `IfcCostValue` di categoria Labor di primo livello.

**Struttura IFC dei CostValues:** tutte le voci di costo (sia EPU importati da prezzario sia analisi prezzi) usano una struttura `IfcCostValue` annidata: un valore sommario con prezzo totale e unità di misura (`UnitBasis`), e i sotto-componenti con le incidenze di categoria in `Components` (`ArithmeticOperator = ADD`). Le voci prezzario con incidenze nulle hanno solo il valore sommario. Il marcatore `IfcCostItem.ObjectType = "RATE_ANALYSIS"` distingue le voci con vera analisi prezzi (struttura qty × prezzo unitario per componente) dalle voci prezzario che riportano solo incidenze monetarie aggregate.

### Import / Export
Import/export dell'intero Cost Schedule (non delle singole tariffe, per quello vedi Rate List Importer) da/verso file **XPWE** (Primus e compatibili):

- **Import XPWE** — crea due nuovi `IfcCostSchedule`: un **EPU** (prezzario, `PweElencoPrezzi`) e, se presente nel file, un **CME** (computo, `PweVociComputo`) già collegato alle voci EPU corrispondenti. Opzioni: raggruppare l'EPU sotto una singola voce sommario invece di preservare la struttura a capitoli, e importare ogni riga di misura (`RGItem`) come quantità IFC separata (con la scomposizione NR×L×B×H nell'attributo `Formula`) invece di un unico totale.
- **Export XPWE** — esporta lo schedule attivo (CME/BoQ) come file XPWE: il prezzario (`PweElencoPrezzi`) viene ricostruito dallo Schedule of Rates collegato quando presente, altrimenti sintetizzato dalle voci stesse.

### Toolbox
Raccoglie gli strumenti di manutenzione massiva sul Cost Schedule attivo, in un unico pannello collassabile.

**BoQ → Schedule of Rates** — Estrae le voci foglia di un **Bill of Quantities** (`IfcCostSchedule` di tipo `PRICEDBILLOFQUANTITIES` o `UNPRICEDBILLOFQUANTITIES`) e le trasferisce in uno **Schedule of Rates**, creandolo ex novo oppure aggiornando uno esistente. Gestisce automaticamente: deduplicazione delle voci (stessa Identification + Name), rilevamento di conflitti (stesso codice, dati diversi), confronto puntuale tra BoQ e SoR con diff inline e risoluzione interattiva voce per voce, report copiabile negli appunti in formato TSV.

**Bulk Update from Rate List** — Aggiorna in blocco i valori unitari del Cost Schedule attivo leggendo le tariffe dal prezzario caricato, con anteprima delle modifiche prima di applicarle.

**Reorder Cost Schedule** — Rinumera le `Identification` di tutte le voci dello schedule attivo in modo gerarchico progressivo (1, 1.1, 1.1.1, 1.2, 2, …). "Reorder All" riparte da zero su tutta la struttura; "Keep Levels Above" rinumera solo a partire da un livello scelto, lasciando invariati i livelli superiori e continuando la numerazione esistente dove già presente invece di azzerarla.

**Rate Sync** — Strumenti a livello di intero schedule per le tariffe condivise (vedi "Tariffe condivise" nel Cost Item Editor): **Audit schedule** riporta quante voci collegate a una tariffa sono fuori sincronia; **Resync all** riallinea in blocco tutte le voci fuori sincronia dello schedule attivo con la rispettiva tariffa controllante.

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
`Su WINDOWS`
```
mklink /J "%APPDATA%\Blender Foundation\Blender\<versione>\scripts\addons\bonsai_5d_plus" "<percorso_repo>\src\bonsai_5d_plus"
```
Abilitare l'addon in *Edit > Preferences > Add-ons* cercando **Bonsai5D+**.

`Su LINUX`

Il comando mklink /J mostrato sopra funziona solo su Windows. Su Linux usa invece un symlink, puntando alla sottocartella src/bonsai_5d_plus (non alla radice del repo):

```
mkdir -p ~/.config/blender/4.2/scripts/addons
ln -s /percorso/assoluto/di/bonsai_5d_plus/src/bonsai_5d_plus \
      ~/.config/blender/4.2/scripts/addons/bonsai_5d_plus
```
Note:

Usa un percorso assoluto per la sorgente — i symlink relativi spesso si rompono.
Assicurati che il link punti a src/bonsai_5d_plus (dove si trova __init__.py), non alla radice del repo — è un errore comune che fa sì che l'add-on non venga trovato.
Modifica 4.2 con la tua versione di Blender.
Riavvia Blender, poi vai su Edit > Preferences > Add-ons, clicca l'icona di refresh e cerca "Bonsai5D+".

### Rigenerare i file di classificazione
I file IFC in `src/data/classifications/` sono già inclusi nel repository. Per rigenerarli (ad esempio dopo aver modificato le categorie):
```
blender.exe --background --python tools/generate_classifications.py
```

---

## Dipendenze

- [Bonsai BIM](https://bonsaibim.org) (addon Blender) — **build giornaliera/alpha dal 17/06/2026 in poi** (`alpha260617+`). L'export PDF del computo richiede i fix `ifc5d` mergiati in ifcopenshell il 16/06/2026 ([#8175](https://github.com/IfcOpenShell/IfcOpenShell/pull/8175) escape dei nomi quantità, [#8176](https://github.com/IfcOpenShell/IfcOpenShell/pull/8176) formula nelle quantità). Con build precedenti la stampa della BoQ fallisce con un errore di parsing JSON.
- [ifcopenshell](https://ifcopenshell.org) (incluso in Bonsai)
- Blender 4.0 o superiore

---

## Licenza

[GPL-3.0](LICENSE) — Copyright (C) 2026 Carlo Pavan.

---

## Summary (English)

**Bonsai5D+** is a Blender addon extending [Bonsai BIM](https://bonsaibim.org) with cost management tools tailored to Italian public procurement regulations (D.Lgs. 36/2023). All data is stored natively in the IFC file using `IfcCostSchedule` and `IfcCostItem` — no proprietary formats.

**Modules** (in sidebar order):

- **Cost Item Editor** — three-panel editor for a single `IfcCostItem`, loaded manually or automatically (auto-load toggle follows Bonsai's own active cost item):
  - *Identification*: single-line ID / Name / Description fields; full description visible in tooltip; long descriptions edited in a dedicated floating Text Editor window.
  - *Cost Values*: three mutually-exclusive price modes, each with an explicit **gate** — if the item's current IFC state doesn't match the selected mode, only a "Clear cost values and…" button is shown, so the active mode is never ambiguous.
    - *Sum*: the item sums its children's costs (`Category = "*"`), nothing to edit.
    - *Fixed*: a flat price with an **inline-editable list** (category, name, value per row) and **one shared unit of measure** for the whole item. The unit picker is dynamic — it offers the common built-ins first, then any unit already declared on the project (`IfcProject.UnitsInContext`) or already used elsewhere in the schedule, to keep unit strings consistent project-wide; `Custom…` remains available for free text.
    - *Rate Analysis*: unit price breakdown into components (Sub-Contract, Labor, Equipment, Material, Safety) with overhead %, profit %, and rounding. Written as a **nested `IfcCostValue` structure**: one summary value carrying the final price and the item's unit of measure (`UnitBasis = IfcMeasureWithUnit(1.0, unit)`), with all components and overhead/profit/rounding entries in `Components` (`ArithmeticOperator = ADD`). Each component carries `Category`, `AppliedValue` (line total), and `UnitBasis` (qty + unit entity) for full round-trip. Source rate references are tracked in `Description` as `ref:[ID](#ifc:STEP_ID)` with automatic stale-rate detection. `IfcCostItem.ObjectType = "RATE_ANALYSIS"` marks items with a genuine qty × unit-price breakdown, distinguishing them from prezzario entries that carry aggregate category incidences only.
  - *Shared rates (rate linking)*: a rate-analysis/price-list item can **control** one or more items in other schedules (`IfcRelAssignsToControl`), so a price update propagates instead of having to edit every BoQ line by hand. A dedicated header at the top of the panel offers, for a **controlled** item: sync status, "Load Controlling Item", "Resync from rate" (when out of sync), "Unlink from Rate" (detach, keep current values), "Make Unique" (detach after copying the controller's Name/Description), "Duplicate Rate" (clone the controller and relink the item to the copy, so it can diverge independently); for an item that **controls** others: dependent count + sync status, "Propagate now…" (preview dialog, pushes name/description/values) and "Resync values" (silent value re-share). Schedule-wide audit/resync tools live in the Toolbox (below).
  - *Quantities (measurement book)*: interactive libretto-delle-misure table for `IfcCostItem.CostQuantities`. Each row has NR × L × B × H fields with live partial computation and a running total. Writes one `IfcQuantityXxx` per row using the IFC4 `Formula` attribute for the expression. **"Import from IFC"** reads the active Quantity Type from the `Qto_*`/`BaseQuantities` property sets of the currently selected IFC elements in the viewport and adds one row per match (a snapshot, not a live link — Apply always rewrites the item's whole `CostQuantities`).

- **Rate List Importer** — imports Italian regional price lists (XML/XPWE formats: Veneto, Lombardia, Toscana, Liguria, Basilicata, SIX, XPWE/Primus, or any Schedule of Rates already in the current IFC project) and exposes them as a browsable list in Blender's sidebar. Items can be assigned to cost items in one click, with automatic component breakdown (labor, equipment, material, safety).

- **Cost Item Classification** — assigns classification codes (SOA, DM17, TOL) to IFC cost items and generates a financial summary by category with amounts and percentages, exportable to **CSV** in one click. Classification systems are loaded automatically from IFC4X3 files in `src/data/classifications/`. The TOL system covers all 20 Tipologie Omogenee di Lavorazione defined in GU 31-12-2024 n.305.

- **Tenders Manager** — bid comparison workflow against a base Bill of Quantities: *Create Tender Schedule* duplicates the source BoQ as a new `TENDER` schedule for a bidding company (full price or a percentage discount, optionally excluding one item such as safety costs); *Offered Prices* is a per-item dialog to enter a bidder's unit prices with a live running total; *Bid Comparison* shows every tender against the base estimate (total, absolute/percentage difference, lowest-bid highlight), with a per-item **TSV** export to clipboard.

- **Prints Manager** — document export for cost data, powered by [Typst](https://typst.app) for PDFs; generated files open automatically:
  - *Export Schedule to PDF*: renders the active `IfcCostSchedule` to PDF via `Ifc5DPdfWriter` (ifc5d / IfcOpenShell) with configurable options (document type, rates visibility, quantity breakdown, summary page, cover).
  - *Export Schedule to ODS*: the same export as an **OpenDocument Spreadsheet** with live calculation formulas (not static values) — same options as the PDF — so the schedule stays editable in LibreOffice Calc.
  - *Export Rate Analysis to PDF*: generates a **scheda analisi prezzi** for the active cost item. Data is read **directly from the IFC file** (not from the UI state), so no prior loading in the Cost Item Editor is required. Components are grouped by category (Sub-Contract, Labor, Equipment, Material, Safety) with a separate header and subtotal per group; the footer shows technical cost, overhead %, profit %, rounding, and final price. *Export All Rate Analyses to PDF* does the same for every rate-analysis item in the active schedule, in a single PDF.
  - *Export Labor Cost Breakdown to PDF*: a **labor-incidence schedule** for the active Cost Schedule — the Bill-of-Quantities layout with two cost columns (total cost and labor cost) and a per-row labor incidence %, plus a final summary page with the incidence per chapter and the general total. Uses the same `Ifc5DCsvWriter` extractor as the BoQ ("Labor" category column); the incidence only appears for items carrying a top-level Labor `IfcCostValue`.
  - **IFC structure:** all cost items (both imported price-list entries and rate-analysis items) use a nested `IfcCostValue` structure: a summary value with the total price and `UnitBasis` (item unit of measure), and monetary category sub-components in `Components` (`ArithmeticOperator = ADD`). Items with no category incidences carry only the summary value.

- **Import / Export** — whole-schedule import/export to/from **XPWE** (Primus and compatible), as opposed to the single-rate import of the Rate List Importer: *Import XPWE* creates a new EPU price-list schedule and, when present in the file, a linked CME (computo) schedule, with options to flatten the EPU chapter hierarchy and to import each measurement row as a separate IFC quantity (NR×L×B×H in the `Formula` attribute) instead of a single total; *Export XPWE* writes the active schedule out, rebuilding the price list from its linked Schedule of Rates when present or synthesising it from the items themselves.

- **Toolbox** — bulk maintenance tools for the active Cost Schedule, grouped under one collapsible panel:
  - *BoQ → Schedule of Rates*: extracts leaf items from a Bill of Quantities and transfers them to a Schedule of Rates (new or existing), with automatic deduplication, conflict detection, and an interactive per-item diff resolver, plus a TSV clipboard report.
  - *Bulk Update from Rate List*: batch-updates unit prices in the active Cost Schedule from the loaded price list, with a preview before applying.
  - *Reorder Cost Schedule*: renumbers every item's `Identification` hierarchically (1, 1.1, 1.1.1, 1.2, 2, …) — "Reorder All" resets the whole structure, "Keep Levels Above" renumbers from a chosen level down, leaving higher levels untouched and continuing existing numeric identifications rather than resetting them.
  - *Rate Sync*: schedule-wide tools for the shared-rate linking described above — "Audit schedule" reports how many rate-linked items are out of sync; "Resync all" realigns every out-of-sync item in the active schedule with its controlling rate.

**Requirements:** Blender 4.0+ and a recent Bonsai BIM **daily/alpha build from 2026-06-17 onward** (`alpha260617+`). PDF export of the bill of quantities relies on the `ifc5d` fixes merged into ifcopenshell on 2026-06-16 ([#8175](https://github.com/IfcOpenShell/IfcOpenShell/pull/8175) escape quantity names, [#8176](https://github.com/IfcOpenShell/IfcOpenShell/pull/8176) include the quantity formula); with older builds the BoQ print fails with a JSON parsing error.
