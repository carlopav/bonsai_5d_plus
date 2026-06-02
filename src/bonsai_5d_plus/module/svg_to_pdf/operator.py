# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import bpy

from ...tool.cost import ifc_unit_to_str as _ifc_unit_to_str


def _open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"


def _get_ifc():
    try:
        from bonsai import tool
        return tool.Ifc.get()
    except Exception:
        return None


def _get_ifc_path():
    try:
        from bonsai import tool
        return tool.Ifc.get_path()
    except Exception:
        return None


def _ensure_ifc5d():
    try:
        import ifc5d  # noqa: F401
        return True
    except ImportError:
        pass
    # Bonsai wheels path fallback
    appdata = os.environ.get("APPDATA", "")
    site = os.path.join(
        appdata,
        r"Blender Foundation\Blender\5.1\extensions\.local\lib\python3.13\site-packages",
    )
    if os.path.isdir(site) and site not in sys.path:
        sys.path.insert(0, site)
    try:
        import ifc5d  # noqa: F401
        return True
    except ImportError:
        return False


def _ensure_typst():
    try:
        import typst  # noqa: F401
        return True
    except ImportError:
        pass
    appdata = os.environ.get("APPDATA", "")
    site = os.path.join(
        appdata,
        r"Blender Foundation\Blender\5.1\extensions\.local\lib\python3.13\site-packages",
    )
    if os.path.isdir(site) and site not in sys.path:
        sys.path.insert(0, site)
    try:
        import typst  # noqa: F401
        return True
    except ImportError:
        return False


def _find_sheet_svgs():
    ifc = _get_ifc()
    if ifc is None:
        return []
    ifc_path = _get_ifc_path()
    if not ifc_path:
        return []
    ifc_dir = os.path.dirname(os.path.abspath(ifc_path))
    sheets_dir = os.path.join(ifc_dir, "sheets")

    try:
        from bonsai.tool import Drawing as _Drawing
        _get_uri = _Drawing.get_document_uri
    except Exception:
        _get_uri = None

    svgs = []
    for doc in ifc.by_type("IfcDocumentInformation"):
        if getattr(doc, "Scope", None) != "SHEET":
            continue

        path = None

        if _get_uri is not None:
            try:
                path = _get_uri(doc)
            except Exception:
                path = None
        if path and not os.path.isfile(path):
            path = None

        if not path:
            loc = getattr(doc, "Location", None) or ""
            if loc:
                p = loc if os.path.isabs(loc) else os.path.join(ifc_dir, loc)
                p = os.path.normpath(p)
                if os.path.isfile(p):
                    path = p

        if not path:
            ident = getattr(doc, "Identification", None) or ""
            name = getattr(doc, "Name", None) or ""
            for candidate in [
                os.path.join(sheets_dir, f"{ident} - {name}.svg") if ident and name else None,
                os.path.join(sheets_dir, f"{name}.svg") if name else None,
                os.path.join(sheets_dir, f"{ident}.svg") if ident else None,
            ]:
                if candidate and os.path.isfile(candidate):
                    path = candidate
                    break

        if path:
            svgs.append(os.path.normpath(path))

    return svgs


def _inline_svg_images(svg_path, _depth=0):
    from urllib.parse import unquote

    if _depth > 8:
        return None

    for prefix, uri in [
        ("", _SVG_NS),
        ("xlink", _XLINK_NS),
        ("dc", "http://purl.org/dc/elements/1.1/"),
        ("cc", "http://creativecommons.org/ns#"),
        ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
        ("inkscape", "http://www.inkscape.org/namespaces/inkscape"),
        ("sodipodi", "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd"),
    ]:
        try:
            ET.register_namespace(prefix, uri)
        except Exception:
            pass

    tree = ET.parse(svg_path)
    root = tree.getroot()
    svg_dir = os.path.dirname(svg_path)

    parent_map = {child: parent for parent in root.iter() for child in parent}

    to_replace = []
    for el in root.iter(f"{{{_SVG_NS}}}image"):
        href_raw = el.get(f"{{{_XLINK_NS}}}href") or el.get("href") or ""
        href = unquote(href_raw)
        if href.lower().endswith(".svg"):
            p = href if os.path.isabs(href) else os.path.join(svg_dir, href.replace("/", os.sep))
            p = os.path.normpath(p)
            if os.path.isfile(p):
                to_replace.append((el, p))

    if not to_replace:
        return None

    for image_el, img_path in to_replace:
        parent = parent_map.get(image_el)
        if parent is None:
            continue
        sub_inlined = _inline_svg_images(img_path, _depth + 1)
        if sub_inlined is not None:
            sub_root = ET.fromstring(sub_inlined)
        else:
            sub_root = ET.parse(img_path).getroot()
        for attr in ("x", "y", "width", "height"):
            val = image_el.get(attr)
            if val is not None:
                sub_root.set(attr, val)
        idx = list(parent).index(image_el)
        parent.remove(image_el)
        parent.insert(idx, sub_root)

    xml_str = ET.tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str).encode("utf-8")


def _svg_to_pdf(svg_path):
    import typst
    import tempfile

    pdf_path = os.path.splitext(svg_path)[0] + ".pdf"
    svg_dir = os.path.dirname(svg_path)
    project_dir = os.path.dirname(svg_dir)

    inlined = _inline_svg_images(svg_path)

    if inlined is not None:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".svg", dir=svg_dir)
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(inlined)
            rel = os.path.relpath(tmp_path, project_dir).replace("\\", "/")
            typ = f'#set page(width: auto, height: auto, margin: 0pt)\n#image("{rel}")\n'
            typst.compile(typ.encode(), output=pdf_path, root=project_dir, format="pdf")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    else:
        rel = os.path.relpath(svg_path, project_dir).replace("\\", "/")
        typ = f'#set page(width: auto, height: auto, margin: 0pt)\n#image("{rel}")\n'
        typst.compile(typ.encode(), output=pdf_path, root=project_dir, format="pdf")

    return pdf_path


class ExportSheetsToPdfOperator(bpy.types.Operator):
    """Convert all Bonsai sheet SVGs to PDF via typst, saved alongside the SVGs."""

    bl_idname = "bim.export_sheets_to_pdf"
    bl_label = "Convert All Sheets to PDF"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _get_ifc() is not None

    def execute(self, context):
        if not _ensure_typst():
            self.report(
                {"ERROR"},
                "typst Python package not found. "
                "Install it in Blender's Python environment: pip install typst",
            )
            return {"CANCELLED"}

        svgs = _find_sheet_svgs()
        if not svgs:
            ifc = _get_ifc()
            if ifc:
                sheets = [
                    d for d in ifc.by_type("IfcDocumentInformation")
                    if getattr(d, "Scope", None) == "SHEET"
                ]
                if sheets:
                    self.report(
                        {"WARNING"},
                        f"Found {len(sheets)} sheet(s) in IFC but SVG files not found on disk. "
                        "Build/export the sheets from Bonsai first.",
                    )
                else:
                    self.report({"WARNING"}, "No sheet IfcDocumentInformation (Scope='SHEET') found.")
            return {"CANCELLED"}

        ok = 0
        generated = []
        for svg in svgs:
            try:
                pdf = _svg_to_pdf(svg)
                generated.append(pdf)
                ok += 1
            except Exception as exc:
                self.report({"WARNING"}, f"{os.path.basename(svg)}: {exc}")

        self.report({"INFO"}, f"Converted {ok}/{len(svgs)} sheet(s) to PDF.")
        if generated:
            if len(generated) <= 3:
                for pdf in generated:
                    _open_file(pdf)
            else:
                _open_file(os.path.dirname(generated[0]))
        return {"FINISHED"}


class ExportScheduleToPdfOperator(bpy.types.Operator):
    """Export the active Cost Schedule to PDF using the ifc5d Typst template."""
    bl_idname = "bim.export_schedule_to_pdf"
    bl_label = "Export Schedule to PDF"
    bl_options = {"REGISTER"}

    force_schedule_type: bpy.props.EnumProperty(
        name="Document Type",
        items=[
            ("AUTO",                    "Auto (from schedule type)",  ""),
            ("PRICEDBILLOFQUANTITIES",  "Priced Bill of Quantities",  ""),
            ("UNPRICEDBILLOFQUANTITIES","Unpriced Bill of Quantities",""),
            ("SCHEDULEOFRATES",         "Schedule of Rates",          ""),
        ],
        default="AUTO",
    )
    should_print_rates:          bpy.props.BoolProperty(name="Show Rates",              default=True)
    should_print_description:    bpy.props.BoolProperty(name="Show Descriptions",       default=False)
    should_print_each_quantity:  bpy.props.BoolProperty(name="Show Quantity Breakdown", default=True)
    should_print_summary:        bpy.props.BoolProperty(name="Show Summary Page",       default=True)
    should_print_cover:          bpy.props.BoolProperty(name="Show Cover Page",         default=False)
    should_print_cost_ids:       bpy.props.BoolProperty(name="Show Item IDs",           default=True)
    nested_structure_depth:      bpy.props.IntProperty( name="Max Depth (0 = all)",     default=0, min=0)

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "force_schedule_type")
        layout.separator(factor=0.5)
        col = layout.column(align=True)
        col.prop(self, "should_print_rates")
        col.prop(self, "should_print_description")
        col.prop(self, "should_print_each_quantity")
        col.prop(self, "should_print_summary")
        col.prop(self, "should_print_cover")
        col.prop(self, "should_print_cost_ids")
        layout.prop(self, "nested_structure_depth")

    def execute(self, context):
        if not _ensure_typst():
            self.report({"ERROR"}, "typst Python package not found. Install it in Blender's Python: pip install typst")
            return {"CANCELLED"}
        if not _ensure_ifc5d():
            self.report({"ERROR"}, "ifc5d module not available (should be bundled with Bonsai).")
            return {"CANCELLED"}

        from ifc5d.ifc5Dspreadsheet import Ifc5DPdfWriter

        ifc = _get_ifc()
        ifc_path = _get_ifc_path()
        if not ifc or not ifc_path:
            self.report({"ERROR"}, "No IFC file loaded.")
            return {"CANCELLED"}

        schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
        schedule = ifc.by_id(int(schedule_id))
        safe_name = (schedule.Name or "schedule").replace("/", "_").replace("\\", "_")
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(ifc_path)), f"{safe_name}.pdf")

        options = {
            "should_print_rates":         self.should_print_rates,
            "should_print_description":   self.should_print_description,
            "should_print_each_quantity": self.should_print_each_quantity,
            "should_print_summary":       self.should_print_summary,
            "should_print_cover":         self.should_print_cover,
            "should_print_cost_ids":      self.should_print_cost_ids,
            "nested_structure_depth":     self.nested_structure_depth,
        }

        try:
            Ifc5DPdfWriter(
                file=ifc,
                output=pdf_path,
                options=options,
                cost_schedule=schedule,
                force_schedule_type=self.force_schedule_type,
            ).write()
        except Exception as e:
            self.report({"ERROR"}, f"PDF generation failed: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved: {pdf_path}")
        _open_file(pdf_path)
        return {"FINISHED"}


import re as _re

_RA_LINE_CATS  = {'Sub-Contract', 'Labor', 'Equipment', 'Material', 'Safety'}
_RA_OVERHEAD   = 'Overhead'
_RA_PROFIT     = 'Profit'
_RA_ROUNDING   = 'Rounding'
_RA_ALL_CATS   = _RA_LINE_CATS | {_RA_OVERHEAD, _RA_PROFIT, _RA_ROUNDING}

_RA_CAT_IT = {
    'Sub-Contract': 'Opere Compiute',
    'Labor':        'Manodopera',
    'Equipment':    'Noli',
    'Material':     'Materiali',
    'Safety':       'Oneri per la Sicurezza',
}
_RA_CAT_ORDER = ['Sub-Contract', 'Labor', 'Equipment', 'Material', 'Safety']

_PCT_RE = _re.compile(r"(\d+(?:\.\d+)?)\s*%")


def has_rate_analysis(cost_item):
    """Return True if this IfcCostItem was processed by the Rate Analysis editor.

    Detection relies on ObjectType == "RATE_ANALYSIS", written by
    RA_OT_ApplyToIfc when the user applies an analysis.  This avoids false
    positives from prezzario items that happen to carry Labor/Material
    category CostValues as incidence breakdowns.
    """
    return getattr(cost_item, "ObjectType", None) == "RATE_ANALYSIS"


def _ra_read_pct(name):
    m = _PCT_RE.search(name or "")
    return float(m.group(1)) if m else 0.0


def _ra_read_ub(cv):
    ub = getattr(cv, "UnitBasis", None)
    if ub is None:
        return None, None
    try:
        vc = ub.ValueComponent
        qty = float(vc.wrappedValue if hasattr(vc, "wrappedValue") else vc)
        unit = _ifc_unit_to_str(ub.UnitComponent)
        return qty, unit
    except Exception:
        return None, None


def _ra_val(cv):
    v = cv.AppliedValue
    return float(v.wrappedValue if hasattr(v, "wrappedValue") else v) if v is not None else 0.0


def read_rate_analysis_from_ifc(file, cost_item):
    """Read rate analysis data directly from an IfcCostItem.

    Returns a dict with keys: identification, name, description, components,
    overhead_pct, profit_pct, rounding.  Returns None if the item has no
    rate-analysis CostValues.
    """
    components = []
    overhead_pct = 0.0
    profit_pct   = 0.0
    rounding     = 0.0
    found        = False
    item_unit    = ""

    cost_values = list(cost_item.CostValues or [])
    # Nested structure: one summary CV with sub-components
    if len(cost_values) == 1 and (getattr(cost_values[0], "Components", None) or []):
        summary_cv = cost_values[0]
        _, item_unit = _ra_read_ub(summary_cv)
        item_unit = item_unit if item_unit and item_unit != "1" else ""
        cost_values = list(summary_cv.Components or [])

    for cv in cost_values:
        cat = cv.Category or ""
        total = _ra_val(cv)

        if cat in _RA_LINE_CATS or cat not in _RA_ALL_CATS:
            found = True
            qty, unit = _ra_read_ub(cv)
            if qty:
                unit_price = round(total / qty, 6)
            else:
                qty, unit, unit_price = 1.0, "", total
            components.append({
                'category':    cat if cat in _RA_LINE_CATS else "",
                'description': cv.Name or "",
                'qty':         qty,
                'unit':        unit or "",
                'unit_price':  unit_price,
                'line_total':  round(total, 2),
            })
        elif cat == _RA_OVERHEAD:
            found = True
            overhead_pct = _ra_read_pct(cv.Name)
        elif cat == _RA_PROFIT:
            found = True
            profit_pct = _ra_read_pct(cv.Name)
        elif cat == _RA_ROUNDING:
            found = True
            rounding = total

    if not found:
        return None

    return {
        'identification': cost_item.Identification or "",
        'name':           cost_item.Name or "",
        'description':    cost_item.Description or "",
        'unit':           item_unit,
        'components':     components,
        'overhead_pct':   overhead_pct,
        'profit_pct':     profit_pct,
        'rounding':       rounding,
    }


def build_rate_analysis_csv(data):
    """Build the rate-analysis CSV from a dict returned by read_rate_analysis_from_ifc."""
    import io
    import csv as _csv

    by_cat = {}
    for comp in data['components']:
        cat = comp['category']
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(comp)

    ordered_cats = [c for c in _RA_CAT_ORDER if c in by_cat]
    ordered_cats += [c for c in by_cat if c not in ordered_cats]

    out = io.StringIO()
    w   = _csv.writer(out)
    w.writerow(['row_type', 'category', 'description', 'qty', 'unit', 'unit_price', 'line_total', 'pct'])

    ct = 0.0
    for cat in ordered_cats:
        cat_label = _RA_CAT_IT.get(cat, cat)
        cat_total = 0.0
        w.writerow(['CATEGORY_HEADER', cat, cat_label, '', '', '', '', ''])
        for comp in by_cat[cat]:
            lt = comp['line_total']
            cat_total += lt
            ct        += lt
            w.writerow([
                'COMPONENT', cat, comp['description'],
                f"{comp['qty']:g}", comp['unit'],
                f"{comp['unit_price']:.6g}", f"{lt:.2f}", '',
            ])
        w.writerow(['CATEGORY_SUBTOTAL', cat, cat_label, '', '', '', f"{cat_total:.2f}", ''])

    overhead_pct = data['overhead_pct']
    profit_pct   = data['profit_pct']
    rounding     = data['rounding']
    sg     = round(ct * overhead_pct / 100.0, 2)
    profit = round((ct + sg) * profit_pct / 100.0, 2)
    final  = ct + sg + profit + rounding

    w.writerow(['SUBTOTAL', '', 'Costo tecnico',   '', '', '', f"{ct:.2f}",     ''])
    w.writerow(['OVERHEAD', '', 'Spese generali',  '', '', '', f"{sg:.2f}",     f"{overhead_pct:.1f}"])
    w.writerow(['PROFIT',   '', "Utile d'impresa", '', '', '', f"{profit:.2f}", f"{profit_pct:.1f}"])
    w.writerow(['ROUNDING', '', 'Arrotondamento',  '', '', '', f"{rounding:.2f}", ''])
    w.writerow(['TOTAL',    '', 'PREZZO FINALE',   '', '', '', f"{final:.2f}",  ''])

    return out.getvalue()


def _ra_target_item(context):
    """Return (ifc_file, cost_item) from the pinned target or the active cost item."""
    ifc = _get_ifc()
    if ifc is None:
        return None, None
    wm = context.window_manager
    target_id = getattr(wm, "rate_analysis_target_ifc_id", 0)
    if target_id:
        return ifc, ifc.by_id(target_id)
    try:
        props = context.scene.BIMCostProperties
        item_id = props.active_cost_item.ifc_definition_id
        if item_id:
            return ifc, ifc.by_id(item_id)
    except Exception:
        pass
    return ifc, None


class ExportRateAnalysisToPdfOperator(bpy.types.Operator):
    """Export the active cost item's Rate Analysis to PDF (reads directly from IFC)."""
    bl_idname = "bim.export_rate_analysis_to_pdf"
    bl_label = "Export Rate Analysis to PDF"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        ifc, item = _ra_target_item(context)
        return item is not None

    def execute(self, context):
        import tempfile
        import shutil

        if not _ensure_typst():
            self.report({"ERROR"}, "typst Python package not found. Install it in Blender's Python: pip install typst")
            return {"CANCELLED"}

        ifc, cost_item = _ra_target_item(context)
        ifc_path = _get_ifc_path()
        if not ifc or cost_item is None or not ifc_path:
            self.report({"ERROR"}, "No IFC file or cost item available.")
            return {"CANCELLED"}

        data = read_rate_analysis_from_ifc(ifc, cost_item)
        if data is None:
            self.report({"WARNING"}, "No rate analysis data found on this cost item.")
            return {"CANCELLED"}

        def _safe(s):
            return (s or "").replace("/", "_").replace("\\", "_").replace(":", "_")

        safe     = f"{_safe(data['identification'])}_{_safe(data['name'])}"[:60] or "rate_analysis"
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(ifc_path)), f"{safe}_analisi.pdf")

        project_currency = ""
        monetary = ifc.by_type("IfcMonetaryUnit")
        if monetary:
            project_currency = monetary[0].Currency or ""

        def _esc(s):
            return (s or "").replace("\\", "\\\\").replace('"', "'").replace("\n", " ").replace("\r", "")

        with tempfile.TemporaryDirectory() as tmp:
            csv_file = os.path.join(tmp, "rate_analysis.csv")
            with open(csv_file, "w", encoding="utf-8", newline="") as f:
                f.write(build_rate_analysis_csv(data))

            shutil.copy(os.path.join(os.path.dirname(__file__), "typst_template_rate_analysis.typ"), tmp)

            main  = '#import "typst_template_rate_analysis.typ": *\n'
            main += "#show: project.with(\n"
            main += '  csv_path: "rate_analysis.csv",\n'
            main += f'  item_identification: "{_esc(data["identification"])}",\n'
            main += f'  item_name: "{_esc(data["name"])}",\n'
            main += f'  item_description: "{_esc(data["description"])}",\n'
            main += f'  project_currency: "{_esc(project_currency)}",\n'
            main += ")\n"

            main_path = os.path.join(tmp, "main.typ")
            with open(main_path, "w", encoding="utf-8") as f:
                f.write(main)

            try:
                import typst
                pdf_bytes = typst.compile(main_path)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
            except Exception as exc:
                self.report({"ERROR"}, f"PDF generation failed: {exc}")
                return {"CANCELLED"}

        self.report({"INFO"}, f"Saved: {pdf_path}")
        _open_file(pdf_path)
        return {"FINISHED"}


class ExportAllRateAnalysisToPdfOperator(bpy.types.Operator):
    """Export all Rate Analysis items in the active Cost Schedule to a single PDF."""
    bl_idname = "bim.export_all_rate_analysis_to_pdf"
    bl_label = "Export All Rate Analyses to PDF"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def execute(self, context):
        import tempfile
        import shutil

        if not _ensure_typst():
            self.report({"ERROR"}, "typst Python package not found.")
            return {"CANCELLED"}

        ifc = _get_ifc()
        ifc_path = _get_ifc_path()
        if not ifc or not ifc_path:
            self.report({"ERROR"}, "No IFC file loaded.")
            return {"CANCELLED"}

        schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
        schedule = ifc.by_id(int(schedule_id))

        ra_items = []

        def _collect(item):
            if has_rate_analysis(item):
                data = read_rate_analysis_from_ifc(ifc, item)
                if data:
                    ra_items.append(data)
            for rel in (item.IsNestedBy or []):
                for child in (rel.RelatedObjects or []):
                    if child.is_a("IfcCostItem"):
                        _collect(child)

        for rel in (schedule.Controls or []):
            for obj in (rel.RelatedObjects or []):
                if obj.is_a("IfcCostItem"):
                    _collect(obj)

        if not ra_items:
            self.report({"WARNING"}, "No rate analysis items found in the active schedule.")
            return {"CANCELLED"}

        project_currency = ""
        monetary = ifc.by_type("IfcMonetaryUnit")
        if monetary:
            project_currency = monetary[0].Currency or ""

        def _esc(s):
            return (s or "").replace("\\", "\\\\").replace('"', "'").replace("\n", " ").replace("\r", "")

        safe_sched = (schedule.Name or "schedule").replace("/", "_").replace("\\", "_")
        pdf_path = os.path.join(
            os.path.dirname(os.path.abspath(ifc_path)),
            f"{safe_sched}_analisi_prezzi.pdf",
        )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(
                os.path.join(os.path.dirname(__file__), "typst_template_rate_analysis.typ"),
                tmp,
            )

            lines = [
                '#import "typst_template_rate_analysis.typ": render_analysis, template_fonts\n',
                '#set page(\n',
                '  paper: "a4",\n',
                '  margin: (left: 15mm, right: 10mm, top: 20mm, bottom: 20mm),\n',
                '  numbering: "1/1",\n',
                '  number-align: end,\n',
                '  footer: context [\n',
                '    #set text(font: template_fonts, size: 7pt)\n',
                '    #grid(columns: (1fr, 1fr), align: (left, right),\n',
                '      [#datetime.today().display("[day]/[month]/[year]")],\n',
                '      [#counter(page).display("1/1", both: true)]\n',
                '    )\n',
                '  ],\n',
                ')\n',
                '#set text(font: template_fonts, size: 8pt, lang: "it")\n\n',
            ]

            for i, data in enumerate(ra_items):
                csv_name = f"ra_{i:04d}.csv"
                with open(os.path.join(tmp, csv_name), "w", encoding="utf-8", newline="") as f:
                    f.write(build_rate_analysis_csv(data))

                if i > 0:
                    lines.append('#pagebreak()\n')
                lines.append('#render_analysis(\n')
                lines.append(f'  csv_path: "{csv_name}",\n')
                lines.append(f'  item_identification: "{_esc(data["identification"])}",\n')
                lines.append(f'  item_name: "{_esc(data["name"])}",\n')
                lines.append(f'  item_description: "{_esc(data["description"])}",\n')
                lines.append(f'  project_currency: "{_esc(project_currency)}",\n')
                lines.append(')\n\n')

            main_path = os.path.join(tmp, "main.typ")
            with open(main_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            try:
                import typst
                pdf_bytes = typst.compile(main_path)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
            except Exception as exc:
                self.report({"ERROR"}, f"PDF generation failed: {exc}")
                return {"CANCELLED"}

        self.report({"INFO"}, f"Saved {len(ra_items)} analisi: {pdf_path}")
        _open_file(pdf_path)
        return {"FINISHED"}


classes = [ExportSheetsToPdfOperator, ExportScheduleToPdfOperator, ExportRateAnalysisToPdfOperator, ExportAllRateAnalysisToPdfOperator]
