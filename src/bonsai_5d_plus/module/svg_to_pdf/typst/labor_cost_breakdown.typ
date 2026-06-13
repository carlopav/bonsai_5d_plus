// Quadro di Incidenza Manodopera (Labor Cost Breakdown)
// Same visual structure as the Bill of Quantities, but each cost item exposes
// two cost columns — total cost and labor cost — plus the labor incidence
// percentage (labor / total) per row and for the grand total.
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
  [Codice], [Descrizione], [Quantità],
  [Costo totale (#currency)], [Costo M.O. (#currency)], [Inc. %],
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
        table.cell(..root-cost-cell-style)[#row.at("Hierarchy")],
        table.cell(..root-cost-cell-style)[#strong(upper(row.at("Name"))) #linebreak() #row.at("Description", default: "")],
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
    let name = if row.at("Name") == "" { strong(upper("Voce senza nome")) } else { strong(upper(row.at("Name"))) }
    let identification = if options.at("should_print_cost_ids") == true and row.at("Identification") != "" {
      linebreak() + row.at("Identification")
    } else { "" }
    let description = if options.at("should_print_description") == true and row.at("Description") != "" {
      [#par(justify: true, text(8pt, row.at("Description", default: "")))]
    } else { "" }
    let quant = if row.at("Quantity", default: "") == "" { [] } else {
      [#format-decimal(float(row.at("Quantity"))) #fmt-unit(row.at("Unit", default: ""))]
    }
    (
      row.at("Hierarchy"),
      name + identification + description,
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

  // Grand total from leaf items only.
  let tot_total = leaves.map(leaf-total).sum(default: 0.0)
  let tot_labor = leaves.map(leaf-labor).sum(default: 0.0)

  let total_row = (
    table.cell(colspan: 2, fill: gray.transparentize(70%), stroke: (top: 0.75pt), align: right)[
      #strong[INCIDENZA MANODOPERA COMPLESSIVA :]
    ],
    table.cell(fill: gray.transparentize(70%), stroke: (top: 0.75pt))[],
    table.cell(fill: gray.transparentize(70%), stroke: (top: 0.75pt), align: right)[#strong(format-decimal(tot_total))],
    table.cell(fill: gray.transparentize(70%), stroke: (top: 0.75pt), align: right)[#strong(format-decimal(tot_labor))],
    table.cell(fill: gray.transparentize(70%), stroke: (top: 0.75pt), align: right)[#strong(pct-of(tot_total, tot_labor))],
  )

  table(
    columns: (18mm, 1fr, 22mm, 28mm, 28mm, 18mm),
    align: (center, left, right, right, right, right),
    stroke: none,
    ..new_rows.flatten(),
    ..total_row,
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
  should_print_cost_ids: true,
  should_print_description: false,
  body,
) = {
  set text(font: template_fonts, size: 8pt, lang: "it")

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
    "should_print_cost_ids": should_print_cost_ids,
    "should_print_description": should_print_description,
  )

  create-schedule(schedule_path, options)

  body
}
