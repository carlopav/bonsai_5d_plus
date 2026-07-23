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
- **Fixed** — un prezzo piatto, con lista **editabile inline** (categoria, nome, valore per riga) e un'**unica unità di misura condivisa** per l'intera voce.
- **Rate Analysis** — costruisce l'**analisi del prezzo** scomponendo il costo unitario in componenti elementari (Sub-Contract, Labor, Equipment, Material, Safety + NONE per valori liberi), ciascuno con descrizione, quantità, unità di misura, prezzo unitario. Un componente può essere importato direttamente da una voce del Rate List; se il prezzo della tariffa sorgente cambia dopo l'applicazione, il componente viene evidenziato con un bottone di aggiornamento rapido. Un componente **free-form** (non collegato a una tariffa) ha anche un campo **descrizione estesa** editabile, che compare nella stampa sotto il nome; per i componenti collegati la descrizione estesa arriva invece dalla voce di prezzario sorgente e non è editabile qui.

  **Ricarichi (dalla v0.0.18)** — i totali seguono la sequenza della scheda "nuovo prezzo", con le tre percentuali **cumulative sul progressivo**:

  ```
  sicurezza = totale tecnico × sic%
  sg        = (totale tecnico + sicurezza) × spese generali%
  utile     = (totale tecnico + sicurezza + sg) × utile%
  ```

  **Costi della sicurezza** è una percentuale a sé, accanto a spese generali e utile, con default 0% — da non confondere con la *categoria* `Safety` dei componenti, che resta una riga di costo con quantità e prezzo unitario.

  Ogni componente porta un flag **Soggetto a ricarichi** (attivo di default): le voci di prezzario il cui prezzo incorpora già sicurezza, spese generali e utile vanno disattivate, così restano fuori dalla base dei ricarichi e vengono sommate **dopo** il totale ricaricato, in una sezione separata. I subtotali per categoria contano le sole voci soggette.

  **Unità di misura** — sia Fixed (unità unica per la voce) sia i singoli componenti di Rate Analysis (+ l'unità del prezzo finale) condividono lo stesso selettore dinamico: propone prima le unità **dichiarate nel progetto IFC corrente** (`IfcProject.UnitsInContext`), mostrate esattamente come le rappresenta IFC (es. `AREAUNIT / SQUARE_METRE`, riusando `bonsai.tool.Cost.format_unit`) — nessuna traduzione in abbreviazioni "umane". Un'unità già usata sulla voce caricata ma non dichiarata nel progetto (entità legacy) resta comunque selezionabile; `Custom…` copre il resto come testo libero. L'unità scelta viene registrata anche quando la quantità di riga è 0 (componente non ancora misurato), perché l'unità resta un'informazione valida a sé e la colonna "Unità" del BoQ in PDF/ODS la legge a prescindere dal valore della quantità.

  **Struttura IFC scritta** (Rate Analysis): un **`IfcCostValue` sommario** con `AppliedValue` = prezzo finale, `UnitBasis` = `IfcMeasureWithUnit(1.0, unità_voce)`, `ArithmeticOperator = ADD`; i **componenti elementari** come sotto-entità in `Components` (ognuno con `Category`, `AppliedValue` = qty × prezzo unitario, `UnitBasis` = qty + unità); **sicurezza, spese generali, utile e arrotondamento** come ulteriori `Components` (`Category` = `"Safety Percentage"` / `"Overhead"` / `"Profit"` / `"Rounding"`, con la percentuale nel `Name`). La categoria `"Safety Percentage"` è deliberatamente distinta da `"Safety"`, che identifica i componenti di costo. Il marcatore `IfcCostItem.ObjectType = "RATE_ANALYSIS"` distingue le voci con analisi prezzi vera dalle voci prezzario che espongono solo incidenze di categoria.

  Il campo `IfcCostValue.Description` del componente ha due usi alternativi: per un componente **collegato** a una tariffa contiene il riferimento `ref:[Identificazione](#ifc:STEP_ID)`; per un componente **free-form** contiene la sua descrizione estesa.

  **⚠️ Convenzione posizionale — il flag "Soggetto a ricarichi" non è un campo.** `IfcCostValue` non ha un attributo libero adatto e, non essendo un'entità radicata (`IfcAppliedValue` non ha supertipo, quindi niente `GlobalId`), **non può partecipare a una `IfcRelAssignsToControl`** come fanno due `IfcCostItem`. Il flag è quindi portato dall'**ordine** dei `Components` — che a schema IFC è una `LIST`, quindi ordinata e stabile:

  > I componenti che precedono la prima CostValue di ricarico o arrotondamento (`Safety Percentage`, `Overhead`, `Profit`, `Rounding`) sono soggetti ai ricarichi; quelli che la seguono sono già comprensivi.

  `Overhead`, `Profit` e `Rounding` vengono scritti **sempre**, anche a 0%, così il confine esiste in ogni caso. I file salvati prima della v0.0.18 hanno tutti i componenti prima del blocco e rileggono quindi come soggetti a ricarico: nessuna migrazione necessaria. **Chiunque scriva `Components` deve preservare quest'ordine**, altrimenti la classificazione cambia senza alcun segnale.

**Tariffe condivise (rate linking)** — un'analisi prezzi/EPU può **controllare** una o più voci in altri schedule (`IfcRelAssignsToControl`), così un aggiornamento di prezzo si propaga senza dover editare ogni computo. Header dedicato in cima al pannello:
- voce **controllata** da una tariffa: stato sync (✓/✗), "Load Controlling Item" per aprire la tariffa sorgente, "Resync from rate" (solo se fuori sync), "Unlink from Rate" (scollega mantenendo i valori correnti), "Make Unique" (scollega copiando prima Nome/Descrizione), "Duplicate Rate" (clona la tariffa e ricollega la voce alla copia, per farla divergere senza toccare l'originale)
- voce che **controlla** altre voci: conteggio + stato sync, "Propagate now…" (dialogo con anteprima delle voci coinvolte, propaga nome/descrizione/valori) e "Resync values" (ricondivide solo i valori, silenzioso)
- strumenti a livello di intero schedule (Audit / Resync all) sono nel **Toolbox**, vedi sotto

**Quantities (libretto delle misure)** — Lettura e modifica di `IfcCostItem.CostQuantities` tramite un libretto delle misure interattivo. Ogni riga ha campi **NR × L × B × H** con parziale calcolato in tempo reale e totale complessivo a fondo pannello. Un picker unità IFC-nativo dedicato (indipendente da quello del prezzo — le quantity possono avere una propria unità di misura, es. importate da un'altra fonte) determina sia il sottotipo `IfcQuantity` scritto nel file sia l'entity stampata sull'attributo `Unit` di ogni quantity; al caricamento viene proposta l'unità già salvata sulle quantity esistenti, o quella del prezzo come suggerimento iniziale per un item senza quantity. La formula viene salvata nell'attributo `Formula` (IFC4) con round-trip completo.

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

Entrambi gli export condividono l'opzione **Round Values Before Summing** (attiva di default), che rende il documento ripercorribile a mano — vedi [Arrotondamenti e ripercorribilità a mano](#arrotondamenti-e-ripercorribilità-a-mano).

**Export Rate Analysis to PDF** — Stampa la **scheda analisi prezzi** della voce attiva (item pinnato nell'editor oppure item selezionato nel pannello Bonsai). I dati vengono letti **direttamente dall'IFC**, non dalla UI, quindi non è necessario aver caricato la voce nell'editor prima di esportare. **Export All Rate Analyses to PDF** esporta in un unico PDF tutte le voci con analisi prezzi presenti nello schedule attivo.

L'impaginazione segue la scheda "nuovo prezzo":

```
MANODOPERA / NOLI / MATERIALI …            voci raggruppate per categoria,
                                           con subtotale per gruppo
                    Totale tecnico :          534,50
    Costi della sicurezza 2,0% di 534,50 :     10,69
          Spese generali 14,0% di 545,19 :     76,33
        Utile d'impresa 10,0% di 621,52 :      62,15
                           TOTALE :           683,67
Voci di prezzario di riferimento già comprensive di oneri
per la sicurezza, spese generali e utile d'impresa
  [B.09.11] Ponteggio a noleggio            210,00
  Subtotale voci di prezzario di riferimento : 245,00
                           TOTALE :           928,67
                   Arrotondamento :            −0,20
PREZZO FINALE                    cad          928,47
```

Dettagli di lettura:
- ogni percentuale esplicita **l'importo su cui è calcolata**, così il concatenarsi dei ricarichi è verificabile riga per riga;
- la sezione delle voci già comprensive compare **solo se ce ne sono**: un'analisi ordinaria mantiene la sequenza classica (totale tecnico → ricarichi → arrotondamento → prezzo finale);
- ogni componente riporta il **codice di prezzario** prima del nome, quando è collegato a una tariffa;
- il flag **Show Component Descriptions** (finestra di dialogo all'export, **disattivo di default**) aggiunge sotto ogni componente la sua descrizione estesa — quella della voce di prezzario per i componenti collegati, quella propria per i free-form. Disattivo, ogni componente occupa una riga sola;
- il **prezzo finale** riporta l'unità di misura della voce; un'unità non definita stampa `-`.

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

## ⚠️ Unità di misura — stato e limiti noti

Bonsai5D+ tratta l'unità di misura come **entità IFC esplicita** (`IfcSIUnit` / `IfcConversionBasedUnit` / `IfcContextDependentUnit`), non come una stringa o un'abbreviazione a parte, sia per il prezzo che per la quantità:

- **Prezzo** (`IfcCostValue.UnitBasis`) e **quantità** (`IfcPhysicalSimpleQuantity.Unit`, dalla **v0.0.15**) portano entrambi l'unità direttamente sull'entità, invece di dipendere implicitamente dall'unità di progetto (`IfcProject.UnitsInContext`) come fallback silenzioso. Prima della v0.0.15 questo fallback poteva **reinterpretare silenziosamente una quantità nell'unità sbagliata** (es. voce di prezzario misurata in metri, progetto in millimetri → valore letto ×1000 errato), senza alcun avviso a video.
- Nel Cost Item Editor i due picker — unità del **prezzo** (Fixed/Rate Analysis) e unità delle **Quantities** (libretto delle misure) — sono **volutamente indipendenti**: le quantità possono arrivare da una fonte diversa dal prezzo (import da prezzario, take-off geometrico, file precedenti) e non vengono mai forzate a coincidere. Al caricamento il picker delle Quantities riflette l'unità realmente salvata su ogni quantità; solo per un item senza quantità propone quella del prezzo come suggerimento iniziale.
- **Not battle tested**: introdotto nella sessione del 2026-07-17. Copre quantità legacy senza `.Unit` salvate da versioni precedenti dell'addon, cost item con sole quantità e nessun cost value, ed export BoQ con unità di prezzo e quantità divergenti, ma manca ancora l'uso prolungato su dati reali.
- **Limite noto, non ancora risolto**: nessuna **conversione di fattore** tra unità diverse (es. prezzario in dm², progetto IFC in m²). Il prezzo deve già essere espresso nell'unità corretta al momento dell'assegnazione della tariffa; l'addon non applica alcun fattore di conversione automatico.

---

## Arrotondamenti e ripercorribilità a mano

Un documento di costo consegnato dev'essere **verificabile con la calcolatrice**: ogni numero stampato dev'essere ricalcolabile dai numeri stampati sopra di esso. Questo vale solo se le somme sono prese sui valori **già arrotondati**, non sul valore a piena precisione poi arrotondato in fase di stampa.

**Due fronti distinti:**

- **Dati salvati in IFC** — allineati allo standard Bonsai: **precisione piena, nessun arrotondamento semantico**, import compreso. Bonsai (`ifcopenshell.util.cost`) scrive e somma i valori verbatim; l'unico arrotondamento nella sua UI è di visualizzazione. Bonsai5D+ fa lo stesso: le `IfcQuantity` e gli `IfcCostValue.AppliedValue` conservano il valore della fonte (il parser dei prezzari ripulisce solo il rumore float a 6 decimali, che è igiene numerica, non una policy di precisione).
- **Output PDF/ODS** — arrotondamento "presto": ogni quantità e ogni importo viene arrotondato **prima** di essere sommato, così il totale di una colonna è la somma delle cifre stampate in quella colonna.

**Convenzione di precisione:** fattori atomici del libretto (NR × L × B × H) a **3 decimali**; parziale di misura, quantità totale, prezzi e importi a **2 decimali**. La somma delle sotto-misure usa i parziali arrotondati (tre righe da 0,005 → 0,01 + 0,01 + 0,01 = 0,03, non 0,015 → 0,02): è la sola forma ripercorribile a mano.

**Cosa resta tollerato:** la **formula** stampata accanto a un parziale (es. `3,70*6,81` = 25,197 mentre la riga mostra 25,20) documenta come è stata ottenuta la misura; è la colonna a dover tornare, non l'eval della formula. Anche l'analisi prezzi mantiene i suoi prezzi unitari derivati a piena precisione.

**Opzione di export `Round Values Before Summing`** (finestra di dialogo PDF e ODS, **attiva di default**): spenta, ripristina l'aritmetica grezza a piena precisione — le stesse cifre del pannello Cost nativo di Bonsai — utile per confrontare quando un totale va spiegato. Nel PDF i subtotali di sezione tornano allora al `TotalPrice` di ifc5d; nell'ODS le formule vive passano da `=ROUND(qta*prezzo;2)` a `=qta*prezzo`.

**⚠️ Limite strutturale, accettato:** con l'arrotondamento attivo le **quantità** tornano ovunque, Bonsai nativo compreso, mentre gli **importi di sezione** possono scostarsi di qualche centesimo dal pannello di Bonsai — che somma i prodotti `qta × prezzo` a piena precisione. Non è aggirabile: `ifcopenshell.util.cost.calculate_applied_value` ignora l'`AppliedValue` memorizzato e ricalcola sempre da zero per le voci con figli, quindi non c'è modo di far arrotondare i totali a Bonsai. L'elaborato consegnato dev'essere ripercorribile a mano; il pannello di Bonsai resta uno strumento di lavoro. I file IFC preesistenti (quantità a più decimali) stampano comunque coerenti, perché l'arrotondamento è applicato in lettura.

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
    - *Fixed*: a flat price with an **inline-editable list** (category, name, value per row) and **one shared unit of measure** for the whole item.
    - *Rate Analysis*: unit price breakdown into components (Sub-Contract, Labor, Equipment, Material, Safety), following the Italian "nuovo prezzo" worksheet. Since **v0.0.18** the three markups — safety costs %, overhead % and profit % — **compound on the running total**: `safety = technical × safety%`, `overhead = (technical + safety) × overhead%`, `profit = (technical + safety + overhead) × profit%`. Safety costs is a percentage in its own right, not to be confused with the `Safety` component *category*, which stays a cost line with a quantity and a unit price.

      Every component carries a **Subject to markups** flag (on by default). Price-list items whose price already includes safety costs, overhead and profit are switched off: they stay out of the markup base and are added **after** the marked-up subtotal, in a section of their own. Per-category subtotals count subject components only. A **free-form** component (not linked to a rate) also has an editable **extended description** shown under its name in the print; a linked component takes that text from its source price-list item instead.

      Written as a **nested `IfcCostValue` structure**: one summary value carrying the final price and the item's unit of measure (`UnitBasis = IfcMeasureWithUnit(1.0, unit)`), with all components plus the safety/overhead/profit/rounding entries in `Components` (`ArithmeticOperator = ADD`, `Category` = `"Safety Percentage"` / `"Overhead"` / `"Profit"` / `"Rounding"`, percentage held in `Name`). Note `"Safety Percentage"` is deliberately distinct from `"Safety"`. Each component carries `Category`, `AppliedValue` (line total), and `UnitBasis` (qty + unit entity) for full round-trip. A component's `Description` has two alternative uses: the source rate reference `ref:[ID](#ifc:STEP_ID)` when linked (with automatic stale-rate detection), its own extended description when free-form. `IfcCostItem.ObjectType = "RATE_ANALYSIS"` marks items with a genuine qty × unit-price breakdown, distinguishing them from prezzario entries that carry aggregate category incidences only.

      **⚠️ Positional convention — the "subject to markups" flag is not a field.** `IfcCostValue` has no free attribute for it and, not being a rooted entity (`IfcAppliedValue` has no supertype, hence no `GlobalId`), **cannot take part in an `IfcRelAssignsToControl`** the way two `IfcCostItem`s do. The flag is carried by the **order** of `Components` — a `LIST` in the IFC schema, therefore ordered and stable:

      > Components preceding the first markup or rounding CostValue (`Safety Percentage`, `Overhead`, `Profit`, `Rounding`) are subject to markups; those following it already include them.

      `Overhead`, `Profit` and `Rounding` are **always** written, even at 0%, so the boundary always exists. Files written before v0.0.18 keep every component ahead of the block and therefore read back as subject to markups — no migration needed. **Anything writing `Components` must preserve that order**, or the classification changes with no signal.
    - *Units*: Fixed's single item-wide unit, each Rate Analysis component's unit, and the Rate Analysis final-price unit all share one dynamic picker. It offers the units actually **declared on the current IFC project** (`IfcProject.UnitsInContext`) first, shown exactly as IFC represents them (reusing `bonsai.tool.Cost.format_unit`, e.g. `AREAUNIT / SQUARE_METRE`) rather than translated to a human abbreviation; a unit already used on the loaded item but not declared on the project (legacy entity) stays selectable too; `Custom…` covers anything else as free text. A chosen unit is recorded even when the row's quantity is 0 (an unmeasured component) — it's still meaningful, and the BoQ PDF/ODS "Unit" column reads it regardless of the quantity value.
  - *Shared rates (rate linking)*: a rate-analysis/price-list item can **control** one or more items in other schedules (`IfcRelAssignsToControl`), so a price update propagates instead of having to edit every BoQ line by hand. A dedicated header at the top of the panel offers, for a **controlled** item: sync status, "Load Controlling Item", "Resync from rate" (when out of sync), "Unlink from Rate" (detach, keep current values), "Make Unique" (detach after copying the controller's Name/Description), "Duplicate Rate" (clone the controller and relink the item to the copy, so it can diverge independently); for an item that **controls** others: dependent count + sync status, "Propagate now…" (preview dialog, pushes name/description/values) and "Resync values" (silent value re-share). Schedule-wide audit/resync tools live in the Toolbox (below).
  - *Quantities (measurement book)*: interactive libretto-delle-misure table for `IfcCostItem.CostQuantities`. Each row has NR × L × B × H fields with live partial computation and a running total. A dedicated IFC-native unit picker — independent of the price's unit, since quantities may come from a source (import, takeoff, a previous file) with their own unit of measure — determines both the `IfcQuantityXxx` subtype written per row and the entity stamped on each quantity's `Unit` attribute. On load it's pre-filled from whatever unit is actually stored on existing quantities, falling back to the item's price unit as a starting suggestion only when there are none yet. The formula is written to the IFC4 `Formula` attribute for full round-trip.

- **Rate List Importer** — imports Italian regional price lists (XML/XPWE formats: Veneto, Lombardia, Toscana, Liguria, Basilicata, SIX, XPWE/Primus, or any Schedule of Rates already in the current IFC project) and exposes them as a browsable list in Blender's sidebar. Items can be assigned to cost items in one click, with automatic component breakdown (labor, equipment, material, safety).

- **Cost Item Classification** — assigns classification codes (SOA, DM17, TOL) to IFC cost items and generates a financial summary by category with amounts and percentages, exportable to **CSV** in one click. Classification systems are loaded automatically from IFC4X3 files in `src/data/classifications/`. The TOL system covers all 20 Tipologie Omogenee di Lavorazione defined in GU 31-12-2024 n.305.

- **Tenders Manager** — bid comparison workflow against a base Bill of Quantities: *Create Tender Schedule* duplicates the source BoQ as a new `TENDER` schedule for a bidding company (full price or a percentage discount, optionally excluding one item such as safety costs); *Offered Prices* is a per-item dialog to enter a bidder's unit prices with a live running total; *Bid Comparison* shows every tender against the base estimate (total, absolute/percentage difference, lowest-bid highlight), with a per-item **TSV** export to clipboard.

- **Prints Manager** — document export for cost data, powered by [Typst](https://typst.app) for PDFs; generated files open automatically:
  - *Export Schedule to PDF*: renders the active `IfcCostSchedule` to PDF via `Ifc5DPdfWriter` (ifc5d / IfcOpenShell) with configurable options (document type, rates visibility, quantity breakdown, summary page, cover).
  - *Export Schedule to ODS*: the same export as an **OpenDocument Spreadsheet** with live calculation formulas (not static values) — same options as the PDF — so the schedule stays editable in LibreOffice Calc. Both exports share the **Round Values Before Summing** option (on by default) that makes the document hand-checkable — see [Rounding and hand-checkability](#rounding-and-hand-checkability).
  - *Export Rate Analysis to PDF*: generates a **scheda analisi prezzi** for the active cost item. Data is read **directly from the IFC file** (not from the UI state), so no prior loading in the Cost Item Editor is required. *Export All Rate Analyses to PDF* does the same for every rate-analysis item in the active schedule, in a single PDF.

    The sheet follows the "nuovo prezzo" worksheet: components grouped by category with a subtotal per group, the technical total, the compounding markups, then — **only when there are any** — the price-list items that already include those markups in their own section with a subtotal, then a total of everything, rounding, and the final price. Each percentage spells out **the amount it is taken on** (`Spese generali 14,0% di 545,19`), so the compounding is verifiable line by line. Components show their price-list code ahead of the name when linked to a rate. The **Show Component Descriptions** flag (export dialog, **off by default**) adds each component's extended description below its name — the source price-list item's for linked components, its own for free-form ones; off, each component takes a single line. The final price carries the item's unit of measure, and an undefined unit prints `-`.
  - *Export Labor Cost Breakdown to PDF*: a **labor-incidence schedule** for the active Cost Schedule — the Bill-of-Quantities layout with two cost columns (total cost and labor cost) and a per-row labor incidence %, plus a final summary page with the incidence per chapter and the general total. Uses the same `Ifc5DCsvWriter` extractor as the BoQ ("Labor" category column); the incidence only appears for items carrying a top-level Labor `IfcCostValue`.
  - **IFC structure:** all cost items (both imported price-list entries and rate-analysis items) use a nested `IfcCostValue` structure: a summary value with the total price and `UnitBasis` (item unit of measure), and monetary category sub-components in `Components` (`ArithmeticOperator = ADD`). Items with no category incidences carry only the summary value.

- **Import / Export** — whole-schedule import/export to/from **XPWE** (Primus and compatible), as opposed to the single-rate import of the Rate List Importer: *Import XPWE* creates a new EPU price-list schedule and, when present in the file, a linked CME (computo) schedule, with options to flatten the EPU chapter hierarchy and to import each measurement row as a separate IFC quantity (NR×L×B×H in the `Formula` attribute) instead of a single total; *Export XPWE* writes the active schedule out, rebuilding the price list from its linked Schedule of Rates when present or synthesising it from the items themselves.

- **Toolbox** — bulk maintenance tools for the active Cost Schedule, grouped under one collapsible panel:
  - *BoQ → Schedule of Rates*: extracts leaf items from a Bill of Quantities and transfers them to a Schedule of Rates (new or existing), with automatic deduplication, conflict detection, and an interactive per-item diff resolver, plus a TSV clipboard report.
  - *Bulk Update from Rate List*: batch-updates unit prices in the active Cost Schedule from the loaded price list, with a preview before applying.
  - *Reorder Cost Schedule*: renumbers every item's `Identification` hierarchically (1, 1.1, 1.1.1, 1.2, 2, …) — "Reorder All" resets the whole structure, "Keep Levels Above" renumbers from a chosen level down, leaving higher levels untouched and continuing existing numeric identifications rather than resetting them.
  - *Rate Sync*: schedule-wide tools for the shared-rate linking described above — "Audit schedule" reports how many rate-linked items are out of sync; "Resync all" realigns every out-of-sync item in the active schedule with its controlling rate.

### ⚠️ Units of measure — status and known limits

Bonsai5D+ treats the unit of measure as an **explicit IFC entity** (`IfcSIUnit` / `IfcConversionBasedUnit` / `IfcContextDependentUnit`), not a string or abbreviation on the side, for both price and quantity:

- **Price** (`IfcCostValue.UnitBasis`) and **quantity** (`IfcPhysicalSimpleQuantity.Unit`, since **v0.0.15**) both carry the unit directly on the entity, instead of implicitly depending on the project's unit (`IfcProject.UnitsInContext`) as a silent fallback. Before v0.0.15 that fallback could **silently reinterpret a quantity in the wrong unit** (e.g. a price-list item measured in metres, project in millimetres → value read out ×1000 wrong), with no warning shown.
- In the Cost Item Editor, the **price** unit picker (Fixed/Rate Analysis) and the **Quantities** unit picker (measurement book) are **deliberately independent**: quantities may come from a different source than the price (price-list import, geometric takeoff, a previous file) and are never forced to match. On load, the Quantities picker reflects whatever unit is actually stored on the item's quantities; it only suggests the price's unit as a starting point for an item with no quantities yet.
- **Not battle tested**: introduced in the 2026-07-17 session. Covers legacy quantities with no `.Unit` written by older addon versions, cost items with quantities but no cost value, and BoQ export with diverging price/quantity units, but still lacks extended use against real-world data.
- **Known, unresolved limitation**: no **conversion factor** between different units (e.g. a price list in dm², IFC project in m²). The price must already be expressed in the correct unit when the rate is assigned; the addon applies no automatic conversion factor.

### Rounding and hand-checkability

A delivered cost document must be **checkable with a calculator**: every printed figure must be recomputable from the figures printed above it. That only holds if sums are taken over the **already-rounded** values, not over the full-precision value rounded at print time.

**Two distinct fronts:**

- **Data stored in IFC** — aligned with the Bonsai standard: **full precision, no semantic rounding**, import included. Bonsai (`ifcopenshell.util.cost`) writes and sums values verbatim; the only rounding in its UI is for display. Bonsai5D+ does the same — `IfcQuantity` values and `IfcCostValue.AppliedValue` keep the source figure (the price-list parser only trims float noise to 6 places, which is numeric hygiene, not a precision policy).
- **PDF/ODS output** — rounded early: every quantity and amount is rounded **before** it is summed, so a column's total is the sum of the figures printed in it.

**Precision convention:** measurement-book atomic factors (NR × L × B × H) at **3 decimals**; measurement partial, total quantity, prices and amounts at **2 decimals**. A row's quantity is the sum of its rounded sub-measurements (three rows of 0.005 → 0.01 + 0.01 + 0.01 = 0.03, not 0.015 → 0.02): the only form that reproduces by hand.

**What stays tolerated:** the **formula** printed beside a partial (e.g. `3.70*6.81` = 25.197 while the row shows 25.20) documents how the measure was obtained; it is the column that must add up, not the formula's eval. Rate analysis likewise keeps its derived unit prices at full precision.

**Export option `Round Values Before Summing`** (PDF and ODS dialog, **on by default**): turn it off to restore the raw full-precision arithmetic — the same figures Bonsai's own Cost panel shows — for comparison when a total needs explaining. In the PDF, section subtotals then fall back to ifc5d's `TotalPrice`; in the ODS the live formulas switch from `=ROUND(qty*rate;2)` to `=qty*rate`.

**⚠️ Structural limit, accepted:** with rounding on, **quantities** reconcile everywhere, Bonsai's native panel included, but **section amounts** may differ by a few cents from Bonsai's panel — which sums the `qty × rate` products at full precision. This is not avoidable: `ifcopenshell.util.cost.calculate_applied_value` ignores the stored `AppliedValue` and always recomputes from scratch for items with children, so there is no way to make Bonsai round its totals. The delivered document must be hand-checkable; Bonsai's panel stays a working tool. Pre-existing IFC files (quantities at more decimals) still print consistently, because the rounding is applied on read.

**Requirements:** Blender 4.0+ and a recent Bonsai BIM **daily/alpha build from 2026-06-17 onward** (`alpha260617+`). PDF export of the bill of quantities relies on the `ifc5d` fixes merged into ifcopenshell on 2026-06-16 ([#8175](https://github.com/IfcOpenShell/IfcOpenShell/pull/8175) escape quantity names, [#8176](https://github.com/IfcOpenShell/IfcOpenShell/pull/8176) include the quantity formula); with older builds the BoQ print fails with a JSON parsing error.
