// Computo Metrico Estimativo (Priced / Unpriced Bill of Quantities)
// Cost items in hierarchy, with quantity breakdown, rate and total, plus a
// final summary page of section subtotals.
//
// Ported from ifc5d's typst_template_ifc_cost_schedule.typ onto common.typ.
//
// author: carlo pavan
// year: 2026

#import "common.typ": *

#let total-cell-style = (stroke: (top: 0.25pt + gray))

#let root-cost-cell-style = (
  stroke: (bottom: (thickness: 0.4pt, dash: "dotted")),
  fill: gray.transparentize(90%),
  align: bottom,
)

// — Page frame (drawn in the page background) —
#let bill_frame(currency: "") = table(
  columns: (18mm, 54mm, 12mm, 12mm, 12mm, 12mm, 20mm, 20mm, 25mm),
  rows: (6mm, 248mm),
  align: (center, left, center, center, center, center, center, center, center),
  stroke: (x, y) => (
    left: if x == 0 { 1pt } else { 0.25pt },
    right: 1pt, top: 1pt, bottom: 1pt,
  ),
  [Code], [Description], [n°], [l], [w], [h/w], [Quantity],
  [Rate (#currency)], [Total (#currency)],
)

#let summary_frame(currency: "") = table(
  columns: (18mm, 107mm, 30mm, 30mm),
  rows: (6mm, 248mm),
  align: (center, left, center, center),
  stroke: (x, y) => (
    left: if x == 0 { 1pt } else { 0.25pt },
    right: 1pt, top: 1pt, bottom: 1pt,
  ),
  text(size: 8pt)[Hierarchy], text(size: 8pt)[Description],
  text(size: 8pt)[Sub Total (#currency)], text(size: 8pt)[Total (#currency)],
)

#let arrange_bill_of_quantity_row(row, options) = {
  if row.at("ItemIsASum") == "True" {
    // SECTION (parent cost item)
    if options.at("nested_structure_depth") == 0 or int(row.at("Index")) <= options.at("nested_structure_depth") {
      let total_price = format-decimal(float(row.at("TotalPrice", default: "0.0")), places: 2)
      (
        [], [], [], [], [], [], [], [], [],
      )
      (
        table.cell(..root-cost-cell-style)[#id-cell(row, options.at("should_print_hierarchy"))],
        table.cell(..root-cost-cell-style)[#strong(upper(row.at("Name"))) #source-rate-line(row) #linebreak() #row.at("Description", default: "")],
        table.cell(..root-cost-cell-style)[],
        table.cell(..root-cost-cell-style)[],
        table.cell(..root-cost-cell-style)[],
        table.cell(..root-cost-cell-style)[],
        table.cell(..root-cost-cell-style)[],
        table.cell(..root-cost-cell-style)[],
        if options.at("should_print_rates") == true {
          table.cell(..root-cost-cell-style)[#strong(total_price)]
        } else {
          table.cell(..root-cost-cell-style)[]
        },
      )
    } else {
      ()
    }
  } else {
    // COST ITEM
    let name = if row.at("Name") == "" { strong(upper("Unnamed Cost Item")) } else { strong(upper(row.at("Name"))) }
    let description = if options.at("should_print_description") == true and row.at("Description") != "" {
      [#par(justify: true, text(8pt, row.at("Description", default: "")))]
    } else { "" }
    let unit = table.cell(align: right)[Sum #unit_map.at(row.at("Unit"), default: "")]
    let quant = if row.at("Quantity") == "" { 0.0 } else { format-decimal(float(row.at("Quantity"))) }
    let rate = if row.at("RateSubtotal") == "" { 0.0 } else { format-decimal(float(row.at("RateSubtotal"))) }
    let total = if row.at("Quantity") == "" or row.at("RateSubtotal") == "" {
      format-decimal(0.0, places: 2)
    } else {
      format-decimal(float(row.at("Quantity")) * float(row.at("RateSubtotal")), places: 2)
    }
    (
      id-cell(row, options.at("should_print_hierarchy")),
      name + source-rate-line(row) + description,
      [], [], [], [], [], [], [],
    )
    if row.at("Quantities") != "" and options.at("should_print_each_quantity") {
      let quantites = json.decode(row.at("Quantities"))
      for quantity in quantites {
        (
          [],
          if quantity.at(0) == "Unnamed" { [quantity] } else { quantity.at(0) },
          [], [], [], [],
          format-decimal(quantity.at(1)),
          [], [],
        )
      }
    }
    if options.at("should_print_rates") == true {
      (
        [], unit, [], [], [], [],
        table.cell(..total-cell-style, align: right + bottom)[#quant],
        table.cell(..total-cell-style, align: right + bottom)[#rate],
        table.cell(..total-cell-style, align: right + bottom)[#total],
      )
    } else {
      (
        [], unit, [], [], [], [],
        table.cell(..total-cell-style, align: right + bottom)[#quant],
        [.................],
        [.......................],
      )
    }
  }
}

#let arrange_summary_row(row, options) = {
  if row.at("ItemIsASum") == "True" {
    if row.at("Index") == "1" {
      // ROOT COST
      (
        strong[#id-cell(row, options.at("should_print_hierarchy"))],
        strong(upper(row.at("Name"))),
        [],
        if options.at("should_print_rates") {
          strong[#format-decimal(float(row.at("TotalPrice")), places: 2)]
        } else { [] },
      )
    } else {
      // SUB-SECTION
      (
        id-cell(row, options.at("should_print_hierarchy")),
        table.cell(inset: (left: int(row.at("Index")) * 2.5mm))[#upper(row.at("Name"))],
        if options.at("should_print_rates") { format-decimal(float(row.at("TotalPrice")), places: 2) } else { [] },
        [],
      )
    }
  } else {
    ()
  }
}

#let create-schedule(path, options) = {
  let data = csv(path, row-type: dictionary)
  let new_rows = data.map(item => arrange_bill_of_quantity_row(item, options))
  table(
    columns: (18mm, 1fr, 12mm, 12mm, 12mm, 12mm, 20mm, 20mm, 25mm),
    align: (center, left, center, center, center, center, right, right, right),
    stroke: none,
    ..new_rows.flatten()
  )
}

#let create-summary(path, options, currency: "") = {
  let data = csv(path, row-type: dictionary)
  let new_rows = data.map(item => arrange_summary_row(item, options))
  let general_total = data.filter(row => row.at("ItemIsASum") == "False")
    .map(row => {
      let qty = if row.at("Quantity", default: "") == "" { 0.0 } else { float(row.at("Quantity")) }
      let rate = if row.at("RateSubtotal", default: "") == "" { 0.0 } else { float(row.at("RateSubtotal")) }
      qty * rate
    })
    .sum(default: 0.00)

  set text(size: 10pt)
  pad(left: 2cm)[SUMMARY:]

  set text(size: 8pt)
  table(
    columns: (18mm, 107mm, 30mm, 30mm),
    align: (center, left, right, right),
    stroke: (x, y) => (
      left: none, right: none,
      top: (thickness: 0.4pt, dash: "dotted"),
      bottom: (thickness: 0.4pt, dash: "dotted"),
    ),
    ..new_rows.flatten()
  )

  set text(size: 10pt)
  grid(
    columns: (18mm, 107mm, 30mm, 30mm),
    align: (center, right, center, right),
    inset: 1mm,
    fill: gray.transparentize(70%),
    [], strong[GENERAL TOTAL:], [],
    if options.at("should_print_rates") { [#strong(format-decimal(general_total, places: 2))] } else { [] },
  )
}

// Entry point: `#show: project.with(...)`.
#let project(
  schedule_path: "",
  title: "",
  schedule_name: "",
  schedule_description: "",
  schedule_type: "PRICEDBILLOFQUANTITIES",
  project_currency: "",
  nested_structure_depth: 0,
  should_print_cover: false,
  should_print_hierarchy: false,
  should_print_description: false,
  should_print_each_quantity: true,
  should_print_rates: true,
  should_print_summary: true,
  body,
) = {
  set text(font: template_fonts, size: 8pt, lang: "en")

  if should_print_cover {
    schedule_cover(title, schedule_name, schedule_description, schedule_type)
    pagebreak()
    counter(page).update(n => n - 1)
  }

  set page(
    paper: "a4",
    margin: (left: 15mm, right: 10mm, top: 35mm, bottom: 20mm),
    numbering: "1/1",
    number-align: end,
    header: std-header(title, schedule_name),
    footer: std-footer(),
    background: place(top + left, dx: 15mm, dy: 25mm, bill_frame(currency: project_currency)),
  )

  let options = (
    "nested_structure_depth": nested_structure_depth,
    "should_print_hierarchy": should_print_hierarchy,
    "should_print_description": should_print_description,
    "should_print_each_quantity": should_print_each_quantity,
    "should_print_rates": should_print_rates,
  )

  create-schedule(schedule_path, options)

  if should_print_summary {
    pagebreak()
    set page(background: place(top + left, dx: 15mm, dy: 25mm, summary_frame(currency: project_currency)))
    create-summary(schedule_path, options, currency: project_currency)
  }

  body
}
