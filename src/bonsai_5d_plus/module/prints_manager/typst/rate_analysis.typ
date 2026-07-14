// Scheda Analisi Prezzi (Rate Analysis)
// One sheet per cost item: cost components grouped by category, with
// overheads, profit and rounding, ending in the final unit price.
//
// author: carlo pavan
// year: 2026

#import "common.typ": *

#let category_abbr = (
  "Sub-Contract": "OPC",
  "Labor":        "LAV",
  "Equipment":    "NOL",
  "Material":     "MAT",
  "Safety":       "SIC",
)

#let arrange_row(row) = {
  let rt = row.at("row_type", default: "")

  if rt == "CATEGORY_HEADER" {
    let label = row.at("description", default: "")
    (
      table.cell(
        colspan: 6,
        fill: gray.transparentize(85%),
        stroke: (top: 0.75pt, bottom: 0.4pt + gray),
        inset: (left: 2mm, y: 1.5mm),
        align: left,
      )[#strong[#upper(label)]],
    )

  } else if rt == "COMPONENT" {
    let cat = category_abbr.at(row.at("category", default: ""), default: "")
    let qty = { let v = row.at("qty", default: ""); if v == "" { 0.0 } else { float(v) } }
    let up  = { let v = row.at("unit_price", default: ""); if v == "" { 0.0 } else { float(v) } }
    let lt  = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(align: center)[#text(size: 7pt)[#cat]],
      table.cell(inset: (left: 3mm))[#row.at("description", default: "")],
      table.cell(align: right)[#format-decimal(qty, places: 3)],
      table.cell(align: center)[#row.at("unit", default: "")],
      table.cell(align: right)[#format-decimal(up)],
      table.cell(align: right)[#format-decimal(lt)],
    )

  } else if rt == "CATEGORY_SUBTOTAL" {
    let val   = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    let label = row.at("description", default: "")
    (
      table.cell(
        colspan: 5,
        stroke: (top: 0.4pt + gray, bottom: 0.75pt),
        align: right,
      )[#text(style: "italic")[Subtotale #label :]],
      table.cell(
        stroke: (top: 0.4pt + gray, bottom: 0.75pt),
        align: right,
      )[#strong[#format-decimal(val)]],
    )

  } else if rt == "SUBTOTAL" {
    let val = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(colspan: 5, inset: (top: 3mm), align: right)[
        #text(style: "italic")[#row.at("description", default: "") :]
      ],
      table.cell(inset: (top: 3mm), align: right)[#format-decimal(val)],
    )

  } else if rt == "OVERHEAD" or rt == "PROFIT" {
    let val     = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    let pct_raw = row.at("pct", default: "")
    let pct_str = if pct_raw == "" or pct_raw == "0.0" { "" } else { "  " + pct_raw + "%" }
    (
      table.cell(colspan: 5, align: right)[
        #text(style: "italic")[#row.at("description", default: "") #pct_str :]
      ],
      table.cell(align: right)[#format-decimal(val)],
    )

  } else if rt == "ROUNDING" {
    let val = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(colspan: 5, align: right)[
        #text(style: "italic")[#row.at("description", default: "") :]
      ],
      table.cell(align: right)[#format-decimal(val)],
    )

  } else if rt == "TOTAL" {
    let val = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(
        colspan: 5,
        fill: gray.transparentize(80%),
        stroke: (top: 0.75pt),
        align: right,
      )[#strong[#upper(row.at("description", default: "PREZZO FINALE")) :]],
      table.cell(
        fill: gray.transparentize(80%),
        stroke: (top: 0.75pt),
        align: right,
      )[#strong[#format-decimal(val)]],
    )

  } else {
    ()
  }
}


#let render_analysis(
  csv_path: "",
  item_identification: "",
  item_name: "",
  item_description: "",
  project_currency: "EUR",
) = {
  // — Item header —
  table(
    columns: (35mm, 1fr),
    stroke: 0.75pt,
    inset: (x: 3mm, y: 2mm),
    align: (left, left),
    table.header(
      table.cell(
        fill: gray.transparentize(80%),
        inset: (x: 3mm, y: 1mm),
      )[#text(size: 6.5pt, weight: "bold")[CODICE]],
      table.cell(
        fill: gray.transparentize(80%),
        inset: (x: 3mm, y: 1mm),
      )[#text(size: 6.5pt, weight: "bold")[VOCE]],
    ),
    [#text(size: 11pt)[#strong[#item_identification]]],
    [#text(size: 11pt)[#strong[#upper(item_name)]]],
  )

  // — Description box —
  if item_description != "" {
    v(1mm)
    block(
      width: 100%,
      inset: (x: 2mm, y: 1.5mm),
      stroke: 0.4pt + gray,
    )[#text(size: 7pt)[#item_description]]
  }

  v(3mm)

  // — Rate analysis table —
  let data = csv(csv_path, row-type: dictionary)

  table(
    columns: (12mm, 1fr, 20mm, 12mm, 22mm, 22mm),
    align: (center, left, right, center, right, right),
    stroke: none,
    inset: (x: 1.5mm, y: 1.5mm),
    table.header(
      text(size: 7pt, weight: "bold")[Cat.],
      text(size: 7pt, weight: "bold")[Descrizione],
      text(size: 7pt, weight: "bold")[Qtà],
      text(size: 7pt, weight: "bold")[U.M.],
      text(size: 7pt, weight: "bold")[P.U. (#project_currency)],
      text(size: 7pt, weight: "bold")[Importo (#project_currency)],
    ),
    ..data.map(row => arrange_row(row)).flatten(),
  )
}


// Single-item entry point: `#show: project.with(...)`.
#let project(
  csv_path: "",
  item_identification: "",
  item_name: "",
  item_description: "",
  project_currency: "EUR",
  body,
) = {
  page-frame(
    header: std-header(item_identification, item_name),
    [
      #render_analysis(
        csv_path: csv_path,
        item_identification: item_identification,
        item_name: item_name,
        item_description: item_description,
        project_currency: project_currency,
      )
      #body
    ],
  )
}
