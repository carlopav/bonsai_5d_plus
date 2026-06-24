# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import os
import subprocess
import sys

import bpy

from ...tool.cost import ifc_unit_to_str as _ifc_unit_to_str
from ...tool.cost import PRICED_BOQ_TYPES


def _open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


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


def _rate_controller(cost_item):
    """The Schedule-of-Rates cost item controlling this one, via IfcRelAssignsToControl."""
    for rel in (cost_item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl"):
            ctrl = rel.RelatingControl
            if ctrl.is_a("IfcCostItem"):
                return ctrl
    return None


def _schedule_of(cost_item):
    """The IfcCostSchedule a cost item belongs to (walks up the nesting)."""
    for rel in (cost_item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl") and rel.RelatingControl.is_a("IfcCostSchedule"):
            return rel.RelatingControl
    for rel in (cost_item.Nests or []):
        return _schedule_of(rel.RelatingObject)
    return None


def _source_rate_label(ifc, cost_item):
    """Label of the linked price-list item, or "" if none.

    Format: "<ScheduleOfRates Name> - <control Identification>". The control's
    Name is intentionally omitted to keep the label short (single line).
    """
    ctrl = _rate_controller(cost_item)
    if ctrl is None:
        return ""
    sor = _schedule_of(ctrl)
    sor_name = (sor.Name or "") if sor is not None else ""
    ident = ctrl.Identification or ""
    if sor_name and ident:
        return f"{sor_name} - [{ident}]"
    if ident:
        return f"[{ident}]"
    return sor_name


def _augment_csv(ifc, csv_text):
    """Post-process the ifc5d CSV per cost item.

    - Add a "SourceRate" column (linked rate via IfcRelAssignsToControl).
    """
    import csv as _csv
    import io

    reader = _csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        return csv_text
    fieldnames = list(reader.fieldnames)
    if "SourceRate" not in fieldnames:
        fieldnames.append("SourceRate")

    rows = []
    for row in reader:
        label = ""
        sid = row.get("Id", "")
        item = None
        if sid:
            try:
                item = ifc.by_id(int(sid))
            except Exception:
                item = None
        if item is not None:
            try:
                label = _source_rate_label(ifc, item)
            except Exception:
                label = ""
        row["SourceRate"] = label
        rows.append(row)

    out = io.StringIO()
    writer = _csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


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
            ("ESTIMATE",                "Estimate",                   ""),
            ("COSTPLAN",                "Cost Plan",                  ""),
            ("BUDGET",                  "Budget",                     ""),
            ("SCHEDULEOFRATES",         "Schedule of Rates",          ""),
        ],
        default="AUTO",
    )
    should_print_rates:          bpy.props.BoolProperty(name="Show Rates",              default=True)
    should_print_description:    bpy.props.BoolProperty(name="Show Descriptions",       default=False)
    should_print_each_quantity:  bpy.props.BoolProperty(name="Show Quantity Breakdown", default=True)
    should_print_qty_decomposition: bpy.props.BoolProperty(name="Show Quantity Decomposition", default=False)
    should_print_summary:        bpy.props.BoolProperty(name="Show Summary Page",       default=True)
    should_print_cover:          bpy.props.BoolProperty(name="Show Cover Page",         default=False)
    should_print_hierarchy:      bpy.props.BoolProperty(name="Hierarchy Renumbering",   default=False)
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
        col.prop(self, "should_print_qty_decomposition")
        col.prop(self, "should_print_summary")
        col.prop(self, "should_print_cover")
        col.prop(self, "should_print_hierarchy")
        layout.prop(self, "nested_structure_depth")

    # ESTIMATE / COSTPLAN are priced BoQ-like (see PRICED_BOQ_TYPES): they route
    # to the bill_of_quantities template with rates, keeping their own type label.
    _HANDLED_TYPES = (*PRICED_BOQ_TYPES, "UNPRICEDBILLOFQUANTITIES", "SCHEDULEOFRATES")

    def execute(self, context):
        import tempfile

        if not _ensure_typst():
            self.report({"ERROR"}, "typst Python package not found. Install it in Blender's Python: pip install typst")
            return {"CANCELLED"}
        if not _ensure_ifc5d():
            self.report({"ERROR"}, "ifc5d module not available (should be bundled with Bonsai).")
            return {"CANCELLED"}

        # ifc5d only provides the data extraction (IFC → CSV); all presentation
        # (the Typst templates) lives in this addon under typst/.
        from ifc5d.ifc5Dspreadsheet import Ifc5DCsvWriter
        from . import typst_render as _tr

        ifc = _get_ifc()
        ifc_path = _get_ifc_path()
        if not ifc or not ifc_path:
            self.report({"ERROR"}, "No IFC file loaded.")
            return {"CANCELLED"}

        schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
        schedule = ifc.by_id(int(schedule_id))
        safe_name = (schedule.Name or "schedule").replace("/", "_").replace("\\", "_")
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(ifc_path)), f"{safe_name}.pdf")

        # Resolve the effective document type.
        if self.force_schedule_type == "AUTO":
            doc_type = schedule.PredefinedType
            if doc_type not in self._HANDLED_TYPES:
                doc_type = "PRICEDBILLOFQUANTITIES"
        else:
            doc_type = self.force_schedule_type

        project_name = ""
        projects = ifc.by_type("IfcProject")
        if projects:
            project_name = projects[0].Name or ""
        currency = ""
        monetary = ifc.by_type("IfcMonetaryUnit")
        if monetary:
            currency = monetary[0].Currency or ""

        # Extract the CSV via ifc5d into a temp dir, then read it back.
        with tempfile.TemporaryDirectory() as td:
            try:
                Ifc5DCsvWriter(file=ifc, output=td, cost_schedule=schedule).write()
            except Exception as e:
                self.report({"ERROR"}, f"Data extraction failed: {e}")
                return {"CANCELLED"}
            csv_files = [f for f in os.listdir(td) if f.lower().endswith(".csv")]
            if not csv_files:
                self.report({"ERROR"}, "ifc5d produced no CSV for this schedule.")
                return {"CANCELLED"}
            with open(os.path.join(td, csv_files[0]), encoding="utf-8") as f:
                csv_text = f.read()

        # Inject the linked Schedule-of-Rates item (IfcRelAssignsToControl) as a
        # "SourceRate" column the templates render under each item's Name.
        csv_text = _augment_csv(ifc, csv_text)

        common = dict(
            schedule_path="/schedule.csv",
            title=project_name,
            schedule_name=schedule.Name or "",
            schedule_description=schedule.Description or "",
            schedule_type=doc_type,
            project_currency=currency,
            should_print_cover=self.should_print_cover,
            should_print_hierarchy=self.should_print_hierarchy,
            should_print_description=self.should_print_description,
        )

        if doc_type == "SCHEDULEOFRATES":
            body = _tr.show_with(
                "schedule_of_rates.typ",
                should_print_rates=self.should_print_rates,
                **common,
            )
        else:
            body = _tr.show_with(
                "bill_of_quantities.typ",
                nested_structure_depth=self.nested_structure_depth,
                should_print_each_quantity=self.should_print_each_quantity,
                should_print_qty_decomposition=self.should_print_qty_decomposition,
                should_print_summary=self.should_print_summary,
                # Unpriced BoQ hides the rate/total columns.
                should_print_rates=self.should_print_rates and doc_type != "UNPRICEDBILLOFQUANTITIES",
                **common,
            )

        try:
            _tr.compile_document(body, {"schedule.csv": csv_text}, pdf_path)
        except Exception as e:
            self.report({"ERROR"}, f"PDF generation failed: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved: {pdf_path}")
        _open_file(pdf_path)
        return {"FINISHED"}


class ExportLaborCostBreakdownToPdfOperator(bpy.types.Operator):
    """Export the active Cost Schedule as a Labor Cost Breakdown (Quadro Incidenza Manodopera) PDF."""
    bl_idname = "bim.export_labor_cost_breakdown_to_pdf"
    bl_label = "Export Labor Cost Breakdown to PDF"
    bl_options = {"REGISTER"}

    should_print_description: bpy.props.BoolProperty(name="Show Descriptions",   default=False)
    should_print_cover:       bpy.props.BoolProperty(name="Show Cover Page",     default=False)
    should_print_hierarchy:   bpy.props.BoolProperty(name="Hierarchy Renumbering", default=False)
    should_print_summary:     bpy.props.BoolProperty(name="Show Summary Page",   default=True)
    nested_structure_depth:   bpy.props.IntProperty( name="Max Depth (0 = all)", default=0, min=0)

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
        col = layout.column(align=True)
        col.prop(self, "should_print_description")
        col.prop(self, "should_print_cover")
        col.prop(self, "should_print_hierarchy")
        col.prop(self, "should_print_summary")
        layout.prop(self, "nested_structure_depth")

    def execute(self, context):
        import tempfile

        if not _ensure_typst():
            self.report({"ERROR"}, "typst Python package not found. Install it in Blender's Python: pip install typst")
            return {"CANCELLED"}
        if not _ensure_ifc5d():
            self.report({"ERROR"}, "ifc5d module not available (should be bundled with Bonsai).")
            return {"CANCELLED"}

        # Same ifc5d extraction as the Bill of Quantities; the labor figure is
        # the "Labor Cost" category column, rolled up by hierarchy in the template.
        from ifc5d.ifc5Dspreadsheet import Ifc5DCsvWriter
        from . import typst_render as _tr

        ifc = _get_ifc()
        ifc_path = _get_ifc_path()
        if not ifc or not ifc_path:
            self.report({"ERROR"}, "No IFC file loaded.")
            return {"CANCELLED"}

        schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
        schedule = ifc.by_id(int(schedule_id))
        safe_name = (schedule.Name or "schedule").replace("/", "_").replace("\\", "_")
        pdf_path = os.path.join(
            os.path.dirname(os.path.abspath(ifc_path)),
            f"{safe_name}_incidenza_manodopera.pdf",
        )

        project_name = ""
        projects = ifc.by_type("IfcProject")
        if projects:
            project_name = projects[0].Name or ""
        currency = ""
        monetary = ifc.by_type("IfcMonetaryUnit")
        if monetary:
            currency = monetary[0].Currency or ""

        with tempfile.TemporaryDirectory() as td:
            try:
                Ifc5DCsvWriter(file=ifc, output=td, cost_schedule=schedule).write()
            except Exception as e:
                self.report({"ERROR"}, f"Data extraction failed: {e}")
                return {"CANCELLED"}
            csv_files = [f for f in os.listdir(td) if f.lower().endswith(".csv")]
            if not csv_files:
                self.report({"ERROR"}, "ifc5d produced no CSV for this schedule.")
                return {"CANCELLED"}
            with open(os.path.join(td, csv_files[0]), encoding="utf-8") as f:
                csv_text = f.read()

        # Inject the linked Schedule-of-Rates item (IfcRelAssignsToControl) as a
        # "SourceRate" column the template renders under each item's Name.
        csv_text = _augment_csv(ifc, csv_text)

        body = _tr.show_with(
            "labor_cost_breakdown.typ",
            schedule_path="/schedule.csv",
            title=project_name,
            schedule_name=schedule.Name or "",
            schedule_description=schedule.Description or "",
            schedule_type="LABORCOSTBREAKDOWN",
            project_currency=currency,
            nested_structure_depth=self.nested_structure_depth,
            should_print_cover=self.should_print_cover,
            should_print_hierarchy=self.should_print_hierarchy,
            should_print_description=self.should_print_description,
            should_print_summary=self.should_print_summary,
        )

        try:
            _tr.compile_document(body, {"schedule.csv": csv_text}, pdf_path)
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
        from . import typst_render as _tr

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

        body = _tr.show_with(
            "rate_analysis.typ",
            csv_path="/rate_analysis.csv",
            item_identification=data["identification"],
            item_name=data["name"],
            item_description=data["description"],
            project_currency=project_currency,
        )
        try:
            _tr.compile_document(body, {"rate_analysis.csv": build_rate_analysis_csv(data)}, pdf_path)
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
        from . import typst_render as _tr

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

        safe_sched = (schedule.Name or "schedule").replace("/", "_").replace("\\", "_")
        pdf_path = os.path.join(
            os.path.dirname(os.path.abspath(ifc_path)),
            f"{safe_sched}_analisi_prezzi.pdf",
        )

        body = (
            '#import "typst/common.typ": template_fonts\n'
            '#import "typst/rate_analysis.typ": render_analysis\n'
            '#set page(\n'
            '  paper: "a4",\n'
            '  margin: (left: 15mm, right: 10mm, top: 20mm, bottom: 20mm),\n'
            '  numbering: "1/1",\n'
            '  number-align: end,\n'
            '  footer: context [\n'
            '    #set text(font: template_fonts, size: 7pt)\n'
            '    #grid(columns: (1fr, 1fr), align: (left, right),\n'
            '      [#datetime.today().display("[day]/[month]/[year]")],\n'
            '      [#counter(page).display("1/1", both: true)]\n'
            '    )\n'
            '  ],\n'
            ')\n'
            '#set text(font: template_fonts, size: 8pt, lang: "it")\n\n'
        )

        csvs = {}
        for i, data in enumerate(ra_items):
            csv_name = f"ra_{i:04d}.csv"
            csvs[csv_name] = build_rate_analysis_csv(data)
            if i > 0:
                body += '#pagebreak()\n'
            body += (
                '#render_analysis(\n'
                f'  csv_path: "/{csv_name}",\n'
                f'  item_identification: "{_tr.esc(data["identification"])}",\n'
                f'  item_name: "{_tr.esc(data["name"])}",\n'
                f'  item_description: "{_tr.esc(data["description"])}",\n'
                f'  project_currency: "{_tr.esc(project_currency)}",\n'
                ')\n\n'
            )

        try:
            _tr.compile_document(body, csvs, pdf_path)
        except Exception as exc:
            self.report({"ERROR"}, f"PDF generation failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved {len(ra_items)} analisi: {pdf_path}")
        _open_file(pdf_path)
        return {"FINISHED"}


classes = [ExportScheduleToPdfOperator, ExportLaborCostBreakdownToPdfOperator, ExportRateAnalysisToPdfOperator, ExportAllRateAnalysisToPdfOperator]
