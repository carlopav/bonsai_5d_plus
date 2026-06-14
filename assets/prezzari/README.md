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
| `emilia_romagna/` | da identificare | XML (export da Alice) | Prezzario regionale OO.PP. Emilia-Romagna | da fare |
| `friuli_venezia_giulia/` | da identificare | XML | Prezzario regionale FVG | da fare |
| `trento/` | da identificare | XML + **XPWE** | Prezzario Provincia Autonoma Trento (PAT) | da fare |
| `toscana/` | `ParserXmlToscana` | XML "strutturato" (ZIP per provincia) | [dati.toscana.it CKAN](https://dati.toscana.it/dataset/prezzario-lavori-pubblici) | da fare |
| `liguria/` | `ParserXmlLiguria` | XML (senza analisi) | [appaltiliguria.regione.liguria.it](https://www.regione.liguria.it/homepage/territorio/appalti-pubblici/prezzario.html) | da fare |
| `lombardia/` | `ParserXmlLombardia` | XML (`tipologia_risorsa`) | Prezzario Regione Lombardia OO.PP. | da fare |
| `basilicata/` | `ParserXmlBasilicata` | XML | Prezzario Regione Basilicata | da fare |
| `six/` | `ParserXmlSix` | XML formato SIX | da identificare | da fare |
| `dei/` | `ParserXpwe` | **XPWE** | DEI 2022 (STR Vision / XPWE) | da fare — formato preferito (un parser, molti prezzari) |

## Note

- `ParserIfcCostSchedule` legge da IFC, non serve un file qui.
- **XPWE preferito** dove disponibile: copre più prezzari con un solo parser; gli
  open-data regionali (Veneto, Toscana, Liguria) escono però solo in XML nativo.
- La categorizzazione richiede che il formato distingua le voci-risorsa pure
  (manodopera / noli / materiali) dalle opere compiute (composite). Verificare
  il segnale del tipo per ogni formato prima di implementare.
