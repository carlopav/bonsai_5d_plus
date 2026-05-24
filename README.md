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

### BoQ → Schedule of Rates
Estrae le voci foglia di un **Bill of Quantities** (`IfcCostSchedule` di tipo `PRICEDBILLOFQUANTITIES` o `UNPRICEDBILLOFQUANTITIES`) e le trasferisce in uno **Schedule of Rates**, creandolo ex novo oppure aggiornando uno esistente.

Gestisce automaticamente:
- deduplicazione delle voci (stessa Identification + Name)
- rilevamento di conflitti (stesso codice, dati diversi)
- confronto puntuale tra BoQ e SoR con diff inline e risoluzione interattiva voce per voce
- report copiabile negli appunti in formato TSV (per LibreOffice Calc)

### Bulk Update Cost Schedule
Aggiorna in blocco i valori unitari del Cost Schedule attivo leggendo le tariffe dal prezzario caricato, con anteprima delle modifiche prima di applicarle.

---

## Installazione

### Per lo sviluppo (symlink)
```
mklink /J "%APPDATA%\Blender Foundation\Blender\<versione>\scripts\addons\bonsai_5d_plus" "<percorso_repo>\src"
```
Abilitare l'addon in *Edit > Preferences > Add-ons* cercando **Bonsai5D+**.

### Release
Zippare il contenuto della cartella `src/` (non la cartella stessa). Il file `.zip` può essere installato direttamente da Blender tramite *Edit > Preferences > Add-ons > Install*.

---

## Dipendenze

- [Bonsai BIM](https://bonsaibim.org) (addon Blender)
- [ifcopenshell](https://ifcopenshell.org) (incluso in Bonsai)
- Blender 4.0 o superiore

---

## Licenza

Da definire.
