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

**Struttura IFC scritta:** ogni componente diventa un `IfcCostValue` con `Category` (es. "Labor"), `AppliedValue` = totale riga (qty × prezzo unitario), `UnitBasis` = `IfcMeasureWithUnit(IfcNumericMeasure(qty), unità)`. La quantità e l'unità del componente sono quindi recuperabili al round-trip. I riferimenti alla tariffa sorgente vengono salvati in `IfcCostValue.Description` nel formato `ref:[Identificazione](#ifc:STEP_ID)`. Spese generali, utile e arrotondamento sono `IfcCostValue` separati con `Category` = "Overhead", "Profit", "Rounding". Le unità di misura riusano le `IfcSIUnit` del progetto (`mq`→`SQUARE_METRE`, ecc.) o creano `IfcConversionBasedUnit` per ore e minuti, minimizzando le entità user-defined nel file.

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

**Export Sheets to PDF** — Converte gli sheet SVG prodotti da Bonsai Drawing in PDF, salvandoli accanto agli SVG originali. Se gli sheet sono ≤ 3 apre tutti i PDF generati; se sono più di 3 apre la cartella contenitore.

**Convenzione IFC:** quando l'utente applica un'analisi prezzi tramite il Rate Analysis editor, la voce `IfcCostItem` riceve `ObjectType = "RATE_ANALYSIS"`. Questo marcatore permette di distinguere le voci con vera analisi prezzi dai semplici item prezzario che riportano incidenze di categoria (Labor, Safety, ecc.) senza una struttura qty × prezzo unitario. Non altera la struttura `CostValues` e resta leggibile da qualsiasi editor IFC.

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
  - *Rate Analysis*: unit price breakdown into components (Sub-Contract, Labor, Equipment, Material, Safety) with overhead %, profit %, and rounding. Each component is written as an `IfcCostValue` with `Category`, `AppliedValue` (qty × unit price), and `UnitBasis` (`IfcNumericMeasure(qty)` + unit entity) for full round-trip. Source rate references are tracked in `Description` as `ref:[ID](#ifc:STEP_ID)` with automatic stale-rate detection. Unit entities reuse existing project `IfcSIUnit` instances (e.g. `SQUARE_METRE` for `mq`) or create `IfcConversionBasedUnit` for hours/minutes — minimising user-defined unit pollution in the file.
  - *Quantities (measurement book)*: interactive libretto-delle-misure table for `IfcCostItem.CostQuantities`. Each row has NR × L × B × H fields with live partial computation and a running total. Writes one `IfcQuantityXxx` per row using the IFC4 `Formula` attribute for the expression.

- **BoQ → Schedule of Rates** — extracts leaf items from a Bill of Quantities and transfers them to a Schedule of Rates (new or existing), with automatic deduplication, conflict detection, and an interactive per-item diff resolver.

- **Prints Manager** — PDF export for cost documents, powered by [Typst](https://typst.app):
  - *Export Schedule to PDF*: renders the active `IfcCostSchedule` to PDF via `Ifc5DPdfWriter` (ifc5d / IfcOpenShell) with configurable options (document type, rates visibility, quantity breakdown, summary page, cover).
  - *Export Rate Analysis to PDF*: generates a **scheda analisi prezzi** for the active cost item. Data is read **directly from the IFC file** (not from the UI state), so no prior loading in the Rate Analysis editor is required. Components are grouped by category (Sub-Contract, Labor, Equipment, Material, Safety) with a separate header and subtotal per group; the footer shows technical cost, overhead %, profit %, rounding, and final price.
  - *Export Sheets to PDF*: converts Bonsai Drawing SVG sheets to PDF, saved alongside the originals; opens generated files automatically.
  - **IFC convention:** applying a rate analysis via the Rate Analysis editor sets `IfcCostItem.ObjectType = "RATE_ANALYSIS"` on the item. This marker reliably distinguishes items with a genuine unit-price breakdown from prezzario items that carry Labour/Safety cost values as category incidences only. It does not affect the `CostValues` structure and is readable by any IFC-compliant tool.

- **Bulk Update Cost Schedule** — batch-updates unit prices in the active Cost Schedule from the loaded price list, with a preview before applying.

- **Cost Item Classification** — assigns classification codes (SOA, DM17, TOL) to IFC cost items and generates a financial summary by category with amounts and percentages. Classification systems are loaded automatically from IFC4X3 files in `src/data/classifications/`. The TOL system covers all 20 Tipologie Omogenee di Lavorazione defined in GU 31-12-2024 n.305.
