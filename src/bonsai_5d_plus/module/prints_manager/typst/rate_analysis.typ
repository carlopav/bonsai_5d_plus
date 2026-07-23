// Scheda Analisi Prezzi (Rate Analysis)
// One sheet per cost item: cost components grouped by category, with
// overheads, profit and rounding, ending in the final unit price.
//
// author: carlo pavan
// year: 2026

#import "common.typ": *

// An undefined unit of measure prints as "-" rather than being left blank, the
// same convention the bill of quantities uses for its unit column.
#let unit-or-dash(u) = if u == "" { "-" } else { u }

// Columns: Descrizione, Qtà, U.M., P.U., Importo. There is no category column —
// each component already sits under its category heading.
#let arrange_row(row) = {
  let rt = row.at("row_type", default: "")

  if rt == "CATEGORY_HEADER" {
    let label = row.at("description", default: "")
    (
      table.cell(
        colspan: 5,
        fill: gray.transparentize(85%),
        stroke: (top: 0.75pt, bottom: 0.4pt + gray),
        inset: (left: 2mm, y: 1.5mm),
        align: left,
      )[#strong[#upper(label)]],
    )

  } else if rt == "COMPONENT" {
    let qty = { let v = row.at("qty", default: ""); if v == "" { 0.0 } else { float(v) } }
    let up  = { let v = row.at("unit_price", default: ""); if v == "" { 0.0 } else { float(v) } }
    let lt  = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    // Price-list code ahead of the name, extended description wrapping below it.
    let ident = row.at("identification", default: "")
    let ext   = row.at("long_description", default: "")
    (
      table.cell(inset: (left: 4mm))[
        #(if ident != "" { text(size: 7pt)[[#ident] ] } else { [] })
        #row.at("description", default: "")
        #(if ext != "" { par(justify: true, text(size: 7pt, ext)) } else { [] })
      ],
      table.cell(align: right)[#format-decimal(qty, places: 3)],
      table.cell(align: center)[#unit-or-dash(row.at("unit", default: ""))],
      table.cell(align: right)[#format-decimal(up)],
      table.cell(align: right)[#format-decimal(lt)],
    )

  } else if rt == "SECTION_HEADER" {
    // Same banded style as the category headers (MATERIALI, MANODOPERA…). The
    // label is a full sentence, so it stays in normal case rather than uppercased.
    let label = row.at("description", default: "")
    (
      table.cell(
        colspan: 5,
        fill: gray.transparentize(85%),
        stroke: (top: 0.75pt, bottom: 0.4pt + gray),
        inset: (left: 2mm, y: 1.5mm),
        align: left,
      )[#strong[#label]],
    )

  } else if rt == "CATEGORY_SUBTOTAL" {
    let val   = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    let label = row.at("description", default: "")
    (
      table.cell(
        colspan: 4,
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
      table.cell(colspan: 4, inset: (top: 3mm), align: right)[
        #text(style: "italic")[#row.at("description", default: "") :]
      ],
      table.cell(inset: (top: 3mm), align: right)[#format-decimal(val)],
    )

  } else if rt == "SAFETY_PCT" or rt == "OVERHEAD" or rt == "PROFIT" {
    // Spell out the amount each percentage is taken on, so the compounding of
    // safety costs, overhead and profit can be followed line by line.
    let val      = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    let pct_raw  = row.at("pct", default: "")
    let base_raw = row.at("base", default: "")
    let pct_str  = if pct_raw == "" or pct_raw == "0.0" { "" } else {
      "  " + pct_raw + "%" + (
        if base_raw == "" { "" } else { " di " + format-decimal(float(base_raw)) }
      )
    }
    (
      table.cell(colspan: 4, align: right)[
        #text(style: "italic")[#row.at("description", default: "") #pct_str :]
      ],
      table.cell(align: right)[#format-decimal(val)],
    )

  } else if rt == "ROUNDING" {
    let val = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(colspan: 4, align: right)[
        #text(style: "italic")[#row.at("description", default: "") :]
      ],
      table.cell(align: right)[#format-decimal(val)],
    )

  } else if rt == "SECTION_TOTAL" {
    // Intermediate total: ruled but not filled, so the final price stays the one
    // highlighted block on the sheet.
    let val = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(
        colspan: 4,
        stroke: (top: 0.4pt + gray),
        align: right,
      )[#strong[#upper(row.at("description", default: "TOTALE")) :]],
      table.cell(
        stroke: (top: 0.4pt + gray),
        align: right,
      )[#strong[#format-decimal(val)]],
    )

  } else if rt == "TOTAL" {
    // Banded like the category headers, but one and a half times as tall and with
    // the label on the left, so the final price reads as the conclusion of the
    // sheet. It carries the unit of measure of the item being priced, under the
    // U.M. column, so the rate reads as an amount per unit.
    let val  = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    let unit = row.at("unit", default: "")
    let band = (
      fill: gray.transparentize(85%),
      stroke: (top: 0.75pt, bottom: 0.4pt + gray),
      inset: (x: 1.5mm, y: 2.25mm),
    )
    (
      table.cell(
        ..band,
        colspan: 2,
        inset: (left: 2mm, y: 2.25mm),
        align: left + horizon,
      )[#strong[#upper(row.at("description", default: "PREZZO FINALE"))]],
      table.cell(..band, align: center + horizon)[#strong[#unit-or-dash(unit)]],
      table.cell(..band, colspan: 2, align: right + horizon)[#strong[#format-decimal(val)]],
    )

  } else if rt == "STALE_TOTAL" {
    // The summary CV's cached AppliedValue disagrees with the sum of the
    // components — the analysis was edited after it was applied. The price shown
    // is the component sum (what the BoQ uses); this red note warns that the
    // stored total is out of date.
    let stored = { let v = row.at("unit_price", default: ""); if v == "" { 0.0 } else { float(v) } }
    let computed = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(colspan: 5, inset: (top: 2mm, x: 1.5mm), align: left)[
        #text(fill: red, size: 7pt)[⚠ Il totale memorizzato sulla voce (#format-decimal(stored)) non
        corrisponde alla somma dei componenti (#format-decimal(computed)): l'analisi è stata
        modificata dopo l'applicazione. Il prezzo riportato è la somma dei componenti.]
      ],
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
      table.cell(
        colspan: 2,
      )[#text(size: 7pt)[#item_description]]
  )

  v(3mm)

  // — Rate analysis table —
  let data = csv(csv_path, row-type: dictionary)

  table(
    columns: (1fr, 20mm, 12mm, 22mm, 22mm),
    align: (left, right, center, right, right),
    stroke: none,
    inset: (x: 1.5mm, y: 1.5mm),
    table.header(
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
    // No running header: code and name already head the sheet in the item table
    // below, so repeating them above it only pushes the content down. The top
    // margin matches the multi-item export, which has never had one either.
    margin: (left: 15mm, right: 10mm, top: 20mm, bottom: 20mm),
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
