# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

"""ODS (OpenDocument Spreadsheet) renderer for cost schedules.

Builds an odfpy ``OpenDocumentSpreadsheet`` directly (no external compiler).
Mirrors the visual structure of the Typst PDF templates (bill_of_quantities.typ,
schedule_of_rates.typ) — hierarchy indentation, bold summary rows, n°/l/w/h
measurement breakdown rows — but writes live spreadsheet formulas
(Quantity*Rate, SUM subtotals) instead of precomputed values, so the sheet
stays editable/recalculable in LibreOffice Calc / Excel.
"""

import csv
import datetime
import io
import json
import re

from ...core.formula import safe_eval, split_formula

# IFC unit Name -> printable symbol. Python port of common.typ's unit_symbols.
UNIT_SYMBOLS = {
    "METRE": "m",
    "KILO METRE": "km",
    "DECI METRE": "dm",
    "CENTI METRE": "cm",
    "MILLI METRE": "mm",
    "SQUARE_METRE": "m²",
    "SQUARE_DECIMETRE": "dm²",
    "SQUARE_CENTIMETRE": "cm²",
    "DECI SQUARE_METRE": "dm²",
    "CENTI SQUARE_METRE": "cm²",
    "MILLI SQUARE_METRE": "mm²",
    "CUBIC_METRE": "m³",
    "DECI CUBIC_METRE": "dm³",
    "CENTI CUBIC_METRE": "cm³",
    "GRAM": "g",
    "KILO GRAM": "kg",
    "MEGA GRAM": "t",
    "QUINTAL": "q",
    "HOUR": "h",
    "MINUTE": "min",
    "SECOND": "s",
    "m2": "m²",
    "m3": "m³",
    "cm2": "cm²",
    "dm2": "dm²",
    "mm2": "mm²",
    "cm3": "cm³",
    "dm3": "dm³",
    "Mg": "t",
}


def fmt_unit(u):
    """IFC unit string -> printable symbol (see UNIT_SYMBOLS)."""
    if not u:
        return ""
    tail = u.split(" / ")[-1] if " / " in u else u
    return UNIT_SYMBOLS.get(tail, tail)


def _fmt_num(value, decimals=2):
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "0"


def _safe_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _col_letter(idx0):
    """0-based column index -> spreadsheet column letter(s) (0 -> A, 26 -> AA)."""
    n = idx0 + 1
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


INDENT_MM = 4
SECTION_BG = "F2F2F2"
GRAND_TOTAL_BG = "D9D9D9"
HEADER_BG = "D9D9D9"

# Decimal places for the rounding policy (see typst/common.typ). Kept in step
# with the Typst side so PDF and ODS agree figure for figure.
QTY_DECIMALS = 2
VALUE_DECIMALS = 2


class _StyleFactory:
    """Creates and caches odf automatic styles for a single document."""

    def __init__(self, doc, currency):
        self.doc = doc
        self._cell_cache = {}
        self._para_cache = {}
        self._col_cache = {}
        self.qty_style_name = self._make_number_style()
        self.money_style_name = self._make_currency_style(currency)

    def _make_number_style(self):
        from odf.number import Number, NumberStyle

        style = NumberStyle(name="QtyDataStyle")
        style.addElement(Number(decimalplaces="2", minintegerdigits="1", grouping="true"))
        self.doc.styles.addElement(style)
        return "QtyDataStyle"

    def _make_currency_style(self, currency):
        from odf.number import CurrencySymbol, CurrencyStyle, Number, Text

        style = CurrencyStyle(name="MoneyDataStyle")
        style.addElement(Number(decimalplaces="2", minintegerdigits="1", grouping="true"))
        style.addElement(Text(text=" "))
        style.addElement(CurrencySymbol(text=currency or ""))
        self.doc.styles.addElement(style)
        return "MoneyDataStyle"

    def cell_style(self, data_style=None, bg=None, padding_left_mm=None, bold=False, wrap=False, halign=None):
        key = (data_style, bg, padding_left_mm, bold, wrap, halign)
        name = self._cell_cache.get(key)
        if name:
            return name
        from odf.style import ParagraphProperties, Style, TableCellProperties, TextProperties

        name = f"CS{len(self._cell_cache)}"
        kwargs = {"name": name, "family": "table-cell"}
        if data_style:
            kwargs["datastylename"] = data_style
        style = Style(**kwargs)
        cell_props = {}
        if bg:
            cell_props["backgroundcolor"] = bg
        if padding_left_mm is not None:
            cell_props["paddingleft"] = f"{padding_left_mm}mm"
        if wrap:
            cell_props["wrapoption"] = "wrap"
        if cell_props:
            style.addElement(TableCellProperties(**cell_props))
        if halign:
            style.addElement(ParagraphProperties(textalign=halign))
        if bold:
            style.addElement(TextProperties(fontweight="bold"))
        self.doc.automaticstyles.addElement(style)
        self._cell_cache[key] = name
        return name

    def para_style(self, bold=False, italic=False, size_pt=None):
        key = (bold, italic, size_pt)
        name = self._para_cache.get(key)
        if name:
            return name
        from odf.style import Style, TextProperties

        name = f"PS{len(self._para_cache)}"
        style = Style(name=name, family="paragraph")
        tp_kwargs = {}
        if bold:
            tp_kwargs["fontweight"] = "bold"
        if italic:
            tp_kwargs["fontstyle"] = "italic"
        if size_pt:
            tp_kwargs["fontsize"] = f"{size_pt}pt"
        if tp_kwargs:
            style.addElement(TextProperties(**tp_kwargs))
        self.doc.automaticstyles.addElement(style)
        self._para_cache[key] = name
        return name

    def col_style(self, width_mm):
        name = self._col_cache.get(width_mm)
        if name:
            return name
        from odf.style import Style, TableColumnProperties

        name = f"COL{len(self._col_cache)}"
        style = Style(name=name, family="table-column")
        style.addElement(TableColumnProperties(columnwidth=f"{width_mm}mm"))
        self.doc.automaticstyles.addElement(style)
        self._col_cache[width_mm] = name
        return name


class _Sheet:
    """A single odf Table plus a running 1-based row counter for formula addressing."""

    def __init__(self, table):
        self.table = table
        self.row_num = 0

    def new_row(self):
        from odf.table import TableRow

        self.row_num += 1
        row = TableRow()
        self.table.addElement(row)
        return row

    def text_cell(self, row, lines, styles, cell_style_name=None):
        """``lines``: list of (text, bold, italic, size_pt) tuples."""
        from odf.table import TableCell
        from odf.text import P

        kwargs = {"valuetype": "string"}
        if cell_style_name:
            kwargs["stylename"] = cell_style_name
        cell = TableCell(**kwargs)
        for text, bold, italic, size in lines:
            if not text:
                continue
            pstyle = styles.para_style(bold=bold, italic=italic, size_pt=size)
            cell.addElement(P(text=text, stylename=pstyle))
        row.addElement(cell)
        return cell

    def empty_cell(self, row, cell_style_name=None):
        from odf.table import TableCell

        cell = TableCell(stylename=cell_style_name) if cell_style_name else TableCell()
        row.addElement(cell)
        return cell

    def num_cell(self, row, value, cell_style_name, formula=None, decimals=2):
        from odf.table import TableCell
        from odf.text import P

        kwargs = {"valuetype": "float", "value": float(value), "stylename": cell_style_name}
        if formula:
            kwargs["formula"] = formula
        cell = TableCell(**kwargs)
        cell.addElement(P(text=_fmt_num(value, decimals)))
        row.addElement(cell)
        return cell


def _add_columns(sheet, styles, widths_mm):
    from odf.table import TableColumn

    for w in widths_mm:
        sheet.table.addElement(TableColumn(stylename=styles.col_style(w)))


def _write_info_block(sheet, styles, title, schedule_name, schedule_description, doc_type, currency):
    label_style = styles.cell_style(bold=True)
    pairs = [("Project:", title), ("Schedule:", schedule_name)]
    if schedule_description:
        pairs.append(("Description:", schedule_description))
    pairs.append(("Type:", doc_type))
    if currency:
        pairs.append(("Currency:", currency))
    pairs.append(("Date:", datetime.date.today().strftime("%d/%m/%Y")))

    for label, value in pairs:
        row = sheet.new_row()
        sheet.text_cell(row, [(label, True, False, None)], styles, cell_style_name=label_style)
        sheet.text_cell(row, [(value or "", False, False, None)], styles)
    sheet.new_row()  # blank separator row


def _id_lines(row, show_hierarchy, move_ident=False):
    ident = row.get("Identification", "") or ""
    if not show_hierarchy:
        return [(ident, False, False, None)]
    h = row.get("Hierarchy", "") or ""
    if move_ident:
        return [(h, False, False, 7)] if h else []
    if h:
        lines = [(h, False, False, 7)]
        if ident:
            lines.append((ident, False, False, None))
        return lines
    return [(ident, False, False, None)]


def _quantities_of(row):
    raw = row.get("Quantities") or ""
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return []


def build_bill_of_quantities(doc, rows, options):
    """Write the Bill of Quantities sheet. Returns (sheet_name, id_to_addr, grand_total_addr)."""
    from odf.table import Table

    show_decomp = options["should_print_qty_decomposition"]
    show_hierarchy = options["should_print_hierarchy"]
    show_desc = options["should_print_description"]
    show_each_qty = options["should_print_each_quantity"]
    move_ident = options["should_move_identification"] and show_hierarchy
    show_rates = options["should_print_rates"] and options["doc_type"] != "UNPRICEDBILLOFQUANTITIES"
    # See the rounding policy in typst/common.typ. When on, the live formulas
    # round each product before the =SUM()s add them, so the sheet recomputes
    # the same figures the PDF prints. When off, the raw full-precision
    # arithmetic is kept, matching Bonsai's cost panel.
    round_values = options.get("should_eval_rounded_values", True)

    def _round(x):
        return round(x, QTY_DECIMALS) if round_values else x

    def _mult_formula(cell1, cell2):
        raw = "{}*{}".format(cell1, cell2)
        return "=ROUND({};{})".format(raw, VALUE_DECIMALS) if round_values else "=" + raw
    currency = options.get("currency", "")

    sheet_name = "Bill of Quantities"
    styles = options["_styles"]

    # Column layout.
    columns = ["Code", "Description"]
    if show_decomp:
        columns += ["n°", "l", "w", "h/w"]
    columns += ["Quantity", "Unit"]
    if show_rates:
        columns += ["Rate", "Total"]
    col_idx = {name: i for i, name in enumerate(columns)}

    def addr(col_name, row_num):
        return f"{_col_letter(col_idx[col_name])}{row_num}"

    table = Table(name=sheet_name)
    sheet = _Sheet(table)

    widths = {
        "Code": 20,
        "Description": 90 if not show_decomp else 60,
        "n°": 12,
        "l": 12,
        "w": 12,
        "h/w": 12,
        "Quantity": 20,
        "Unit": 14,
        "Rate": 20,
        "Total": 25,
    }
    _add_columns(sheet, styles, [widths[c] for c in columns])

    _write_info_block(
        sheet,
        styles,
        options.get("title", ""),
        options.get("schedule_name", ""),
        options.get("schedule_description", ""),
        options["doc_type"],
        currency,
    )

    header_style = styles.cell_style(bg=HEADER_BG, bold=True)
    hrow = sheet.new_row()
    for c in columns:
        sheet.text_cell(hrow, [(c, True, False, None)], styles, cell_style_name=header_style)

    section_cell_style = styles.cell_style(bg=SECTION_BG)
    section_indent_cache = {}

    def section_indent_style(level):
        s = section_indent_cache.get(level)
        if s is None:
            s = styles.cell_style(bg=SECTION_BG, padding_left_mm=level * INDENT_MM, wrap=True)
            section_indent_cache[level] = s
        return s

    id_to_addr = {}
    root_frame = {"depth": 0, "total_cell": None, "children_addrs": []}
    stack = [root_frame]

    def finalize_section(frame):
        cell = frame["total_cell"]
        if cell is None:
            return
        children = frame["children_addrs"]
        if children:
            cell.setAttribute("formula", "=SUM({})".format(",".join(children)))

    for row in rows:
        depth = int(row.get("Index", "1") or "1")
        is_sum = row.get("ItemIsASum") == "True"

        while stack[-1]["depth"] >= depth:
            finalize_section(stack.pop())
        parent = stack[-1]

        if is_sum:
            r = sheet.new_row()
            sheet.text_cell(r, _id_lines(row, show_hierarchy), styles, cell_style_name=section_cell_style)
            desc_lines = [(row.get("Name", "") or "", True, False, None)]
            source_rate = row.get("SourceRate", "") or ""
            if source_rate:
                desc_lines.append((source_rate, False, True, 8))
            sheet.text_cell(r, desc_lines, styles, cell_style_name=section_indent_style(depth - 1))
            if show_decomp:
                for _ in range(4):
                    sheet.empty_cell(r, cell_style_name=section_cell_style)
            sheet.empty_cell(r, cell_style_name=section_cell_style)  # Quantity
            sheet.empty_cell(r, cell_style_name=section_cell_style)  # Unit
            total_cell = None
            if show_rates:
                sheet.empty_cell(r, cell_style_name=section_cell_style)  # Rate
                money_bold = styles.cell_style(
                    data_style=styles.money_style_name, bg=SECTION_BG, bold=True, halign="end"
                )
                total_cell = sheet.num_cell(r, _round(_safe_float(row.get("TotalPrice"))), money_bold)
            row_id = row.get("Id", "")
            if row_id:
                id_to_addr[row_id] = addr("Total", sheet.row_num) if show_rates else None
            frame = {"depth": depth, "total_cell": total_cell, "children_addrs": []}
            stack.append(frame)
            if show_rates and row_id:
                parent["children_addrs"].append(addr("Total", sheet.row_num))
        else:
            r = sheet.new_row()
            main_row_num = sheet.row_num
            sheet.text_cell(r, _id_lines(row, show_hierarchy, move_ident=move_ident), styles)
            name = row.get("Name", "") or "Unnamed Cost Item"
            desc_lines = []
            ident = row.get("Identification", "") or ""
            if move_ident and ident:
                desc_lines.append((f"[{ident}]", False, False, 7))
            desc_lines.append((name, True, False, None))
            source_rate = row.get("SourceRate", "") or ""
            if source_rate:
                desc_lines.append((source_rate, False, True, 8))
            if show_desc and row.get("Description"):
                desc_lines.append((row.get("Description"), False, False, 8))
            indent_style = styles.cell_style(padding_left_mm=(depth - 1) * INDENT_MM, wrap=True)
            sheet.text_cell(r, desc_lines, styles, cell_style_name=indent_style)
            if show_decomp:
                for _ in range(4):
                    sheet.empty_cell(r)

            quantities = _quantities_of(row) if show_each_qty else []
            qty_style = styles.cell_style(data_style=styles.qty_style_name, halign="end")
            if quantities:
                sub_addrs = [addr("Quantity", main_row_num + i) for i in range(1, len(quantities) + 1)]
                qty_formula = "=SUM({})".format(",".join(sub_addrs))
                # Sum of the rounded sub-quantities, matching the =SUM over the
                # rounded sub-rows written below, so the column adds up by hand.
                qty_value = sum(_round(_safe_float(q[1])) for q in quantities)
                sheet.num_cell(r, qty_value, qty_style, formula=qty_formula)
            else:
                qty_value = _round(_safe_float(row.get("Quantity")))
                sheet.num_cell(r, qty_value, qty_style)
            sheet.text_cell(r, [(fmt_unit(row.get("Unit", "")), False, False, None)], styles)

            total_addr = None
            if show_rates:
                rate_value = _round(_safe_float(row.get("RateSubtotal")))
                money_style = styles.cell_style(data_style=styles.money_style_name, halign="end")
                sheet.num_cell(r, rate_value, money_style)
                total_formula = _mult_formula(addr("Quantity", main_row_num), addr("Rate", main_row_num))
                money_bold = styles.cell_style(data_style=styles.money_style_name, bold=True, halign="end")
                sheet.num_cell(r, _round(qty_value * rate_value), money_bold, formula=total_formula)
                total_addr = addr("Total", main_row_num)

            row_id = row.get("Id", "")
            if row_id:
                id_to_addr[row_id] = total_addr

            # Measurement breakdown sub-rows.
            for q in quantities:
                qname = "" if q[0] == "Unnamed" else (q[0] or "")
                qvalue = _round(_safe_float(q[1]))
                formula_text = q[2] if len(q) > 2 else ""
                sr = sheet.new_row()
                sheet.empty_cell(sr)
                sub_indent = styles.cell_style(padding_left_mm=depth * INDENT_MM, wrap=True)
                sheet.text_cell(sr, [(qname, False, True, 8)], styles, cell_style_name=sub_indent)
                if show_decomp:
                    factor_cells = split_formula(formula_text, qvalue)[:4]
                    for cell_text in factor_cells:
                        _write_factor_cell(sheet, sr, cell_text, styles)
                sheet.num_cell(sr, qvalue, qty_style)
                sheet.empty_cell(sr)  # Unit
                if show_rates:
                    sheet.empty_cell(sr)  # Rate
                    sheet.empty_cell(sr)  # Total

            if total_addr and row_id:
                parent["children_addrs"].append(total_addr)

    while stack:
        finalize_section(stack.pop())

    grand_total_addr = None
    if show_rates and root_frame["children_addrs"]:
        r = sheet.new_row()
        label_style = styles.cell_style(bg=GRAND_TOTAL_BG, bold=True)
        sheet.empty_cell(r, cell_style_name=label_style)
        sheet.text_cell(r, [("GENERAL TOTAL", True, False, None)], styles, cell_style_name=label_style)
        if show_decomp:
            for _ in range(4):
                sheet.empty_cell(r, cell_style_name=label_style)
        sheet.empty_cell(r, cell_style_name=label_style)  # Quantity
        sheet.empty_cell(r, cell_style_name=label_style)  # Unit
        sheet.empty_cell(r, cell_style_name=label_style)  # Rate
        money_bold = styles.cell_style(data_style=styles.money_style_name, bg=GRAND_TOTAL_BG, bold=True, halign="end")
        total_formula = "=SUM({})".format(",".join(root_frame["children_addrs"]))
        sheet.num_cell(r, 0.0, money_bold, formula=total_formula)
        grand_total_addr = addr("Total", sheet.row_num)

    doc.spreadsheet.addElement(table)
    return sheet_name, id_to_addr, grand_total_addr


def _write_factor_cell(sheet, row, cell_text, styles):
    qty_style = styles.cell_style(data_style=styles.qty_style_name, halign="end")
    if cell_text == "":
        sheet.num_cell(row, 1.0, qty_style)
        return
    is_plain_number = re.fullmatch(r"-?\d+(\.\d+)?", cell_text.strip()) is not None
    if is_plain_number:
        sheet.num_cell(row, _safe_float(cell_text), qty_style)
        return
    value = safe_eval(cell_text)
    sheet.num_cell(row, value if value is not None else 0.0, qty_style, formula=f"={cell_text}")


def build_schedule_of_rates(doc, rows, options):
    """Write the flat Schedule of Rates sheet: Code | Description | Unit | Rate."""
    from odf.table import Table

    show_hierarchy = options["should_print_hierarchy"]
    show_desc = options["should_print_description"]
    currency = options.get("currency", "")
    styles = options["_styles"]

    sheet_name = "Schedule of Rates"
    table = Table(name=sheet_name)
    sheet = _Sheet(table)
    _add_columns(sheet, styles, [25, 110, 20, 25])

    _write_info_block(
        sheet,
        styles,
        options.get("title", ""),
        options.get("schedule_name", ""),
        options.get("schedule_description", ""),
        options["doc_type"],
        currency,
    )

    header_style = styles.cell_style(bg=HEADER_BG, bold=True)
    hrow = sheet.new_row()
    for c in ["Code", "Description", "Unit", "Rate"]:
        sheet.text_cell(hrow, [(c, True, False, None)], styles, cell_style_name=header_style)

    money_style = styles.cell_style(data_style=styles.money_style_name, halign="end")
    for row in rows:
        if row.get("ItemIsASum") == "True":
            continue
        r = sheet.new_row()
        sheet.text_cell(r, _id_lines(row, show_hierarchy), styles)
        desc_lines = [(row.get("Name", "") or "", True, False, None)]
        source_rate = row.get("SourceRate", "") or ""
        if source_rate:
            desc_lines.append((source_rate, False, True, 8))
        if show_desc and row.get("Description"):
            desc_lines.append((row.get("Description"), False, False, 8))
        sheet.text_cell(r, desc_lines, styles)
        sheet.text_cell(r, [(fmt_unit(row.get("Unit", "")), False, False, None)], styles)
        sheet.num_cell(r, _safe_float(row.get("RateSubtotal")), money_style)

    doc.spreadsheet.addElement(table)


def build_summary_sheet(doc, rows, options, main_sheet_name, id_to_addr, grand_total_addr):
    """A "Summary" tab listing the ItemIsASum rows, referencing the main sheet's subtotal cells."""
    from odf.table import Table

    show_hierarchy = options["should_print_hierarchy"]
    show_rates = options["should_print_rates"] and options["doc_type"] != "UNPRICEDBILLOFQUANTITIES"
    styles = options["_styles"]

    table = Table(name="Summary")
    sheet = _Sheet(table)
    _add_columns(sheet, styles, [18, 120, 30])

    header_style = styles.cell_style(bg=HEADER_BG, bold=True)
    hrow = sheet.new_row()
    for c in ["Code", "Description", "Total"]:
        sheet.text_cell(hrow, [(c, True, False, None)], styles, cell_style_name=header_style)

    money_style = styles.cell_style(data_style=styles.money_style_name, halign="end")
    money_bold = styles.cell_style(data_style=styles.money_style_name, bold=True, halign="end")

    for row in rows:
        if row.get("ItemIsASum") != "True":
            continue
        depth = int(row.get("Index", "1") or "1")
        is_root = depth == 1
        r = sheet.new_row()
        sheet.text_cell(r, _id_lines(row, show_hierarchy), styles, cell_style_name=styles.cell_style(bold=is_root))
        indent_style = styles.cell_style(bold=is_root, padding_left_mm=(depth - 1) * INDENT_MM, wrap=True)
        sheet.text_cell(r, [(row.get("Name", "") or "", is_root, False, None)], styles, cell_style_name=indent_style)
        ref_addr = id_to_addr.get(row.get("Id", ""))
        if show_rates and ref_addr:
            formula = f"='{main_sheet_name}'.{ref_addr}"
            sheet.num_cell(
                r, _safe_float(row.get("TotalPrice")), money_bold if is_root else money_style, formula=formula
            )
        else:
            sheet.empty_cell(r)

    if show_rates and grand_total_addr:
        r = sheet.new_row()
        label_style = styles.cell_style(bg=GRAND_TOTAL_BG, bold=True)
        sheet.empty_cell(r, cell_style_name=label_style)
        sheet.text_cell(r, [("GENERAL TOTAL", True, False, None)], styles, cell_style_name=label_style)
        formula = f"='{main_sheet_name}'.{grand_total_addr}"
        total_style = styles.cell_style(data_style=styles.money_style_name, bg=GRAND_TOTAL_BG, bold=True, halign="end")
        sheet.num_cell(r, 0.0, total_style, formula=formula)

    doc.spreadsheet.addElement(table)


def compile_document(csv_text, options, output_path):
    """Entry point: CSV text (from ifc5d) + option dict -> saved .ods file.

    ``options`` mirrors the ExportScheduleToOdsOperator properties, plus
    ``doc_type``, ``title``, ``schedule_name``, ``schedule_description``,
    ``currency`` (added by the caller alongside the bpy.props booleans).
    """
    from odf.opendocument import OpenDocumentSpreadsheet

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    doc = OpenDocumentSpreadsheet()
    styles = _StyleFactory(doc, options.get("currency", ""))
    options = dict(options)
    options["_styles"] = styles

    if options["doc_type"] == "SCHEDULEOFRATES":
        build_schedule_of_rates(doc, rows, options)
    else:
        main_name, id_to_addr, grand_total_addr = build_bill_of_quantities(doc, rows, options)
        if options.get("should_print_summary"):
            build_summary_sheet(doc, rows, options, main_name, id_to_addr, grand_total_addr)

    doc.save(output_path)
