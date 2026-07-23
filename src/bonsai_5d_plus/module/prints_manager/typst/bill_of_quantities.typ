// Computo Metrico Estimativo (Priced / Unpriced Bill of Quantities)
// Cost items in hierarchy, with quantity breakdown, rate and total, plus a
// final summary page of section subtotals.
//
// The quantity-decomposition columns (n / l / w / h) are optional: when on,
// each measurement row fills them by splitting its Formula ("NR x L x W x H");
// when off (default) those columns disappear, the Description column absorbs
// their width, and any formula is shown in parentheses after the row name.
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
  align: top,
)

// Evaluate a single arithmetic factor (e.g. "256.667-23") to a number, or none
// if it is not a safe numeric expression. Only digits and + - * / . ( ) space
// are allowed, so eval() cannot run arbitrary code.
#let eval-factor(s) = {
  let t = s.trim()
  if t == "" { return none }
  if t.match(regex("^[\\d\\.\\+\\-\\*/\\(\\)\\s]+$")) == none { return none }
  let v = eval(t, mode: "code")
  if type(v) == int or type(v) == float { float(v) } else { none }
}

// A decomposition factor rendered as a small single-value cell: an unused axis
// is shown as "-" — written as 1 by the XPWE importer and as 0 by the
// measurement book, both meaning "no subdivision here". Any other value is
// shown with two decimals. One point smaller than the table text to fit.
#let factor-cell(v) = text(7pt)[#(
  if v == 1.0 or v == 0.0 { "-" } else { format-decimal(v, places: 2) }
)]

// Render already-formatted content in red when its underlying numeric value is
// negative; otherwise leave it untouched. Used to flag negative quantities and
// totals throughout the bill.
#let neg-red(v, body) = if v < 0 { text(red)[#body] } else { [#body] }

// Left indent reflecting a row's depth in the cost hierarchy, applied to the
// Description column so the whole bill — sections, cost-item names and their
// descriptions/measurements — is visually oriented like the summary, not only
// the summary page. `Index` is 1 for the root; each nested level adds one unit
// (~three spaces). Tune `indent-unit` to taste.
#let indent-unit = 2.25mm
#let row-indent(row) = (int(row.at("Index", default: "1")) - 1) * indent-unit

// When the "move Identification" option is on (only for leaf cost items, and
// only together with hierarchy renumbering — which then owns the generated code
// in the first column), the item's Identification (typically the price-list
// code) is shown at the top of the Description column, above the Name on its own
// line, in black and between square brackets. Rendered at the same size as the
// first-column hierarchy code (7pt) so the two stay aligned on the row's first
// line. Returns the identification line + a linebreak, or empty content.
#let ident-prefix(row, move_ident) = {
  if move_ident {
    let ident = row.at("Identification", default: "")
    if ident != "" { text(7pt, "[" + ident + "]") + linebreak() } else { [] }
  } else { [] }
}

// Decompose a "a × b × c × d" formula into its four numeric factors. Returns
// the four computed values, or () when the formula is not exactly four
// × -separated parts or any part is not a numeric expression (then the formula
// is shown verbatim and the columns stay empty — the n/l/w/h columns must
// always hold a single value, never a fragment of the formula).
// Labels for the four decomposition columns, used to annotate factors that are
// expressions rather than plain numbers.
#let factor-labels = ("n", "l", "w", "h/w")

// When decomposition columns are shown, each n/l/w/h column holds the computed
// total of its factor. For factors that are expressions (not plain numbers) we
// also report how that total was obtained next to the description, e.g.
// "(n=25*0.1) (h/w=15*2)". Plain numbers and trivial "1" factors get no note.
#let factor-notes(f) = {
  let parts = f.split("×").map(p => p.trim())
  if parts.len() != 4 { return "" }
  let notes = ()
  for (i, p) in parts.enumerate() {
    if p.match(regex("^[\\d\\.]+$")) == none {
      notes.push("(" + factor-labels.at(i) + "=" + p + ")")
    }
  }
  notes.join(" ")
}

#let formula-parts(f) = {
  if f == "" { return () }
  let parts = f.split("×").map(p => p.trim())
  if parts.len() != 4 { return () }
  let vals = parts.map(eval-factor)
  if vals.any(v => v == none) { () } else { vals }
}

// The portion of a formula worth showing next to the quantity, or "" when
// nothing meaningful remains. The measurement book always writes the four fixed
// factors "NR × L × B × H", padding the unused ones with 0, so a formula arrives
// here as e.g. "3 × 2.05 × 0 × 0". Only the factors carrying an actual
// measurement are shown: zeros are dropped, the rest are printed to two decimals
// and joined with "*" without spaces, giving "(3.00*2.05)", "(1.00)",
// "(4.00*5.50*0.50)". Printing the padding zeros made the parenthesis look like
// the decomposition columns even when those were switched off (issue #13).
// Dropping the padding is not a single rule, because the two writers pad the
// unused positions differently:
//   - the measurement book (_build_formula_qty) writes 0, and skips zero fields
//     when computing the partial, so a 0 is always padding;
//   - the XPWE import (core/parsers/xpwe.py) writes 1 for an empty column, so
//     there a 1 is padding — but a 1 typed into the NR field is a real count.
// From the string alone those two 1s are indistinguishable. What saves us is
// that a factor of 1 never changes the product: it is dropped whenever another
// factor survives, and kept only when it is all that is left, which is exactly
// the "one item, no dimensions" row.
//
// A factor that is an expression rather than a plain number is kept verbatim —
// rounding it to two decimals would throw away how the value was obtained — but
// is wrapped in parentheses, since "*" is the separator too and "25*0.1*3.00"
// would not show where one factor ends. A formula with any factor we cannot
// evaluate is shown in full, since we can't tell which parts matter.
#let formula-display(f) = {
  let t = f.trim()
  if t == "" { return "" }
  let parts = t.split("×").map(p => p.trim()).filter(p => p != "")
  // Unexpected format: any non-numeric factor → show the formula in full.
  if parts.any(p => eval-factor(p) == none) { return t }
  let measured = parts.filter(p => eval-factor(p) != 0.0)
  if measured.len() == 0 { return "" }
  let significant = measured.filter(p => eval-factor(p) != 1.0)
  if significant.len() == 0 { return format-decimal(1.0, places: 2) }
  significant
    .map(p => if p.match(regex("^[\\d\\.]+$")) != none {
      format-decimal(float(p), places: 2)
    } else if p.starts-with("(") and p.ends-with(")") {
      p
    } else {
      "(" + p + ")"
    })
    .join("*")
}

// — Page frame (drawn in the page background). Widths sum to 185mm. —
#let bill_frame(currency: "", show_decomp: false) = {
  let strk = (x, y) => (left: if x == 0 { 1pt } else { 0.25pt }, right: 1pt, top: 1pt, bottom: 1pt)
  if show_decomp {
    table(
      columns: (18mm, 54mm, 12mm, 12mm, 12mm, 12mm, 20mm, 20mm, 25mm),
      rows: (6mm, 248mm),
      align: (center, left, center, center, center, center, center, center, center),
      stroke: strk,
      [Code], [Description], [n°], [l], [w], [h/w], [Quantity],
      [Rate (#currency)], [Total (#currency)],
    )
  } else {
    table(
      columns: (18mm, 102mm, 20mm, 20mm, 25mm),
      rows: (6mm, 248mm),
      align: (center, left, center, center, center),
      stroke: strk,
      [Code], [Description], [Quantity], [Rate (#currency)], [Total (#currency)],
    )
  }
}

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

#let arrange_bill_of_quantity_row(row, options, totals) = {
  let show_decomp = options.at("should_print_qty_decomposition")
  // Empty decomposition cells, present only in decomposition mode.
  let mid = if show_decomp { ([], [], [], []) } else { () }
  // Move the Identification into the Description column (leaf items) and hide it
  // for summary costs: it is only meaningful for leaf cost items, and only when
  // the hierarchy renumbering owns the generated first-column code.
  let move_ident = options.at("should_move_identification") and options.at("should_print_hierarchy")

  if row.at("ItemIsASum") == "True" {
    // SECTION (parent cost item)
    if options.at("nested_structure_depth") == 0 or int(row.at("Index")) <= options.at("nested_structure_depth") {
      let total_price = format-decimal(totals.at(row.at("Id", default: ""), default: 0.0), places: 2)
      let rblank = table.cell(..root-cost-cell-style)[]
      let rmid = if show_decomp { (rblank, rblank, rblank, rblank) } else { () }
      let total_cell = if options.at("should_print_rates") == true {
        table.cell(..root-cost-cell-style)[#strong(total_price)]
      } else {
        table.cell(..root-cost-cell-style)[]
      }
      range(if show_decomp { 9 } else { 5 }).map(_ => [])
      (
        table.cell(..root-cost-cell-style)[#id-cell(row, options.at("should_print_hierarchy"), move_ident: move_ident)],
        table.cell(..root-cost-cell-style)[#pad(left: row-indent(row))[#strong(upper(row.at("Name"))) #source-rate-line(row) #linebreak() #row.at("Description", default: "")]],
      ) + rmid + (rblank, rblank, total_cell)
    } else {
      ()
    }
  } else {
    // COST ITEM
    let name = if row.at("Name") == "" { strong(upper("Unnamed Cost Item")) } else { strong(upper(row.at("Name"))) }
    let description = if options.at("should_print_description") == true and row.at("Description") != "" {
      [#par(justify: true, text(8pt, row.at("Description", default: "")))]
    } else { "" }
    let unit_str = fmt-unit(row.at("Unit", default: ""))
    let unit = table.cell(align: right)[#if unit_str != "" { unit_str } else { "-" }]
    // Rounded early and summed from the rounded parts — see the rounding
    // policy in common.typ. quant_v is the sum of the rounded measurement
    // rows, so the Quantity column adds up to the breakdown below it.
    let rounded = options.at("should_eval_rounded_values", default: true)
    let quant_v = row-quantity(row, rounded: rounded)
    let rate_v = row-rate(row, rounded: rounded)
    let total_v = row-total(row, rounded: rounded)
    let quant = format-decimal(quant_v)
    let rate = format-decimal(rate_v)
    let total = format-decimal(total_v, places: 2)

    (id-cell(row, options.at("should_print_hierarchy"), move_ident: move_ident), pad(left: row-indent(row))[#(ident-prefix(row, move_ident) + name + source-rate-line(row) + description)]) + mid + ([], [], [])

    if row.at("Quantities") != "" and options.at("should_print_each_quantity") {
      let quantites = json.decode(row.at("Quantities"))
      for q in quantites {
        let qname = if q.at(0) == "Unnamed" { "" } else { q.at(0) }
        let f = q.at(2, default: "")
        let parts = formula-parts(f)
        let qty_cell = neg-red(q.at(1), format-decimal(q.at(1)))
        if show_decomp and parts.len() == 4 {
          let notes = factor-notes(f)
          let label = if notes != "" { (qname + " " + notes).trim() } else { qname }
          ([], pad(left: row-indent(row))[#label], factor-cell(parts.at(0)), factor-cell(parts.at(1)), factor-cell(parts.at(2)), factor-cell(parts.at(3)), qty_cell, [], [])
        } else {
          // No decomposition: show the significant part of the formula after the
          // row name, dropping trivial "1" factors and redundant single numbers.
          let shown = formula-display(f)
          let label = if shown != "" { qname + " (" + shown + ")" } else { qname }
          ([], pad(left: row-indent(row))[#label]) + mid + (qty_cell, [], [])
        }
      }
    }

    if options.at("should_print_rates") == true {
      ([], unit) + mid + (
        table.cell(..total-cell-style, align: right + bottom)[#neg-red(quant_v, quant)],
        table.cell(..total-cell-style, align: right + bottom)[#neg-red(rate_v, rate)],
        table.cell(..total-cell-style, align: right + bottom)[#neg-red(total_v, total)],
      )
    } else {
      ([], unit) + mid + (
        table.cell(..total-cell-style, align: right + bottom)[#neg-red(quant_v, quant)],
        [.................],
        [.......................],
      )
    }
  }
}

#let arrange_summary_row(row, options, totals) = {
  // The summary only lists summary costs, which never carry a meaningful code.
  // So whenever hierarchy renumbering is on (the generated code owns the first
  // column), hide the Identification here and show only the hierarchy number.
  let move_ident = options.at("should_print_hierarchy")
  if row.at("ItemIsASum") == "True" {
    let subtotal = totals.at(row.at("Id", default: ""), default: 0.0)
    if row.at("Index") == "1" {
      // ROOT COST
      (
        strong[#id-cell(row, options.at("should_print_hierarchy"), move_ident: move_ident)],
        strong(upper(row.at("Name"))),
        [],
        if options.at("should_print_rates") {
          strong[#format-decimal(subtotal, places: 2)]
        } else { [] },
      )
    } else {
      // SUB-SECTION
      (
        id-cell(row, options.at("should_print_hierarchy"), move_ident: move_ident),
        table.cell(inset: (left: int(row.at("Index")) * 2.5mm))[#upper(row.at("Name"))],
        if options.at("should_print_rates") { format-decimal(subtotal, places: 2) } else { [] },
        [],
      )
    }
  } else {
    ()
  }
}

#let create-schedule(path, options) = {
  let show_decomp = options.at("should_print_qty_decomposition")
  let data = csv(path, row-type: dictionary)
  let totals = section-totals(data, rounded: options.at("should_eval_rounded_values", default: true))
  let cols = if show_decomp {
    (18mm, 1fr, 12mm, 12mm, 12mm, 12mm, 20mm, 20mm, 25mm)
  } else {
    (18mm, 1fr, 20mm, 20mm, 25mm)
  }
  let aln = if show_decomp {
    (center, left, center, center, center, center, right, right, right)
  } else {
    (center, left, right, right, right)
  }

  // Page-break level: 0 keeps a single flowing table (current behaviour); N > 0
  // starts a new page before every *rendered* summary cost whose hierarchy depth
  // (Index, root = 1) is <= N. A single table cannot be split by a pagebreak, so
  // the rows are grouped into one table per page; the background frame repeats
  // automatically on each page.
  //
  // A break is only taken when the current group already holds at least one leaf
  // cost item: this keeps consecutive summary headers (a parent and its first
  // sub-section) together instead of orphaning a header alone at the foot of a
  // page, so every page break lands on actual priced content.
  let break_level = options.at("page_break_level", default: 0)

  let groups = ()
  let current = ()
  let has_leaf = false
  for item in data {
    let cells = arrange_bill_of_quantity_row(item, options, totals)
    let is_sum = item.at("ItemIsASum") == "True"
    let lvl = int(item.at("Index", default: "1"))
    let rendered = cells.len() > 0
    if break_level > 0 and is_sum and rendered and lvl <= break_level and has_leaf {
      groups.push(current)
      current = ()
      has_leaf = false
    }
    current = current + cells
    if rendered and not is_sum { has_leaf = true }
  }
  if current.len() > 0 { groups.push(current) }

  for (i, g) in groups.enumerate() {
    if i > 0 { pagebreak(weak: true) }
    table(columns: cols, align: aln, stroke: none, ..g.flatten())
  }
}

#let create-summary(path, options, currency: "") = {
  let data = csv(path, row-type: dictionary)
  let rounded = options.at("should_eval_rounded_values", default: true)
  let totals = section-totals(data, rounded: rounded)
  let new_rows = data.map(item => arrange_summary_row(item, options, totals))
  // Sum of the top-level rows, so the page adds up to the sections listed on it.
  let general_total = general-total(data, totals, rounded: rounded)

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
  page_break_level: 0,
  should_print_cover: false,
  should_print_hierarchy: false,
  should_move_identification: false,
  should_print_description: false,
  should_print_each_quantity: true,
  should_print_qty_decomposition: false,
  should_print_rates: true,
  should_print_summary: true,
  should_eval_rounded_values: true,
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
    background: place(top + left, dx: 15mm, dy: 25mm,
      bill_frame(currency: project_currency, show_decomp: should_print_qty_decomposition)),
  )

  let options = (
    "nested_structure_depth": nested_structure_depth,
    "page_break_level": page_break_level,
    "should_print_hierarchy": should_print_hierarchy,
    "should_move_identification": should_move_identification,
    "should_print_description": should_print_description,
    "should_print_each_quantity": should_print_each_quantity,
    "should_print_qty_decomposition": should_print_qty_decomposition,
    "should_print_rates": should_print_rates,
    "should_eval_rounded_values": should_eval_rounded_values,
  )

  create-schedule(schedule_path, options)

  if should_print_summary {
    pagebreak()
    set page(background: place(top + left, dx: 15mm, dy: 25mm, summary_frame(currency: project_currency)))
    create-summary(schedule_path, options, currency: project_currency)
  }

  body
}
