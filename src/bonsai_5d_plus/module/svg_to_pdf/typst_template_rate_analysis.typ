// Rate Analysis Sheet Template (Scheda Analisi Prezzi)
// author: carlo pavan
// year: 2026

#let template_fonts = ("Liberation Sans", "Roboto", "Arial", "Calibri")

// Palette
#let _fill_header  = gray.transparentize(75%)   // column headers
#let _fill_section = gray.transparentize(90%)   // category section rows
#let _fill_foot    = gray.transparentize(95%)   // subtotals / footer rows

// Registro-style strokes: heavier frame, thin interior verticals
#let _stroke_heavy  = 0.75pt
#let _stroke_border = 0.5pt
#let _stroke_table  = (x, y) => (
  left:   if x == 0 { 0.75pt } else { 0.25pt },
  right:  0.75pt,
  top:    0.5pt,
  bottom: 0.5pt,
)

#let category_abbr = (
  "Sub-Contract": "OPC",
  "Labor":        "LAV",
  "Equipment":    "NOL",
  "Material":     "MAT",
  "Safety":       "SIC",
)

#let format-decimal(num, places: 2) = {
  let rounded = calc.round(float(num), digits: places)
  let str-num = str(rounded)
  let parts   = str-num.split(".")
  let int-part = parts.at(0)
  let dec-part = parts.at(1, default: "")
  let neg = int-part.starts-with("-")
  if neg { int-part = int-part.slice(1) }
  let fmt = ""
  let chars = int-part.clusters().rev()
  for (i, c) in chars.enumerate() {
    if i > 0 and calc.rem(i, 3) == 0 { fmt = "'" + fmt }
    fmt = c + fmt
  }
  dec-part = dec-part + "0" * (places - dec-part.len())
  (if neg { "-" } else { "" }) + fmt + "." + dec-part
}


// ---------------------------------------------------------------------------
// Shared page chrome
// ---------------------------------------------------------------------------

#let ra-page-header(identification, name) = [
  #set text(font: template_fonts, size: 7pt, lang: "it")
  #grid(
    columns: (auto, 1fr),
    column-gutter: 5mm,
    align: bottom,
    text(weight: "bold")[#identification],
    text()[#upper(name)],
  )
  #v(-0.5mm)
  #line(length: 100%, stroke: _stroke_heavy)
]

#let ra-page-footer() = context [
  #set text(font: template_fonts, size: 7pt, lang: "it")
  #line(length: 100%, stroke: _stroke_border)
  #v(0.5mm)
  #grid(
    columns: (1fr, 1fr),
    align: (left, right),
    datetime.today().display("[day]/[month]/[year]"),
    counter(page).display("1/1", both: true),
  )
]


// ---------------------------------------------------------------------------
// Row renderer for the analysis table
// ---------------------------------------------------------------------------

#let arrange_row(row) = {
  let rt = row.at("row_type", default: "")

  if rt == "CATEGORY_HEADER" {
    let label = row.at("description", default: "")
    (
      table.cell(
        colspan: 6,
        fill: _fill_section,
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
      table.cell(colspan: 5, fill: _fill_foot, align: right)[
        #text(style: "italic")[Subtotale #label :]
      ],
      table.cell(fill: _fill_foot, align: right)[#strong[#format-decimal(val)]],
    )

  } else if rt == "SUBTOTAL" {
    let val = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(colspan: 5, fill: _fill_foot, align: right)[
        #text(style: "italic")[#row.at("description", default: "") :]
      ],
      table.cell(fill: _fill_foot, align: right)[#format-decimal(val)],
    )

  } else if rt == "OVERHEAD" or rt == "PROFIT" {
    let val     = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    let pct_raw = row.at("pct", default: "")
    let pct_str = if pct_raw == "" or pct_raw == "0.0" { "" } else { "  " + pct_raw + "%" }
    (
      table.cell(colspan: 5, fill: _fill_foot, align: right)[
        #text(style: "italic")[#row.at("description", default: "") #pct_str :]
      ],
      table.cell(fill: _fill_foot, align: right)[#format-decimal(val)],
    )

  } else if rt == "ROUNDING" {
    let val = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(colspan: 5, fill: _fill_foot, align: right)[
        #text(style: "italic")[#row.at("description", default: "") :]
      ],
      table.cell(fill: _fill_foot, align: right)[#format-decimal(val)],
    )

  } else if rt == "TOTAL" {
    let val = { let v = row.at("line_total", default: ""); if v == "" { 0.0 } else { float(v) } }
    (
      table.cell(
        colspan: 5,
        fill: _fill_header,
        align: right,
      )[#strong[#upper(row.at("description", default: "PREZZO FINALE")) :]],
      table.cell(fill: _fill_header, align: right)[#strong[#format-decimal(val)]],
    )

  } else {
    ()
  }
}


// ---------------------------------------------------------------------------
// Content block: one analysis (item header + description + row table)
// ---------------------------------------------------------------------------

#let render_analysis(
  csv_path: "",
  item_identification: "",
  item_name: "",
  item_description: "",
  project_currency: "EUR",
) = {
  // — Item header —
  table(
    columns: (32mm, 1fr),
    stroke: _stroke_table,
    inset: (x: 3mm, y: 2mm),
    align: (left, left),
    table.header(
      table.cell(fill: _fill_header, inset: (x: 3mm, y: 1mm))[
        #text(size: 6.5pt, weight: "bold")[CODICE]
      ],
      table.cell(fill: _fill_header, inset: (x: 3mm, y: 1mm))[
        #text(size: 6.5pt, weight: "bold")[VOCE]
      ],
    ),
    [#text(size: 11pt)[#strong[#item_identification]]],
    [#text(size: 11pt)[#strong[#upper(item_name)]]],
  )

  // — Description box —
  if item_description != "" {
    v(0.5mm)
    block(
      width: 100%,
      inset: (x: 2mm, y: 1.5mm),
      stroke: _stroke_border,
    )[#text(size: 7pt)[#item_description]]
  }

  v(2mm)

  // — Rate analysis table —
  let data = csv(csv_path, row-type: dictionary)

  table(
    columns: (12mm, 1fr, 20mm, 12mm, 22mm, 22mm),
    align: (center, left, right, center, right, right),
    stroke: _stroke_table,
    inset: (x: 1.5mm, y: 1.5mm),
    table.header(
      table.cell(fill: _fill_header)[#text(size: 7pt, weight: "bold")[Cat.]],
      table.cell(fill: _fill_header)[#text(size: 7pt, weight: "bold")[Descrizione]],
      table.cell(fill: _fill_header)[#text(size: 7pt, weight: "bold")[Qtà]],
      table.cell(fill: _fill_header)[#text(size: 7pt, weight: "bold")[U.M.]],
      table.cell(fill: _fill_header)[#text(size: 7pt, weight: "bold")[P.U. (#project_currency)]],
      table.cell(fill: _fill_header)[#text(size: 7pt, weight: "bold")[Importo (#project_currency)]],
    ),
    ..data.map(row => arrange_row(row)).flatten(),
  )
}


// ---------------------------------------------------------------------------
// Document wrapper for single-item export
// ---------------------------------------------------------------------------

#let project(
  csv_path: "",
  item_identification: "",
  item_name: "",
  item_description: "",
  project_currency: "EUR",
  body,
) = {

  set page(
    paper: "a4",
    margin: (left: 15mm, right: 10mm, top: 22mm, bottom: 20mm),
    numbering: "1/1",
    number-align: end,
    header: ra-page-header(item_identification, item_name),
    footer: ra-page-footer(),
  )

  set text(font: template_fonts, size: 8pt, lang: "it")

  render_analysis(
    csv_path: csv_path,
    item_identification: item_identification,
    item_name: item_name,
    item_description: item_description,
    project_currency: project_currency,
  )

  body
}
