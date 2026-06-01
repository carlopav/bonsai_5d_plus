// Rate Analysis Sheet Template (Scheda Analisi Prezzi)
// author: carlo pavan
// year: 2026

#let template_fonts = ("Liberation Sans", "Roboto", "Arial", "Calibri")

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
  let parts = str-num.split(".")
  let integer-part = parts.at(0)
  let decimal-part = parts.at(1, default: "")
  let is-negative = integer-part.starts-with("-")
  if is-negative { integer-part = integer-part.slice(1) }
  let formatted = ""
  let chars = integer-part.clusters().rev()
  for (i, char) in chars.enumerate() {
    if i > 0 and calc.rem(i, 3) == 0 { formatted = "'" + formatted }
    formatted = char + formatted
  }
  decimal-part = decimal-part + "0" * (places - decimal-part.len())
  (if is-negative { "-" } else { "" }) + formatted + "." + decimal-part
}

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
    margin: (left: 15mm, right: 10mm, top: 35mm, bottom: 20mm),
    numbering: "1/1",
    number-align: end,
    header: [
      #set text(font: template_fonts, size: 9pt, lang: "it")
      #table(
        columns: (1fr, 2fr),
        rows: 10mm,
        stroke: none,
        inset: 0mm,
        align: (top + left, top + right),
        [#item_identification], [#item_name]
      )
    ],
    footer: context [
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [#datetime.today().display("[day]/[month]/[year]")],
        [#counter(page).display("1/1", both: true)]
      )
    ],
  )

  set text(font: template_fonts, size: 8pt, lang: "it")

  // — Item header —
  table(
    columns: (auto, 1fr),
    rows: 8mm,
    stroke: none,
    inset: 0mm,
    align: (left + bottom, left + bottom),
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
