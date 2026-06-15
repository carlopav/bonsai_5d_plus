# Prezzari — test assets

Sample price lists used to develop and test the rate-list parsers
(`src/bonsai_5d_plus/core/parsers.py`) and the cost categorisation
(labor/equipment/material → `IfcCostValue.Category`).

The actual price-list files are **not committed** (size + licensing) — see
`.gitignore`. Drop the files into the matching folder; the folder structure and
this README are versioned.

## Folder → parser → format

| Folder | Parser class | Format | Source | Status |
|---|---|---|---|---|
| `veneto/` | `ParserXmlVeneto` | XML (elenco + analisi) | Prezzario Regionale Veneto (settori RU/AT/PR-A/PR-B) | ✅ categorizzazione fatta |
| `emilia_romagna/` | `ParserXmlSix` | XML formato SIX | Prezzario regionale OO.PP. Emilia-Romagna | ✅ categorizzazione fatta (sezioni) |
| `friuli_venezia_giulia/` | `ParserXmlSix` | XML formato SIX | Prezzario regionale FVG | ✅ categorizzazione fatta (`specie`) |
| `trento/` | `ParserXmlSix` (XML) / `ParserXpwe` (XPWE) | XML SIX + **XPWE** | Prezzario Provincia Autonoma Trento (PAT) | ✅ categorizzazione fatta (sezioni) |
| `toscana/` | `ParserXmlToscana` | XML "strutturato" (ZIP per provincia) | [dati.toscana.it CKAN](https://dati.toscana.it/dataset/prezzario-lavori-pubblici) | ✅ categorizzazione fatta (`livello1`) |
| `liguria/` | `ParserXmlLiguria` | XML (senza analisi) | [appaltiliguria.regione.liguria.it](https://www.regione.liguria.it/homepage/territorio/appalti-pubblici/prezzario.html) | da fare |
| `lombardia/` | `ParserXmlLombardia` | XML (`tipologia_risorsa`) | Prezzario Regione Lombardia OO.PP. | ✅ categorizzazione fatta (`tipologia_risorsa`) |
| `basilicata/` | `ParserXmlBasilicata` | XML | Prezzario Regione Basilicata | da fare |
| `six/` | `ParserXmlSix` | XML formato SIX (`specie` o sezioni) | Emilia-Romagna, FVG, Trento, DEI-BC | ✅ categorizzazione fatta |
| `dei/` | `ParserXpwe` (XPWE) / `ParserXmlSix` (DEI-BC XML) | **XPWE** + XML SIX | DEI 2022 (STR Vision / XPWE) | ✅ categorizzazione fatta — formato preferito (un parser, molti prezzari) |

## Note

- `ParserIfcCostSchedule` legge da IFC, non serve un file qui.
- **XPWE preferito** dove disponibile: copre più prezzari con un solo parser; gli
  open-data regionali (Veneto, Toscana, Liguria) escono però solo in XML nativo.
- La categorizzazione richiede che il formato distingua le voci-risorsa pure
  (manodopera / noli / materiali) dalle opere compiute (composite). Verificare
  il segnale del tipo per ogni formato prima di implementare. Segnali usati:
  SIX → `specie`/`specieId` o titoli di sezione; Toscana → `livello1`
  `descrizionebreve`; Lombardia → `tipologia_risorsa`; XPWE → descrizione del
  capitolo più specifico (super/cap/sotto).
- **File non ancora riconosciuti** dall'auto-detection (`_find_xml_parser`),
  da gestire a parte: `lombardia/F) … Precedente struttura.xml` (vecchio
  schema) e `veneto/analisiPrezzi…xml` (file di sole analisi, root diversa).
