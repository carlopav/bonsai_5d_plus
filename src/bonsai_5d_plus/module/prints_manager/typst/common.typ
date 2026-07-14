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
