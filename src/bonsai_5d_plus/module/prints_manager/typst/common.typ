// Common Typst module for Bonsai5D+ cost documents.
// Shared primitives used by every document template: fonts, number / currency
// / unit formatting, and page chrome (header, footer, cover, page frame).
//
// Each document file imports this with `#import "common.typ": *` and defines
// only its own table layout and render entry point.
//
// author: carlo pavan
// year: 2026

#let template_fonts = ("Liberation Sans", "Roboto", "Arial", "Calibri")

// Thousands-separated decimal with a fixed number of places.
// Accepts numbers or numeric strings; handles negatives.
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

// Money with an optional trailing currency code.
#let fmt-money(num, currency: "") = {
  format-decimal(num, places: 2) + (if currency != "" { " " + currency } else { "" })
}

// — Rounding policy —
// A printed cost document has to be checkable with a calculator: every figure
// must be recomputable from the figures printed above it. That only holds if
// the sums are taken over the *rounded* values, which is why the rounding
// happens here — early, on the way in — rather than at the point where each
// number is finally formatted.
//
// Summing rounded values is not the same as rounding the sum: three rows of
// 0.005 each print as 0.01 and add up to 0.03, while the raw sum 0.015 rounds
// to 0.02. Only the first can be reproduced by hand, so it is the one used.
//
// The formula printed beside a measurement row is deliberately exempt:
// "3.70*6.81" evaluates to 25.197 while the row prints 25.20. The formula
// documents how the measure was obtained; it is the column that has to add up.
//
// Nothing here is written back to IFC: the stored values keep their full
// precision, as Bonsai writes them. This is presentation only.
//
// Every entry point takes `rounded`, wired to the export option
// `should_eval_rounded_values` (on by default). Turning it off restores the
// raw full-precision arithmetic — the same figures Bonsai's own cost panel
// shows — which is what to compare against when a total needs explaining.

#let QTY_PLACES = 2
#let MONEY_PLACES = 2

#let round-qty(x) = calc.round(float(x), digits: QTY_PLACES)
#let round-money(x) = calc.round(float(x), digits: MONEY_PLACES)

// CSV cells are strings and an unmeasured item leaves them empty.
#let num-or-zero(row, key) = {
  let raw = row.at(key, default: "")
  if raw == "" { 0.0 } else { float(raw) }
}

// A cost item's measurement rows, as (name, value, formula) triples.
#let row-quantities(row) = {
  let raw = row.at("Quantities", default: "")
  if raw == "" { () } else { json.decode(raw) }
}

// A cost item's quantity: the sum of its rounded measurement rows, so the
// Quantity column always adds up to the breakdown printed under it. Computed
// this way even when the breakdown is hidden, so that switching a print option
// never changes a total. Items measured without a breakdown fall back to the
// ifc5d figure.
#let row-quantity(row, rounded: true) = {
  if not rounded { return num-or-zero(row, "Quantity") }
  let qs = row-quantities(row)
  if qs.len() == 0 {
    round-qty(num-or-zero(row, "Quantity"))
  } else {
    qs.map(q => round-qty(q.at(1))).sum(default: 0.0)
  }
}

#let row-rate(row, rounded: true) = {
  let v = num-or-zero(row, "RateSubtotal")
  if rounded { round-money(v) } else { v }
}

#let row-total(row, rounded: true) = {
  let v = row-quantity(row, rounded: rounded) * row-rate(row, rounded: rounded)
  if rounded { round-money(v) } else { v }
}

// Section subtotals: `Id -> total`, each the sum of the rounded totals of the
// leaf items below it. Deliberately not ifc5d's "TotalPrice", which comes from
// the "*" cost value — i.e. from ifcopenshell's full-precision recursive sum —
// and so would not match the rows printed above it.
//
// The CSV rows are flat, with "Index" carrying the depth (root = 1), so one
// forward pass suffices: keep the currently open summary at each depth and let
// every leaf add itself to all of them.
// When rounded is off, a summary keeps ifc5d's own "TotalPrice" (the "*" cost
// value, ifcopenshell's full-precision recursive sum) so the document matches
// Bonsai's cost panel exactly.
#let section-totals(data, rounded: true) = {
  if not rounded {
    let totals = (:)
    for row in data {
      if row.at("ItemIsASum") == "True" {
        totals.insert(row.at("Id", default: ""), num-or-zero(row, "TotalPrice"))
      }
    }
    return totals
  }
  let totals = (:)
  let open = ()  // open.at(d - 1) = Id of the summary row open at depth d
  for row in data {
    let depth = int(row.at("Index", default: "1"))
    if row.at("ItemIsASum") == "True" {
      open = open.slice(0, calc.min(depth - 1, open.len()))
      while open.len() < depth - 1 { open.push(none) }
      open.push(row.at("Id", default: ""))
      totals.insert(row.at("Id", default: ""), 0.0)
    } else {
      let t = row-total(row)
      for id in open {
        if id != none and id != "" {
          totals.insert(id, totals.at(id, default: 0.0) + t)
        }
      }
    }
  }
  totals
}

// Grand total: the sum of the top-level rows, so the summary page adds up to
// exactly the sections listed on it.
#let general-total(data, totals, rounded: true) = {
  data
    .filter(row => int(row.at("Index", default: "1")) == 1)
    .map(row => if row.at("ItemIsASum") == "True" {
      totals.at(row.at("Id", default: ""), default: 0.0)
    } else {
      row-total(row, rounded: rounded)
    })
    .sum(default: 0.0)
}

// IFC unit Name → printable symbol. Keys cover both the verbose form produced
// by ifc5d's format_unit ("<UnitType> / <Prefix> <Name>", we map the part after
// " / ") and the compact symbols produced by ifcopenshell's get_unit_symbol
// ("m2", "kg", "cm2", "Mg" …). The prefix-on-area/volume convention is standard:
// cm² = SQUARE_METRE with prefix CENTI, dm³ = CUBIC_METRE with prefix DECI, etc.
#let unit_symbols = (
  // length
  "METRE": "m", "KILO METRE": "km", "DECI METRE": "dm", "CENTI METRE": "cm", "MILLI METRE": "mm",
  // area (conversion-unit names we create, plus the prefixed-SI spelling other tools may use)
  "SQUARE_METRE": "m²", "SQUARE_DECIMETRE": "dm²", "SQUARE_CENTIMETRE": "cm²",
  "DECI SQUARE_METRE": "dm²", "CENTI SQUARE_METRE": "cm²", "MILLI SQUARE_METRE": "mm²",
  // volume
  "CUBIC_METRE": "m³", "DECI CUBIC_METRE": "dm³", "CENTI CUBIC_METRE": "cm³",
  // mass (tonne kept as "t" rather than the SI "Mg")
  "GRAM": "g", "KILO GRAM": "kg", "MEGA GRAM": "t", "QUINTAL": "q",
  // time
  "HOUR": "h", "MINUTE": "min", "SECOND": "s",
  // compact forms from ifcopenshell.get_unit_symbol
  "m2": "m²", "m3": "m³", "cm2": "cm²", "dm2": "dm²", "mm2": "mm²", "cm3": "cm³", "dm3": "dm³", "Mg": "t",
)

// IFC unit → printable symbol. Handles the verbose "<UnitType> / <Name>" form,
// the compact symbol form, and passes any free-text unit (USERDEFINED such as
// "a corpo", "cad", "q", "mq/cm") through unchanged.
#let fmt-unit(u) = {
  if u == "" { return "" }
  let tail = if u.contains(" / ") { u.split(" / ").last() } else { u }
  unit_symbols.at(tail, default: tail)
}

// First-column cell: the cost item's Identification, optionally prefixed by the
// hierarchical renumbering (the CSV "Hierarchy" column) when it is enabled.
// Identification is always shown; the hierarchy number, when on, sits above it.
// When `move_ident` is set (only used by the bill, and only together with
// hierarchy renumbering), the Identification is instead rendered in the
// Description column, so the first column carries only the generated code.
#let id-cell(row, show_hierarchy, move_ident: false) = {
  let ident = row.at("Identification", default: "")
  if show_hierarchy {
    let h = row.at("Hierarchy", default: "")
    if move_ident {
      if h != "" { text(7pt)[#h] } else { [] }
    } else if h != "" {
      text(7pt)[#h] + (if ident != "" { linebreak() + [#ident] } else { [] })
    } else { [#ident] }
  } else {
    [#ident]
  }
}

// Linked Schedule-of-Rates item, shown under the Name. The label is injected
// into the CSV as the "SourceRate" column (computed from the IfcRelAssignsToControl
// relationship): "<ScheduleOfRates Name> - <control Identification> <control Name>".
#let source-rate-line(row) = {
  let s = row.at("SourceRate", default: "")
  if s != "" { linebreak() + text(7pt, style: "italic")[#s] } else { [] }
}

#let today-str() = datetime.today().display("[day]/[month]/[year]")

// Standard footer: date on the left, page number on the right.
// Text size is inherited from the page body (matches the legacy templates).
#let std-footer() = context [
  #grid(
    columns: (1fr, 1fr),
    align: (left, right),
    [#today-str()],
    [#counter(page).display("1/1", both: true)],
  )
]

// Standard two-column running header (e.g. project title / document name).
#let std-header(left_text, right_text) = [
  #set text(font: template_fonts, size: 9pt)
  #table(
    columns: (1fr, 2fr),
    rows: 10mm,
    stroke: none,
    inset: 0mm,
    align: (top + left, top + right),
    [#left_text], [#right_text],
  )
]

// Page-framing show-rule wrapper. A document calls:
//   #show: page-frame.with(header: ..., background: ...)
// `footer: auto` uses std-footer(); pass `none` or custom content to override.
#let page-frame(
  header: none,
  footer: auto,
  background: none,
  margin: (left: 15mm, right: 10mm, top: 35mm, bottom: 20mm),
  body,
) = {
  set text(font: template_fonts, size: 8pt, lang: "it")
  set page(
    paper: "a4",
    margin: margin,
    numbering: "1/1",
    number-align: end,
    header: header,
    footer: if footer == auto { std-footer() } else { footer },
    background: background,
  )
  body
}

// Cover page for cost schedules. Kept faithful to the legacy ifc5d template
// so Bill-of-Quantities / Schedule-of-Rates output is unchanged.
#let schedule_cover(title, schedule_name, schedule_description, schedule_type) = {
  set page(
    numbering: none,
    margin: (top: 35mm, left: 20mm, right: 10mm),
    background: place(top + left, dx: 15mm, dy: 25mm,
      table(columns: 185mm, rows: 254mm, align: (center, left, center), stroke: 1pt)),
    footer: [
      #set text(size: 7pt, fill: gray)
      #align(right)[#linebreak()powered by IfcOpenShell]
    ],
  )
  set text(font: template_fonts, size: 12pt)
  place(bottom + left, dx: 0mm, dy: -10mm,
    grid(
      columns: (30mm, 135mm),
      gutter: 2em,
      align: top + left,
      [Title:], [*#title*],
      [Schedule:], [*#schedule_name*],
      [Schedule Type:], [#schedule_type],
      if schedule_description != "" { [Description:] },
      if schedule_description != "" { [#schedule_description] },
      [], [],
      [#today-str()], [Signed],
      [], [.................................],
    )
  )
}
