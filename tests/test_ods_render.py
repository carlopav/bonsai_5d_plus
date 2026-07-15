# Requires pytest: pip install pytest
"""Regression test: leaf cost items and sibling section headers at the same
hierarchy depth must share the same left-indent in the ODS Bill of Quantities
(see build_bill_of_quantities() in ods_render.py)."""

import pytest

odf = pytest.importorskip("odf")

from odf.opendocument import load  # noqa: E402
from odf.style import Style, TableCellProperties  # noqa: E402
from odf.table import Table, TableCell, TableRow  # noqa: E402
from odf.text import P  # noqa: E402

from bonsai_5d_plus.module.prints_manager import ods_render  # noqa: E402

# Root section (depth 1) with two depth-2 siblings: a sub-section header and a
# leaf item, plus one depth-3 leaf nested under the sub-section.
CSV_TEXT = """Id,ItemIsASum,Hierarchy,Index,Identification,Name,Description,Unit,Quantities,Quantity,RateSubtotal,TotalPrice,SourceRate
1,True,1,1,1,Root Section,,,,,,,
2,True,1.1,2,1.1,Sub Section,,,,,,,
3,False,1.1.1,2,1.1.1,Leaf Sibling,,m,,10,5,50,
4,False,1.1.2,3,1.1.2,Leaf Child,,m,,10,5,50,
"""

OPTIONS = {
    "should_print_qty_decomposition": False,
    "should_print_hierarchy": True,
    "should_print_description": False,
    "should_print_each_quantity": False,
    "should_move_identification": False,
    "should_print_rates": True,
    "should_print_summary": False,
    "doc_type": "PRICEDBILLOFQUANTITIES",
    "title": "T",
    "schedule_name": "S",
    "schedule_description": "",
    "currency": "EUR",
}


def _description_cells(ods_path):
    """Maps each Description-column cell's text -> its padding-left (mm)."""
    doc = load(ods_path)
    table = doc.spreadsheet.getElementsByType(Table)[0]
    cell_styles = {}
    for row in table.getElementsByType(TableRow):
        cells = row.getElementsByType(TableCell)
        if len(cells) < 2:
            continue
        cell = cells[1]
        text = "".join(str(p) for p in cell.getElementsByType(P))
        style_name = cell.getAttribute("stylename")
        if text and style_name:
            cell_styles[text] = style_name

    paddings = {}
    for style in doc.automaticstyles.getElementsByType(Style):
        name = style.getAttribute("name")
        props = style.getElementsByType(TableCellProperties)
        if props:
            paddings[name] = props[0].getAttribute("paddingleft")

    return {text: paddings.get(style_name) for text, style_name in cell_styles.items()}


def test_leaf_item_and_sibling_section_share_indent(tmp_path):
    out_path = str(tmp_path / "boq.ods")
    ods_render.compile_document(CSV_TEXT, OPTIONS, out_path)

    padding_by_text = _description_cells(out_path)

    assert padding_by_text["Sub Section"] == padding_by_text["Leaf Sibling"]
    # A leaf nested one level deeper stays indented further than its parent section.
    assert padding_by_text["Leaf Child"] != padding_by_text["Sub Section"]
