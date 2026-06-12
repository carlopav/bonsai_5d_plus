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
                '#import "typst_template_rate_analysis.typ": render_analysis, ra-page-header, ra-page-footer, template_fonts\n',
                '#let _cur-id   = state("_cur-id",   "")\n',
                '#let _cur-name = state("_cur-name", "")\n',
                '#set page(\n',
                '  paper: "a4",\n',
                '  margin: (left: 15mm, right: 10mm, top: 22mm, bottom: 20mm),\n',
                '  numbering: "1/1",\n',
                '  number-align: end,\n',
                '  header: context [#ra-page-header(_cur-id.get(), _cur-name.get())],\n',
                '  footer: ra-page-footer(),\n',
                ')\n',
                '#set text(font: template_fonts, size: 8pt, lang: "it")\n\n',
            ]

            for i, data in enumerate(ra_items):
                csv_name = f"ra_{i:04d}.csv"
                with open(os.path.join(tmp, csv_name), "w", encoding="utf-8", newline="") as f:
                    f.write(build_rate_analysis_csv(data))

                if i > 0:
                    lines.append('#pagebreak()\n')
                lines.append(f'#_cur-id.update("{_esc(data["identification"])}")\n')
                lines.append(f'#_cur-name.update("{_esc(data["name"])}")\n')
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


# ---------------------------------------------------------------------------
# Price comparison helpers
# ---------------------------------------------------------------------------

def _collect_leaf_items(item):
    """Yield all leaf IfcCostItem descendants (items with no IfcCostItem children)."""
    children = [
        obj for rel in (item.IsNestedBy or [])
        for obj in (rel.RelatedObjects or [])
        if obj.is_a("IfcCostItem")
    ]
    if not children:
        yield item
    else:
        for child in children:
            yield from _collect_leaf_items(child)


def _item_unit_price(item):
    cvs = list(item.CostValues or [])
    if not cvs:
        return None
    v = cvs[0].AppliedValue
    return float(v.wrappedValue if hasattr(v, "wrappedValue") else v) if v is not None else None


def _effective_unit_price(item):
    """Unit price: direct CostValue first, then follow IfcRelAssignsToControl to a rate source."""
    price = _item_unit_price(item)
    if price is not None:
        return price
    for rel in (item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl"):
            ctrl = rel.RelatingControl
            if ctrl.is_a("IfcCostItem"):
                price = _item_unit_price(ctrl)
                if price is not None:
                    return price
    return None


def _item_unit(item):
    cvs = list(item.CostValues or [])
    if not cvs:
        return ""
    ub = getattr(cvs[0], "UnitBasis", None)
    if ub is None:
        return ""
    u = _ifc_unit_to_str(ub.UnitComponent)
    return u if u != "1" else ""


def _item_quantity(item):
    total = 0.0
    for q in (item.CostQuantities or []):
        for attr in ("AreaValue", "VolumeValue", "LengthValue", "CountValue",
                     "WeightValue", "TimeValue", "NumberValue"):
            v = getattr(q, attr, None)
            if v is not None:
                total += float(v)
                break
    return total


def read_boq_comparison(ifc, schedules):
    """Align leaf items across N schedules for the price comparison table.

    schedules[0] is the base (provides ordering).  All schedules contribute prices.
    Matching key: normalised (Identification, Name, Description).
    Items present with the same Identification but differing Name/Description are
    emitted as separate 'divergent' sub-rows immediately after the 'main' row.

    Returns a list of row dicts:
      type            'aligned' | 'main' | 'divergent'
      progressive     int (None for divergent sub-rows)
      identification  str (blank for divergent sub-rows)
      name            str
      unit            str
      quantity        float
      unit_prices     [float|None, ...]  one entry per schedule
    """

    def _norm(s):
        return (s or "").strip().lower()

    # Build per-schedule index: identification → list of entry dicts
    sched_data = []
    for sched in schedules:
        data = {}
        for rel in (sched.Controls or []):
            for root in (rel.RelatedObjects or []):
                if root.is_a("IfcCostItem"):
                    for leaf in _collect_leaf_items(root):
                        ident = (leaf.Identification or "").strip()
                        entry = {
                            'name':        (leaf.Name or "").strip(),
                            'description': (leaf.Description or "").strip(),
                            'unit':        _item_unit(leaf),
                            'quantity':    _item_quantity(leaf),
                            'price':       _effective_unit_price(leaf),
                        }
                        data.setdefault(ident, []).append(entry)
        sched_data.append(data)

    # Ordered list of identifications: base schedule first, then others
    seen = set()
    idents_ordered = []
    for rel in (schedules[0].Controls or []):
        for root in (rel.RelatedObjects or []):
            if root.is_a("IfcCostItem"):
                for leaf in _collect_leaf_items(root):
                    ident = (leaf.Identification or "").strip()
                    if ident not in seen:
                        seen.add(ident)
                        idents_ordered.append(ident)
    for si in range(1, len(schedules)):
        for ident in sched_data[si]:
            if ident not in seen:
                seen.add(ident)
                idents_ordered.append(ident)

    rows = []
    progressive = 0

    for ident in idents_ordered:
        # Collect unique (norm_name, norm_desc) variants across all schedules
        variants = {}  # (norm_name, norm_desc) → {display_name, display_desc, {si: entry}}
        for si, data in enumerate(sched_data):
            for entry in data.get(ident, []):
                key = (_norm(entry['name']), _norm(entry['description']))
                if key not in variants:
                    variants[key] = {
                        'display_name': entry['name'],
                        'display_desc': entry['description'],
                        'by_sched':     {},
                    }
                variants[key]['by_sched'][si] = entry

        # Sort: base schedule variant first
        sorted_variants = sorted(
            variants.items(),
            key=lambda kv: 0 if 0 in kv[1]['by_sched'] else 1,
        )

        n_variants = len(sorted_variants)
        is_first = True

        for (norm_name, norm_desc), vinfo in sorted_variants:
            prices = []
            unit = ""
            quantity = 0.0
            for si in range(len(schedules)):
                entry = vinfo['by_sched'].get(si)
                if entry:
                    prices.append(entry['price'])
                    if not unit:
                        unit = entry['unit']
                    if not quantity:
                        quantity = entry['quantity']
                else:
                    prices.append(None)

            if is_first:
                progressive += 1
                row_type = 'aligned' if n_variants == 1 else 'main'
            else:
                row_type = 'divergent'

            rows.append({
                'type':           row_type,
                'progressive':    progressive if is_first else None,
                'identification': ident if is_first else "",
                'name':           vinfo['display_name'],
                'unit':           unit,
                'quantity':       quantity,
                'unit_prices':    prices,
            })
            is_first = False

    return rows


def _build_price_comparison_typst(base_name, schedule_names, rows, currency):
    """Generate a complete Typst document for the price comparison table.

    schedule_names: names of ALL schedules (base first).
    rows: output of read_boq_comparison().
    """

    def _te(s):
        return (s or "").replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("#", "\\#")

    n = len(schedule_names)
    # Fixed cols: N(7) Codice(28) Desc(1fr) UM(10) Qty(18); per schedule: PU(20) Tot(25)
    col_defs = "7mm, 28mm, 1fr, 10mm, 18mm" + (", 20mm, 25mm" * n)

    # Registro-style stroke: heavier frame, thin interior verticals
    stroke_decl = (
        "  stroke: (x, y) => ("
        "left: if x == 0 { 1pt } else { 0.25pt }, "
        "right: 1pt, top: 0.5pt, bottom: 0.5pt),"
    )

    # Header row 1: 5 fixed cells (rowspan 2) + n schedule name cells (colspan 2)
    h1_fill = "gray.transparentize(75%)"
    h1 = (
        f"    table.cell(rowspan: 2, align: center + horizon, fill: {h1_fill})[#text(size: 7pt, weight: \"bold\")[N.]],\n"
        f"    table.cell(rowspan: 2, align: center + horizon, fill: {h1_fill})[#text(size: 7pt, weight: \"bold\")[Codice]],\n"
        f"    table.cell(rowspan: 2, align: center + horizon, fill: {h1_fill})[#text(size: 7pt, weight: \"bold\")[Descrizione]],\n"
        f"    table.cell(rowspan: 2, align: center + horizon, fill: {h1_fill})[#text(size: 7pt, weight: \"bold\")[U.M.]],\n"
        f"    table.cell(rowspan: 2, align: right + horizon, fill: {h1_fill})[#text(size: 7pt, weight: \"bold\")[Qtà]],\n"
    )
    for name in schedule_names:
        h1 += f"    table.cell(colspan: 2, align: center, fill: {h1_fill})[#text(size: 7pt, weight: \"bold\")[{_te(name)}]],\n"

    # Header row 2: PU + Totale subheadings
    h2_fill = "gray.transparentize(88%)"
    h2 = ""
    for _ in schedule_names:
        h2 += f"    table.cell(align: right, fill: {h2_fill})[#text(size: 6.5pt)[P.U.]],\n"
        h2 += f"    table.cell(align: right, fill: {h2_fill})[#text(size: 6.5pt)[Totale]],\n"

    # Data rows
    data_rows = ""
    for row in rows:
        is_div  = row['type'] == 'divergent'
        fill    = "fill: gray.transparentize(93%), " if is_div else ""
        txt     = "#text(size: 7pt, style: \"italic\")" if is_div else "#text(size: 7pt)"

        prog    = str(row['progressive']) if row['progressive'] is not None else ""
        qty     = row['quantity']
        qty_str = f"{qty:g}" if qty else "—"

        r = (
            f"  table.cell(align: center, {fill})[{txt}[{_te(prog)}]],\n"
            f"  table.cell({fill})[{txt}[{_te(row['identification'])}]],\n"
            f"  table.cell({fill})[{txt}[{_te(row['name'])}]],\n"
            f"  table.cell(align: center, {fill})[{txt}[{_te(row['unit'])}]],\n"
            f"  table.cell(align: right, {fill})[{txt}[{qty_str}]],\n"
        )
        for price in row['unit_prices']:
            if price is not None:
                total = price * qty if qty else 0.0
                r += f"  table.cell(align: right, {fill})[{txt}[{price:.2f}]],\n"
                r += f"  table.cell(align: right, {fill})[{txt}[{total:.2f}]],\n"
            else:
                r += f"  table.cell(align: center, {fill})[—],\n"
                r += f"  table.cell(align: center, {fill})[—],\n"
        data_rows += r + "\n"

    # Totals row — exclude divergent sub-rows to avoid double counting
    tot_fill = "gray.transparentize(75%)"
    totals = f"  table.cell(colspan: 5, align: right, fill: {tot_fill})[#strong[Totale]],\n"
    for si in range(n):
        s = sum(
            (row['unit_prices'][si] or 0.0) * row['quantity']
            for row in rows
            if row['type'] != 'divergent' and row['unit_prices'][si] is not None
        )
        totals += f"  table.cell(colspan: 2, align: right, fill: {tot_fill})[#strong[{s:.2f}]],\n"

    cur = _te(currency) or "EUR"
    return f"""#import "typst_template_rate_analysis.typ": template_fonts, ra-page-footer, _stroke_heavy, _stroke_border

#set page(
  paper: "a4",
  flipped: true,
  margin: (x: 15mm, top: 20mm, bottom: 20mm),
  numbering: "1/1",
  number-align: end,
  header: [
    #set text(font: template_fonts, size: 7pt, lang: "it")
    #text(weight: "bold")[QUADRO DI RAFFRONTO PREZZI] #h(1fr) Base: {_te(base_name)}
    #v(-0.5mm)
    #line(length: 100%, stroke: _stroke_heavy)
  ],
  footer: ra-page-footer(),
)
#set text(font: template_fonts, size: 8pt, lang: "it")

#table(
  columns: ({col_defs}),
{stroke_decl}
  inset: (x: 1.5mm, y: 1.5mm),
  table.header(
{h1}
{h2}
  ),
{data_rows}
{totals}
)
"""


class COMP_OT_RefreshSchedules(bpy.types.Operator):
    """Refresh the schedule list from the current IFC project."""
    bl_idname = "comparison.refresh_schedules"
    bl_label = "Refresh Schedules"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _get_ifc() is not None

    def execute(self, context):
        ifc = _get_ifc()
        wm = context.window_manager
        wm.comparison_schedules.clear()

        schedules = list(ifc.by_type("IfcCostSchedule"))
        # Auto-detect base: prefer first BoQ
        base_id = None
        for s in schedules:
            if s.PredefinedType in ("PRICEDBILLOFQUANTITIES", "UNPRICEDBILLOFQUANTITIES"):
                base_id = s.id()
                break

        for s in schedules:
            item = wm.comparison_schedules.add()
            item.schedule_id = s.id()
            item.name = s.Name or f"#{s.id()}"
            item.predefined_type = s.PredefinedType or ""
            item.is_base = (s.id() == base_id)
            item.enabled = True

        self.report({"INFO"}, f"{len(schedules)} schedule(s) found.")
        return {"FINISHED"}


class COMP_OT_SetBase(bpy.types.Operator):
    """Set this schedule as the base (provides quantities)."""
    bl_idname = "comparison.set_base"
    bl_label = "Set as Base"
    bl_options = {"REGISTER"}

    schedule_id: bpy.props.IntProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        for item in context.window_manager.comparison_schedules:
            item.is_base = (item.schedule_id == self.schedule_id)
        return {"FINISHED"}


class COMP_OT_ExportPriceComparison(bpy.types.Operator):
    """Export a price comparison table to PDF (landscape A4)."""
    bl_idname = "comparison.export_price_comparison"
    bl_label = "Export Price Comparison to PDF"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        schedules = wm.comparison_schedules
        has_base = any(s.is_base for s in schedules)
        has_comp = any(s.enabled and not s.is_base for s in schedules)
        return has_base and has_comp

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

        wm = context.window_manager
        base_entry = next((s for s in wm.comparison_schedules if s.is_base), None)
        if not base_entry:
            self.report({"ERROR"}, "Select a base schedule.")
            return {"CANCELLED"}

        # All enabled schedules: base first, then the rest in list order
        ordered_entries = [base_entry] + [
            s for s in wm.comparison_schedules if s.enabled and not s.is_base
        ]
        if len(ordered_entries) < 2:
            self.report({"ERROR"}, "Enable at least one comparison schedule.")
            return {"CANCELLED"}

        schedules      = [ifc.by_id(e.schedule_id) for e in ordered_entries]
        schedule_names = [e.name for e in ordered_entries]

        rows = read_boq_comparison(ifc, schedules)
        if not rows:
            self.report({"WARNING"}, "No items found in base schedule.")
            return {"CANCELLED"}

        currency = ""
        monetary = ifc.by_type("IfcMonetaryUnit")
        if monetary:
            currency = monetary[0].Currency or ""

        typ_content = _build_price_comparison_typst(
            base_name=base_entry.name,
            schedule_names=schedule_names,
            rows=rows,
            currency=currency,
        )

        safe = (base_entry.name).replace("/", "_").replace("\\", "_")
        pdf_path = os.path.join(
            os.path.dirname(os.path.abspath(ifc_path)),
            f"{safe}_raffronto_prezzi.pdf",
        )

        template_src = os.path.join(os.path.dirname(__file__), "typst_template_rate_analysis.typ")
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(template_src, tmp)
            main_path = os.path.join(tmp, "main.typ")
            with open(main_path, "w", encoding="utf-8") as f:
                f.write(typ_content)
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


classes = [ExportSheetsToPdfOperator, ExportScheduleToPdfOperator, ExportRateAnalysisToPdfOperator, ExportAllRateAnalysisToPdfOperator, COMP_OT_RefreshSchedules, COMP_OT_SetBase, COMP_OT_ExportPriceComparison]
