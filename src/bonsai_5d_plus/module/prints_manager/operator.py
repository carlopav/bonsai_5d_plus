# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import os
import subprocess
import sys

import bpy

from ...tool.cost import ifc_unit_to_str as _ifc_unit_to_str
from ...tool.cost import parse_cost_value_ref
from ...tool.cost import PRICED_BOQ_TYPES
from ...tool.cost import hierarchy_code_map as _compute_hierarchy_map
from ...tool.cost import max_hierarchy_level as _max_hierarchy_level


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


def _augment_csv(ifc, csv_text, hierarchy_map=None):
    """Post-process the ifc5d CSV per cost item.

    - Add a "SourceRate" column (linked rate via IfcRelAssignsToControl).
    - Optionally override the "Hierarchy" column with `hierarchy_map`
      (see _compute_hierarchy_map).
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
        if hierarchy_map is not None and sid:
            row["Hierarchy"] = hierarchy_map.get(int(sid), row.get("Hierarchy", ""))
        rows.append(row)

    out = io.StringIO()
    writer = _csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _ensure_module(name):
    # Bonsai wheels path fallback
    try:
        __import__(name)
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
        __import__(name)
        return True
    except ImportError:
        return False


def _ensure_ifc5d():
    return _ensure_module("ifc5d")


def _ensure_typst():
    return _ensure_module("typst")


def _ensure_odf():
    return _ensure_module("odf")


# ESTIMATE / COSTPLAN / BUDGET are priced BoQ-like (see PRICED_BOQ_TYPES):
# they route to the bill_of_quantities template with rates, keeping their own
# type label. TENDER renders the same way (a bidder's priced BoQ) but is kept
# out of PRICED_BOQ_TYPES so it is not treated as a valid source elsewhere
# (BoQ->SoR conversion, tender generation).
_HANDLED_TYPES = (*PRICED_BOQ_TYPES, "TENDER", "UNPRICEDBILLOFQUANTITIES", "SCHEDULEOFRATES")


def _extract_schedule_csv(context, should_print_hierarchy, hierarchy_start_level, force_schedule_type):
    """Shared IFC -> CSV data extraction (ifc5d) for both the PDF and ODS exporters.

    Returns a dict with ifc, ifc_path, schedule, doc_type, csv_text, project_name,
    currency; or a dict with only "error" set when extraction fails.
    """
    import tempfile

    if not _ensure_ifc5d():
        return {"error": "ifc5d module not available (should be bundled with Bonsai)."}

    from ifc5d.ifc5Dspreadsheet import Ifc5DCsvWriter

    ifc = _get_ifc()
    ifc_path = _get_ifc_path()
    if not ifc or not ifc_path:
        return {"error": "No IFC file loaded."}

    schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
    schedule = ifc.by_id(int(schedule_id))

    if force_schedule_type == "AUTO":
        doc_type = schedule.PredefinedType
        if doc_type not in _HANDLED_TYPES:
            doc_type = "PRICEDBILLOFQUANTITIES"
    else:
        doc_type = force_schedule_type

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
            return {"error": f"Data extraction failed: {e}"}
        csv_files = [f for f in os.listdir(td) if f.lower().endswith(".csv")]
        if not csv_files:
            return {"error": "ifc5d produced no CSV for this schedule."}
        with open(os.path.join(td, csv_files[0]), encoding="utf-8") as f:
            csv_text = f.read()

    # Inject the linked Schedule-of-Rates item (IfcRelAssignsToControl) as a
    # "SourceRate" column, and override ifc5d's plain positional "Hierarchy"
    # column when requested.
    hierarchy_map = _compute_hierarchy_map(schedule, hierarchy_start_level) if should_print_hierarchy else None
    csv_text = _augment_csv(ifc, csv_text, hierarchy_map=hierarchy_map)

    return {
        "ifc": ifc,
        "ifc_path": ifc_path,
        "schedule": schedule,
        "doc_type": doc_type,
        "csv_text": csv_text,
        "project_name": project_name,
        "currency": currency,
    }


# Shared across the PDF and ODS exporters. A cost document has to be checkable
# with a calculator, so by default every quantity and money figure is rounded
# before it is summed — the total of a column is the sum of the (rounded)
# figures printed in it. Turning this off restores the raw full-precision
# arithmetic, i.e. exactly what Bonsai's own cost panel shows, which is what to
# compare against when a total needs explaining. Never writes to IFC.
_ROUNDED_VALUES_PROP = {
    "name": "Round Values Before Summing",
    "description": (
        "Round each quantity and amount before adding it up, so every total "
        "equals the sum of the figures printed above it and the document can "
        "be checked by hand. Turn off to reproduce Bonsai's full-precision "
        "figures instead. Does not modify the IFC file"
    ),
    "default": True,
}


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
            ("TENDER",                  "Tender",                     ""),
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
    should_eval_rounded_values:  bpy.props.BoolProperty(**_ROUNDED_VALUES_PROP)
    should_print_hierarchy:      bpy.props.BoolProperty(name="Hierarchy Renumbering",   default=False)
    hierarchy_start_level:       bpy.props.IntProperty(
        name="Renumber From Level",
        description=(
            "Cost hierarchy level (0 = root) from which items are renumbered. "
            "Levels above it keep their existing Identification as-is; from "
            "this level down, existing numeric Identifications are kept and "
            "continued rather than reset. 0 renumbers the whole hierarchy"
        ),
        default=0, min=0,
    )
    should_move_identification:  bpy.props.BoolProperty(
        name="Identification in Description column",
        description=(
            "For self-contained BoQs where the Identification holds the price-list code: "
            "show each cost item's Identification above its Name in the Description column, "
            "leaving the generated hierarchy code alone in the first column. "
            "Requires Hierarchy Renumbering"
        ),
        default=False,
    )
    nested_structure_depth:      bpy.props.IntProperty( name="Max Depth (0 = all)",     default=0, min=0)
    page_break_level:            bpy.props.IntProperty(
        name="Summary Cost to New Page",
        description=(
            "Start a new page before each summary cost down to this hierarchy level "
            "(0 = no page breaks / current behaviour; 1 = first level; 2 = first and "
            "second level; and so on)"
        ),
        default=0, min=0, max=9,
    )

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
        col.prop(self, "should_eval_rounded_values")
        col.prop(self, "should_print_hierarchy")
        sub = col.column(align=True)
        sub.enabled = self.should_print_hierarchy
        sub.prop(self, "hierarchy_start_level")
        if self.should_print_hierarchy:
            try:
                ifc = _get_ifc()
                schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
                max_level = _max_hierarchy_level(ifc.by_id(int(schedule_id)))
                sub.label(text=f"Deepest level in this schedule: {max_level}")
            except Exception:
                pass
        sub.prop(self, "should_move_identification")
        layout.prop(self, "nested_structure_depth")
        layout.prop(self, "page_break_level")

    def execute(self, context):
        if not _ensure_typst():
            self.report({"ERROR"}, "typst Python package not found. Install it in Blender's Python: pip install typst")
            return {"CANCELLED"}

        # ifc5d only provides the data extraction (IFC → CSV); all presentation
        # (the Typst templates) lives in this addon under typst/.
        from . import typst_render as _tr

        data = _extract_schedule_csv(
            context, self.should_print_hierarchy, self.hierarchy_start_level, self.force_schedule_type
        )
        if "error" in data:
            self.report({"ERROR"}, data["error"])
            return {"CANCELLED"}

        ifc_path = data["ifc_path"]
        schedule = data["schedule"]
        doc_type = data["doc_type"]
        csv_text = data["csv_text"]
        project_name = data["project_name"]
        currency = data["currency"]

        safe_name = (schedule.Name or "schedule").replace("/", "_").replace("\\", "_")
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(ifc_path)), f"{safe_name}.pdf")

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
        # Moving the Identification into the Description column only makes sense
        # together with the generated hierarchy code; gate it on that here too.
        move_identification = self.should_move_identification and self.should_print_hierarchy

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
                page_break_level=self.page_break_level,
                should_move_identification=move_identification,
                should_print_each_quantity=self.should_print_each_quantity,
                should_print_qty_decomposition=self.should_print_qty_decomposition,
                should_print_summary=self.should_print_summary,
                should_eval_rounded_values=self.should_eval_rounded_values,
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


class ExportScheduleToOdsOperator(bpy.types.Operator):
    """Export the active Cost Schedule to ODS with live spreadsheet formulas."""
    bl_idname = "bim.export_schedule_to_ods"
    bl_label = "Export Schedule to ODS"
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
            ("TENDER",                  "Tender",                     ""),
            ("SCHEDULEOFRATES",         "Schedule of Rates",          ""),
        ],
        default="AUTO",
    )
    should_print_rates:          bpy.props.BoolProperty(name="Show Rates",              default=True)
    should_print_description:    bpy.props.BoolProperty(name="Show Descriptions",       default=False)
    should_print_each_quantity:  bpy.props.BoolProperty(name="Show Quantity Breakdown", default=True)
    should_print_qty_decomposition: bpy.props.BoolProperty(name="Show Quantity Decomposition", default=False)
    should_print_summary:        bpy.props.BoolProperty(name="Show Summary Sheet",      default=True)
    should_eval_rounded_values:  bpy.props.BoolProperty(**_ROUNDED_VALUES_PROP)
    should_print_hierarchy:      bpy.props.BoolProperty(name="Hierarchy Renumbering",   default=False)
    hierarchy_start_level:       bpy.props.IntProperty(
        name="Renumber From Level",
        description=(
            "Cost hierarchy level (0 = root) from which items are renumbered. "
            "Levels above it keep their existing Identification as-is; from "
            "this level down, existing numeric Identifications are kept and "
            "continued rather than reset. 0 renumbers the whole hierarchy"
        ),
        default=0, min=0,
    )
    should_move_identification:  bpy.props.BoolProperty(
        name="Identification in Description column",
        description=(
            "For self-contained BoQs where the Identification holds the price-list code: "
            "show each cost item's Identification above its Name in the Description column, "
            "leaving the generated hierarchy code alone in the first column. "
            "Requires Hierarchy Renumbering"
        ),
        default=False,
    )
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
        col.prop(self, "should_eval_rounded_values")
        col.prop(self, "should_print_hierarchy")
        sub = col.column(align=True)
        sub.enabled = self.should_print_hierarchy
        sub.prop(self, "hierarchy_start_level")
        if self.should_print_hierarchy:
            try:
                ifc = _get_ifc()
                schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
                max_level = _max_hierarchy_level(ifc.by_id(int(schedule_id)))
                sub.label(text=f"Deepest level in this schedule: {max_level}")
            except Exception:
                pass
        sub.prop(self, "should_move_identification")
        layout.prop(self, "nested_structure_depth")

    def execute(self, context):
        if not _ensure_odf():
            self.report({"ERROR"}, "odfpy Python package not found. Install it in Blender's Python: pip install odfpy")
            return {"CANCELLED"}

        # ifc5d only provides the data extraction (IFC → CSV); all presentation
        # lives in this addon, in ods_render.py.
        from . import ods_render as _or

        data = _extract_schedule_csv(
            context, self.should_print_hierarchy, self.hierarchy_start_level, self.force_schedule_type
        )
        if "error" in data:
            self.report({"ERROR"}, data["error"])
            return {"CANCELLED"}

        ifc_path = data["ifc_path"]
        schedule = data["schedule"]
        doc_type = data["doc_type"]
        csv_text = data["csv_text"]
        project_name = data["project_name"]
        currency = data["currency"]

        safe_name = (schedule.Name or "schedule").replace("/", "_").replace("\\", "_")
        ods_path = os.path.join(os.path.dirname(os.path.abspath(ifc_path)), f"{safe_name}.ods")

        # Moving the Identification into the Description column only makes sense
        # together with the generated hierarchy code; gate it on that here too.
        move_identification = self.should_move_identification and self.should_print_hierarchy

        options = dict(
            doc_type=doc_type,
            should_print_rates=self.should_print_rates,
            should_print_description=self.should_print_description,
            should_print_each_quantity=self.should_print_each_quantity,
            should_print_qty_decomposition=self.should_print_qty_decomposition,
            should_print_summary=self.should_print_summary,
            should_eval_rounded_values=self.should_eval_rounded_values,
            should_print_hierarchy=self.should_print_hierarchy,
            should_move_identification=move_identification,
            title=project_name,
            schedule_name=schedule.Name or "",
            schedule_description=schedule.Description or "",
            currency=currency,
        )

        try:
            _or.compile_document(csv_text, options, ods_path)
        except Exception as e:
            self.report({"ERROR"}, f"ODS generation failed: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved: {ods_path}")
        _open_file(ods_path)
        return {"FINISHED"}


class ExportLaborCostBreakdownToPdfOperator(bpy.types.Operator):
    """Export the active Cost Schedule as a Labor Cost Breakdown (Quadro Incidenza Manodopera) PDF."""
    bl_idname = "bim.export_labor_cost_breakdown_to_pdf"
    bl_label = "Export Labor Cost Breakdown to PDF"
    bl_options = {"REGISTER"}

    should_print_description: bpy.props.BoolProperty(name="Show Descriptions",   default=False)
    should_print_cover:       bpy.props.BoolProperty(name="Show Cover Page",     default=False)
    should_print_hierarchy:   bpy.props.BoolProperty(name="Hierarchy Renumbering", default=False)
    hierarchy_start_level:    bpy.props.IntProperty(
        name="Renumber From Level",
        description=(
            "Cost hierarchy level (0 = root) from which items are renumbered. "
            "Levels above it keep their existing Identification as-is; from "
            "this level down, existing numeric Identifications are kept and "
            "continued rather than reset. 0 renumbers the whole hierarchy"
        ),
        default=0, min=0,
    )
    should_print_summary:     bpy.props.BoolProperty(name="Show Summary Page",   default=True)
    should_eval_rounded_values: bpy.props.BoolProperty(**_ROUNDED_VALUES_PROP)
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
        col.prop(self, "should_eval_rounded_values")
        col.prop(self, "should_print_hierarchy")
        sub = col.column(align=True)
        sub.enabled = self.should_print_hierarchy
        sub.prop(self, "hierarchy_start_level")
        if self.should_print_hierarchy:
            try:
                ifc = _get_ifc()
                schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
                max_level = _max_hierarchy_level(ifc.by_id(int(schedule_id)))
                sub.label(text=f"Deepest level in this schedule: {max_level}")
            except Exception:
                pass
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
        # "SourceRate" column the template renders under each item's Name, and
        # override ifc5d's plain positional "Hierarchy" column when requested.
        hierarchy_map = _compute_hierarchy_map(schedule, self.hierarchy_start_level) if self.should_print_hierarchy else None
        csv_text = _augment_csv(ifc, csv_text, hierarchy_map=hierarchy_map)

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
            should_eval_rounded_values=self.should_eval_rounded_values,
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
_RA_SAFETY_PCT = 'Safety Percentage'
_RA_OVERHEAD   = 'Overhead'
_RA_PROFIT     = 'Profit'
_RA_ROUNDING   = 'Rounding'
_RA_MARKUP_CATS = {_RA_SAFETY_PCT, _RA_OVERHEAD, _RA_PROFIT, _RA_ROUNDING}
_RA_ALL_CATS   = _RA_LINE_CATS | _RA_MARKUP_CATS

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
    """(quantity, unit) from a CostValue's UnitBasis, or (None, None).

    "1" is the dimensionless placeholder written by set_unit_basis_entity when no
    unit was chosen, so it reads back as no unit at all rather than as a symbol.
    """
    ub = getattr(cv, "UnitBasis", None)
    if ub is None:
        return None, None
    try:
        vc = ub.ValueComponent
        qty = float(vc.wrappedValue if hasattr(vc, "wrappedValue") else vc)
        unit = _ifc_unit_to_str(ub.UnitComponent)
        return qty, ("" if unit == "1" else unit)
    except Exception:
        return None, None


def _ra_val(cv):
    v = cv.AppliedValue
    return float(v.wrappedValue if hasattr(v, "wrappedValue") else v) if v is not None else 0.0


def _ra_source_info(file, cv):
    """(identification, long_description) of the price-list item a component came from.

    The identification is taken from the reference text itself, so the code still
    prints when the source item is gone; the extended description needs the entity
    and is dropped when it cannot be resolved. Free-form components carry no
    reference: their own Description text is used as the extended description.
    """
    ident, step_id = parse_cost_value_ref(cv)
    if step_id is None:
        return "", " ".join((getattr(cv, "Description", None) or "").split())
    long_description = ""
    try:
        source = file.by_id(step_id)
        if source.is_a("IfcCostItem"):
            long_description = " ".join((source.Description or "").split())
            if not ident:
                ident = source.Identification or ""
    except Exception:
        pass
    return ident, long_description


def read_rate_analysis_from_ifc(file, cost_item):
    """Read rate analysis data directly from an IfcCostItem.

    Returns a dict with keys: identification, name, description, components,
    safety_pct, overhead_pct, profit_pct, rounding.  Returns None if the item has
    no rate-analysis CostValues.

    Components carry an `apply_markup` flag read from their position: those
    written after the markup block already include safety costs, overhead and
    profit (see RA_OT_ApplyToIfc). Files written before that convention have every
    component ahead of the block, so they all come back subject to markups.
    """
    components = []
    safety_pct   = 0.0
    overhead_pct = 0.0
    profit_pct   = 0.0
    rounding     = 0.0
    found        = False
    item_unit    = ""
    past_markups = False

    cost_values = list(cost_item.CostValues or [])
    # Nested structure: one summary CV with sub-components
    if len(cost_values) == 1 and (getattr(cost_values[0], "Components", None) or []):
        summary_cv = cost_values[0]
        _, item_unit = _ra_read_ub(summary_cv)
        item_unit = item_unit or ""
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
            ident, long_description = _ra_source_info(file, cv)
            components.append({
                'category':         cat if cat in _RA_LINE_CATS else "",
                'identification':   ident,
                'description':      cv.Name or "",
                'long_description': long_description,
                'qty':              qty,
                'unit':             unit or "",
                'unit_price':       unit_price,
                'line_total':       round(total, 2),
                'apply_markup':     not past_markups,
            })
        elif cat == _RA_SAFETY_PCT:
            found = True
            past_markups = True
            safety_pct = _ra_read_pct(cv.Name)
        elif cat == _RA_OVERHEAD:
            found = True
            past_markups = True
            overhead_pct = _ra_read_pct(cv.Name)
        elif cat == _RA_PROFIT:
            found = True
            past_markups = True
            profit_pct = _ra_read_pct(cv.Name)
        elif cat == _RA_ROUNDING:
            found = True
            past_markups = True
            rounding = total

    if not found:
        return None

    return {
        'identification': cost_item.Identification or "",
        'name':           cost_item.Name or "",
        'description':    cost_item.Description or "",
        'unit':           item_unit,
        'components':     components,
        'safety_pct':     safety_pct,
        'overhead_pct':   overhead_pct,
        'profit_pct':     profit_pct,
        'rounding':       rounding,
    }


_RA_INCL_SECTION_LABEL = (
    "Voci di prezzario di riferimento già comprensive di oneri "
    "per la sicurezza, spese generali e utile d'impresa"
)
# Rendered by the template as "Subtotale <label> :".
_RA_INCL_SUBTOTAL_LABEL = "voci di prezzario di riferimento"

_RA_DESCRIPTION_FLAG_HELP = (
    "Print each component's extended description under its name: the price-list "
    "item's description for linked components, the component's own for free-form "
    "ones. Off keeps the sheet to one line per component"
)


def build_rate_analysis_csv(data, should_print_description=False):
    """Build the rate-analysis CSV from a dict returned by read_rate_analysis_from_ifc.

    Lays out the Italian "nuovo prezzo" worksheet: components grouped by category
    with their subtotals, the compounding markups, then the items that already
    include those markups listed plainly, and finally rounding and the unit price.

    `should_print_description` turns on the extended description printed under each
    component's name; it is off by default, keeping the sheet to one line per item.
    """
    import io
    import csv as _csv

    header = [
        'row_type', 'category', 'identification', 'description', 'long_description',
        'qty', 'unit', 'unit_price', 'line_total', 'pct', 'base',
    ]
    out = io.StringIO()
    w   = _csv.writer(out)
    w.writerow(header)

    def _row(cells):
        # Typst's csv() rejects short rows, so trailing columns are padded here
        # rather than spelled out at every call site.
        w.writerow(cells + [''] * (len(header) - len(cells)))

    def _component_row(comp):
        _row([
            'COMPONENT', comp['category'], comp.get('identification', ''),
            comp['description'],
            comp.get('long_description', '') if should_print_description else '',
            f"{comp['qty']:g}", comp['unit'],
            f"{comp['unit_price']:.6g}", f"{comp['line_total']:.2f}",
        ])

    def _summary_row(row_type, label, amount, pct='', base=None, unit=''):
        # `base` is the amount a percentage is taken on, printed next to it so the
        # reader can follow the compounding.
        _row([
            row_type, '', '', label, '', '', unit, '',
            f"{amount:.2f}", pct, '' if base is None else f"{base:.2f}",
        ])

    marked_up = [c for c in data['components'] if c.get('apply_markup', True)]
    inclusive = [c for c in data['components'] if not c.get('apply_markup', True)]

    by_cat = {}
    for comp in marked_up:
        by_cat.setdefault(comp['category'], []).append(comp)
    ordered_cats = [c for c in _RA_CAT_ORDER if c in by_cat]
    ordered_cats += [c for c in by_cat if c not in ordered_cats]

    ct = 0.0
    for cat in ordered_cats:
        cat_label = _RA_CAT_IT.get(cat, cat)
        cat_total = 0.0
        _row(['CATEGORY_HEADER', cat, '', cat_label])
        for comp in by_cat[cat]:
            cat_total += comp['line_total']
            ct        += comp['line_total']
            _component_row(comp)
        _row(['CATEGORY_SUBTOTAL', cat, '', cat_label, '', '', '', '', f"{cat_total:.2f}"])

    safety_pct   = data.get('safety_pct', 0.0)
    overhead_pct = data['overhead_pct']
    profit_pct   = data['profit_pct']
    rounding     = data['rounding']

    safety   = round(ct * safety_pct / 100.0, 2)
    sg       = round((ct + safety) * overhead_pct / 100.0, 2)
    profit   = round((ct + safety + sg) * profit_pct / 100.0, 2)
    subtotal = ct + safety + sg + profit
    ct_incl  = sum(c['line_total'] for c in inclusive)
    final    = subtotal + ct_incl + rounding

    _summary_row('SUBTOTAL', 'Totale tecnico', ct)
    if safety_pct:
        _summary_row('SAFETY_PCT', 'Costi della sicurezza', safety,
                     f"{safety_pct:.1f}", base=ct)
    _summary_row('OVERHEAD', 'Spese generali', sg,
                 f"{overhead_pct:.1f}", base=ct + safety)
    _summary_row('PROFIT', "Utile d'impresa", profit,
                 f"{profit_pct:.1f}", base=ct + safety + sg)
    _summary_row('SECTION_TOTAL', 'TOTALE', subtotal)

    if inclusive:
        _row(['SECTION_HEADER', '', '', _RA_INCL_SECTION_LABEL])
        for comp in inclusive:
            _component_row(comp)
        # CATEGORY_SUBTOTAL renders as "Subtotale <label> :", matching the per-category
        # subtotals above; the TOTALE that follows carries everything before rounding.
        _row(['CATEGORY_SUBTOTAL', '', '', _RA_INCL_SUBTOTAL_LABEL,
              '', '', '', '', f"{ct_incl:.2f}"])
        _summary_row('SECTION_TOTAL', 'TOTALE', subtotal + ct_incl)

    _summary_row('ROUNDING', 'Arrotondamento', rounding)
    _summary_row('TOTAL', 'PREZZO FINALE', final, unit=data.get('unit', ''))

    return out.getvalue()


def _ra_target_item(context):
    """Return (ifc_file, cost_item) from the pinned target or the active cost item."""
    ifc = _get_ifc()
    if ifc is None:
        return None, None
    editor = getattr(context.scene, "bonsai5d_cost_editor", None)
    target_id = getattr(editor, "rate_analysis_target_ifc_id", 0)
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

    should_print_description: bpy.props.BoolProperty(
        name="Show Component Descriptions",
        description=_RA_DESCRIPTION_FLAG_HELP,
        default=False,
    )

    @classmethod
    def poll(cls, context):
        ifc, item = _ra_target_item(context)
        return item is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.prop(self, "should_print_description")

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
            _tr.compile_document(
                body,
                {"rate_analysis.csv": build_rate_analysis_csv(data, self.should_print_description)},
                pdf_path,
            )
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

    should_print_description: bpy.props.BoolProperty(
        name="Show Component Descriptions",
        description=_RA_DESCRIPTION_FLAG_HELP,
        default=False,
    )

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.prop(self, "should_print_description")

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
            csvs[csv_name] = build_rate_analysis_csv(data, self.should_print_description)
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


classes = [ExportScheduleToPdfOperator, ExportScheduleToOdsOperator, ExportLaborCostBreakdownToPdfOperator, ExportRateAnalysisToPdfOperator, ExportAllRateAnalysisToPdfOperator]
