// Elenco Prezzi Unitari (Schedule of Rates)
// Flat list of priced items (no hierarchy, no quantities): identification,
// description, unit and unit rate.
//
// Ported from ifc5d's typst_template_ifc_cost_schedule.typ onto common.typ.
//
// author: carlo pavan
// year: 2026

#import "common.typ": *

// — Page frame (drawn in the page background) —
#let rates_frame(currency: "") = table(
  columns: (30mm, 130mm, 25mm),
  rows: (6mm, 248mm),
  align: (center, left, center),
  stroke: (x, y) => (
    left: if x == 0 { 1pt } else { 0.25pt },
    right: 1pt, top: 1pt, bottom: 1pt,
  ),
  [Code], [Description], [Rate (#currency)],
)

#let arrange_schedule_of_rates_row(row, options) = {
  if row.at("ItemIsASum") == "True" { return () }  // skip sections
  let name = strong(upper(row.at("Name")))
  let description = [#par(justify: true, text(8pt, row.at("Description", default: "")))]
  let unit = table.cell(align: right + bottom)[#unit_map.at(row.at("Unit"), default: "")]
  let rate = if row.at("RateSubtotal") == "" { 0.0 } else { format-decimal(float(row.at("RateSubtotal"))) }
  (
    id-cell(row, options.at("should_print_hierarchy")),
    name + source-rate-line(row) + linebreak() + description,
    [],
  )
  (
    [],
    unit,
    table.cell(align: right + bottom)[#rate],
  )
  (
    [], [], [],
  )
}

#let create-schedule(path, options) = {
  let data = csv(path, row-type: dictionary)
  let new_rows = data.map(item => arrange_schedule_of_rates_row(item, options))
  table(
    columns: (30mm, 130mm, 25mm),
    align: (center, left, right),
    stroke: none,
    ..new_rows.flatten()
  )
}

// Entry point: `#show: project.with(...)`.
#let project(
  schedule_path: "",
  title: "",
  schedule_name: "",
  schedule_description: "",
  schedule_type: "SCHEDULEOFRATES",
  project_currency: "",
  should_print_cover: false,
  should_print_hierarchy: false,
  should_print_description: false,
  should_print_rates: true,
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
    background: place(top + left, dx: 15mm, dy: 25mm, rates_frame(currency: project_currency)),
  )

  let options = (
    "should_print_hierarchy": should_print_hierarchy,
    "should_print_description": should_print_description,
    "should_print_rates": should_print_rates,
  )

  create-schedule(schedule_path, options)

  body
}
