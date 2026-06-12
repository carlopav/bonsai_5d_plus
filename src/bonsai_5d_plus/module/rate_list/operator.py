# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import json
import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from . import data as _data
from .data import _do_import, _do_import_ifc, _refresh_ifc_schedules_cache, _invalidate_filter_cache
from ...tool.cost import create_cost_item, refresh_cost_ui

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


class ImportRateList(Operator, ImportHelper):
    """Import an Italian regional price list (prezzario) in XML or XPWE format."""

    bl_idname = "import.rate_list"
    bl_label = "Import Rate List"
    filename_ext = ".xml"
    filter_glob: bpy.props.StringProperty(
        default="*.xml;*.xpwe",
        options={"HIDDEN"},
        maxlen=255,
    )

    def execute(self, context):
        success = _do_import(self.filepath, context, self.report)
        return {"FINISHED"} if success else {"CANCELLED"}


class UpdateActiveCostItem(*_IfcOperatorBase):
    """Update active cost item with selected rate data."""

    bl_idname = "import.xml_rate_update_cost_item"
    bl_label = "Update active cost item"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return (
                len(getattr(context.scene, "xml_rate_list", [])) > 0
                and props.active_cost_schedule_id != 0
                and props.active_cost_item is not None
            )
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        selected_rate = context.scene.xml_rate_list[context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=selected_rate, create_new_item=False,
            combine_desc=context.scene.xml_rate_combine_desc)


class ImportRateToActiveCostSchedule(*_IfcOperatorBase):
    """Add a new cost item to the active schedule with selected rate data."""

    bl_idname = "import.xml_rate_add_cost_item"
    bl_label = "Import Rate to Active Cost Schedule"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return (
                len(getattr(context.scene, "xml_rate_list", [])) > 0
                and props.active_cost_schedule_id != 0
                and props.active_cost_item is not None
            )
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        selected_rate = context.scene.xml_rate_list[context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=selected_rate, create_new_item=True,
            combine_desc=context.scene.xml_rate_combine_desc)


class AssignRateValue(*_IfcOperatorBase):
    """Assign the selected rate as the cost value of the active cost item."""

    bl_idname = "import.xml_rate_assign_cost_value"
    bl_label = "Assign Cost Rate Value"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            if context.scene.rate_source_mode != 'IFC_SCHEDULE':
                return False
            props = context.scene.BIMCostProperties
            if str(props.active_cost_schedule_id) == context.scene.ifc_rate_source_schedule:
                return False
            if props.active_cost_schedule_id == 0 or props.active_cost_item is None:
                return False
            selected = context.scene.xml_rate_list[context.scene.xml_rate_list_active_index]
            return json.loads(selected.attributes).get("ifc_id", 0) != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        from bonsai.core import cost as cost_core
        selected = context.scene.xml_rate_list[context.scene.xml_rate_list_active_index]
        ifc_id = json.loads(selected.attributes).get("ifc_id", 0)
        file = tool.Ifc.get()
        cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        cost_rate = file.by_id(ifc_id)
        cost_core.assign_cost_value(tool.Ifc, tool.Cost, cost_item=cost_item, cost_rate=cost_rate)
        refresh_cost_ui(tool)


class CUSTOM_OT_toggle(Operator):
    bl_idname = "xml_rate_list_ui.toggle"
    bl_label = "Toggle"

    index: bpy.props.IntProperty()

    def execute(self, context):
        item = context.scene.xml_rate_list[self.index]
        item.is_expanded = not item.is_expanded
        context.scene.xml_rate_list_active_index = self.index
        _invalidate_filter_cache()
        return {"FINISHED"}


class CUSTOM_OT_collapse_to_level_0(Operator):
    bl_idname = "xml_rate_list_ui.collapse_to_level_0"
    bl_label = "Collapse to Level 0"

    def execute(self, context):
        for item in context.scene.xml_rate_list:
            if item.is_parent:
                item.is_expanded = item.level < 0
        _invalidate_filter_cache()
        return {"FINISHED"}


class CUSTOM_OT_collapse_to_level_1(Operator):
    bl_idname = "xml_rate_list_ui.collapse_to_level_1"
    bl_label = "Collapse to Level 1"

    def execute(self, context):
        for item in context.scene.xml_rate_list:
            if item.is_parent:
                item.is_expanded = item.level < 1
        _invalidate_filter_cache()
        return {"FINISHED"}


class CUSTOM_OT_expand_all(Operator):
    bl_idname = "xml_rate_list_ui.expand_all"
    bl_label = "Expand All"

    def execute(self, context):
        for item in context.scene.xml_rate_list:
            if item.is_parent:
                item.is_expanded = True
        _invalidate_filter_cache()
        return {"FINISHED"}


class IFC_OT_rate_source_refresh(Operator):
    bl_idname = "ifc_rate_source.refresh"
    bl_label = "Refresh Schedules"

    def execute(self, context):
        _refresh_ifc_schedules_cache()
        schedule_id = context.scene.ifc_rate_source_schedule
        if schedule_id and schedule_id != '__NONE__':
            _do_import_ifc(schedule_id, context)
        return {"FINISHED"}


def _fmt_duration(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _notify_popup(context, message, icon='CHECKMARK'):
    def draw(menu, _ctx):
        menu.layout.label(text=message)
    context.window_manager.popup_menu(draw, title="Ricerca semantica", icon=icon)


class BuildSearchIndex(Operator):
    """Build the search indexes for the currently loaded price list.

    The lexical (BM25) index is instant. The embedding index needs Ollama
    with the bge-m3 model ('ollama pull bge-m3'); it is built in the
    background while Blender stays usable (ESC to cancel) and cached on disk"""

    bl_idname = "rate_list.build_search_index"
    bl_label = "Semantic Search"

    _timer = None
    _job = None

    @classmethod
    def poll(cls, context):
        return len(getattr(context.scene, "xml_rate_list", [])) > 0

    def execute(self, context):
        from ...core import semantic_search as _ss
        from ...core import embedding_search as _es

        if _es.active_job() is not None:
            self.report({'WARNING'}, "Indicizzazione già in corso")
            return {'CANCELLED'}

        rates = [json.loads(item.attributes) for item in context.scene.xml_rate_list]
        _ss.build_index(rates, key=_data._current_search_key)

        if not _es.is_available():
            self.report(
                {'INFO'},
                "Indice lessicale creato. Per la ricerca semantica avvia Ollama, "
                "esegui 'ollama pull bge-m3' e ripremi il pulsante",
            )
            return {'FINISHED'}

        self._job = _es.build_index_async(rates, key=_data._current_search_key)
        if self._job is None:
            self.report({'WARNING'}, "Impossibile avviare l'indicizzazione embeddings")
            return {'FINISHED'}

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.25, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        job = self._job

        if event.type == 'ESC' and not job.finished:
            job.cancel()
            return {'PASS_THROUGH'}  # keep waiting for the worker to stop

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        if not job.finished:
            pct = job.done * 100 // job.total if job.total else 0
            eta = job.eta
            text = (
                f"Indicizzazione embeddings: {job.done}/{job.total} ({pct}%) — "
                f"trascorso {_fmt_duration(job.elapsed)}"
            )
            if eta is not None:
                text += f", restano ~{_fmt_duration(eta)}"
            text += " — ESC per annullare"
            context.workspace.status_text_set(text)
            _data._redraw_view3d_ui()
            return {'PASS_THROUGH'}

        # Worker finished (success, error or cancelled)
        self._cleanup(context)
        _data._redraw_view3d_ui()
        if job.error:
            self.report({'WARNING'}, f"Indice embeddings non creato: {job.error}")
            _notify_popup(context, f"Errore: {job.error}", icon='ERROR')
            return {'CANCELLED'}
        if job.cancelled:
            self.report({'INFO'}, "Indicizzazione annullata")
            _notify_popup(context, "Indicizzazione annullata", icon='CANCEL')
            return {'CANCELLED'}
        msg = f"Indice creato in {_fmt_duration(job.elapsed)} ({job.total} voci)"
        self.report({'INFO'}, msg)
        _notify_popup(context, msg)
        return {'FINISHED'}

    def _cleanup(self, context):
        context.workspace.status_text_set(None)
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


classes = [
    ImportRateList,
    UpdateActiveCostItem,
    ImportRateToActiveCostSchedule,
    AssignRateValue,
    CUSTOM_OT_toggle,
    CUSTOM_OT_collapse_to_level_0,
    CUSTOM_OT_collapse_to_level_1,
    CUSTOM_OT_expand_all,
    IFC_OT_rate_source_refresh,
    BuildSearchIndex,
]
