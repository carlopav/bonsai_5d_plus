// Labor Cost Breakdown (Quadro di Incidenza Manodopera)
// Same visual structure as the Bill of Quantities, but each cost item exposes
// two cost columns — total cost and labor cost — plus the labor incidence
// percentage (labor / total) per row, with a final summary page of per-chapter
// incidences and the grand total (same layout as the Bill of Quantities).
//
// Consumes the standard ifc5d cost-schedule CSV (same extractor as the Bill
// of Quantities) — no custom export. The labor figure is the per-unit
// "Labor Cost" category column; the line cost is Quantity * RateSubtotal and
// the line labor is Quantity * "Labor Cost". Section subtotals and the grand
// total are rolled up here in Typst by hierarchy.
//
// Relevant CSV columns:
//   Hierarchy, ItemIsASum, Index, Identification, Name, Description,
//   Quantity, Unit, RateSubtotal, "Labor Cost"
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

// Labor incidence as a percentage string. Empty total → 0.0%.
#let pct-of(total, labor) = {
  if total == 0.0 { "0.0%" } else { format-decimal(labor / total * 100.0, places: 1) + "%" }
}

#let _num(row, key) = { let v = row.at(key, default: ""); if v == "" { 0.0 } else { float(v) } }

// Per-leaf line cost and labor cost, derived from the ifc5d CSV columns.
#let leaf-total(row) = _num(row, "Quantity") * _num(row, "RateSubtotal")
#let leaf-labor(row) = _num(row, "Quantity") * _num(row, "Labor Cost")

// — Page frame (drawn in the page background). Widths sum to 185mm. —
#let labor_frame(currency: "") = table(
  columns: (18mm, 71mm, 22mm, 28mm, 28mm, 18mm),
  rows: (6mm, 248mm),
  align: (center, left, center, center, center, center),
  stroke: (x, y) => (
    left: if x == 0 { 1pt } else { 0.25pt },
    right: 1pt, top: 1pt, bottom: 1pt,
  ),
  [Code], [Description], [Quantity],
  [Total cost (#currency)], [Labor cost (#currency)], [Labor %],
)

// — Summary page frame. Widths sum to 185mm. —
#let labor_summary_frame(currency: "") = table(
  columns: (18mm, 89mm, 30mm, 30mm, 18mm),
  rows: (6mm, 248mm),
  align: (center, left, center, center, center),
  stroke: (x, y) => (
    left: if x == 0 { 1pt } else { 0.25pt },
    right: 1pt, top: 1pt, bottom: 1pt,
  ),
  text(size: 8pt)[Code], text(size: 8pt)[Description],
  text(size: 8pt)[Total cost (#currency)], text(size: 8pt)[Labor cost (#currency)],
  text(size: 8pt)[Labor %],
)

// `total` / `labor` are the (already computed/aggregated) line amounts.
#let arrange_labor_row(row, options, total, labor) = {
  if row.at("ItemIsASum") == "True" {
    // SECTION (parent cost item) — aggregated total / labor / incidence
    if options.at("nested_structure_depth") == 0 or int(row.at("Index")) <= options.at("nested_structure_depth") {
      (
        [], [], [], [], [], [],
      )
      (
        table.cell(..root-cost-cell-style)[#id-cell(row, options.at("should_print_hierarchy"))],
        table.cell(..root-cost-cell-style)[#strong(upper(row.at("Name"))) #source-rate-line(row) #linebreak() #row.at("Description", default: "")],
        table.cell(..root-cost-cell-style)[],
        table.cell(..root-cost-cell-style)[#strong(format-decimal(total))],
        table.cell(..root-cost-cell-style)[#strong(format-decimal(labor))],
        table.cell(..root-cost-cell-style)[#strong(pct-of(total, labor))],
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
    let quant = if row.at("Quantity", default: "") == "" { [] } else {
      [#format-decimal(float(row.at("Quantity"))) #fmt-unit(row.at("Unit", default: ""))]
    }
    (
      id-cell(row, options.at("should_print_hierarchy")),
      name + source-rate-line(row) + description,
      table.cell(..total-cell-style, align: right + bottom)[#quant],
      table.cell(..total-cell-style, align: right + bottom)[#format-decimal(total)],
      table.cell(..total-cell-style, align: right + bottom)[#format-decimal(labor)],
      table.cell(..total-cell-style, align: right + bottom)[#pct-of(total, labor)],
    )
  }
}

#let create-schedule(path, options) = {
  let data = csv(path, row-type: dictionary)
  let leaves = data.filter(row => row.at("ItemIsASum") == "False")

  // A section's amounts are the sum of its leaf descendants (hierarchy prefix).
  let aggregate(h) = {
    let ls = leaves.filter(row => row.at("Hierarchy").starts-with(h + "."))
    (ls.map(leaf-total).sum(default: 0.0), ls.map(leaf-labor).sum(default: 0.0))
  }

  let new_rows = ()
  for row in data {
    if row.at("ItemIsASum") == "True" {
      let (t, l) = aggregate(row.at("Hierarchy"))
      new_rows += arrange_labor_row(row, options, t, l)
    } else {
      new_rows += arrange_labor_row(row, options, leaf-total(row), leaf-labor(row))
    }
  }

  table(
    columns: (18mm, 1fr, 22mm, 28mm, 28mm, 18mm),
    align: (center, left, right, right, right, right),
    stroke: none,
    ..new_rows.flatten(),
  )
}

// One summary row per chapter (section), with its aggregated incidence.
#let arrange_labor_summary_row(row, leaves, show_hierarchy) = {
  if row.at("ItemIsASum") == "True" {
    let h = row.at("Hierarchy")
    let ls = leaves.filter(r => r.at("Hierarchy").starts-with(h + "."))
    let total = ls.map(leaf-total).sum(default: 0.0)
    let labor = ls.map(leaf-labor).sum(default: 0.0)
    if row.at("Index") == "1" {
      // ROOT CHAPTER
      (
        strong[#id-cell(row, show_hierarchy)],
        strong(upper(row.at("Name"))),
        strong[#format-decimal(total)],
        strong[#format-decimal(labor)],
        strong[#pct-of(total, labor)],
      )
    } else {
      // SUB-SECTION
      (
        id-cell(row, show_hierarchy),
        table.cell(inset: (left: int(row.at("Index")) * 2.5mm))[#upper(row.at("Name"))],
        format-decimal(total),
        format-decimal(labor),
        pct-of(total, labor),
      )
    }
  } else {
    ()
  }
}

#let create-summary(path, show_hierarchy) = {
  let data = csv(path, row-type: dictionary)
  let leaves = data.filter(row => row.at("ItemIsASum") == "False")
  let new_rows = data.map(item => arrange_labor_summary_row(item, leaves, show_hierarchy))
  let tot_total = leaves.map(leaf-total).sum(default: 0.0)
  let tot_labor = leaves.map(leaf-labor).sum(default: 0.0)

  set text(size: 10pt)
  pad(left: 2cm)[SUMMARY:]

  set text(size: 8pt)
  table(
    columns: (18mm, 1fr, 30mm, 30mm, 18mm),
    align: (center, left, right, right, right),
    stroke: (x, y) => (
      left: none, right: none,
      top: (thickness: 0.4pt, dash: "dotted"),
      bottom: (thickness: 0.4pt, dash: "dotted"),
    ),
    ..new_rows.flatten()
  )

  set text(size: 10pt)
  grid(
    columns: (18mm, 1fr, 30mm, 30mm, 18mm),
    align: (center, right, right, right, right),
    inset: 1mm,
    fill: gray.transparentize(70%),
    [], strong[GENERAL TOTAL:],
    strong[#format-decimal(tot_total)],
    strong[#format-decimal(tot_labor)],
    strong[#pct-of(tot_total, tot_labor)],
  )
}

// Entry point: `#show: project.with(...)`.
#let project(
  schedule_path: "",
  title: "",
  schedule_name: "",
  schedule_description: "",
  schedule_type: "LABORCOSTBREAKDOWN",
  project_currency: "",
  nested_structure_depth: 0,
  should_print_cover: false,
  should_print_hierarchy: false,
  should_print_description: false,
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
    background: place(top + left, dx: 15mm, dy: 25mm, labor_frame(currency: project_currency)),
  )

  let options = (
    "nested_structure_depth": nested_structure_depth,
    "should_print_hierarchy": should_print_hierarchy,
    "should_print_description": should_print_description,
  )

  create-schedule(schedule_path, options)

  if should_print_summary {
    pagebreak()
    set page(background: place(top + left, dx: 15mm, dy: 25mm, labor_summary_frame(currency: project_currency)))
    create-summary(schedule_path, should_print_hierarchy)
  }

  body
}
