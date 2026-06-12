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


class LLMSuggestRates(Operator):
    """Suggest price list items for the typed description using local Ollama LLM."""

    bl_idname = "rate_list.llm_suggest"
    bl_label = "AI Suggest"

    @classmethod
    def poll(cls, context):
        return len(getattr(context.scene, "xml_rate_list", [])) > 0

    def execute(self, context):
        from ...core import semantic_search as _ss
        from ...core import llm_search as _llm

        query = context.scene.xml_llm_query.strip()
        if not query:
            self.report({'WARNING'}, "Inserisci una descrizione della lavorazione")
            return {'CANCELLED'}

        if not _llm.is_available():
            self.report({'ERROR'}, "Ollama non raggiungibile su localhost:11434")
            return {'CANCELLED'}

        context.scene.xml_llm_status = "Ricerca in corso..."
        context.scene.xml_llm_results.clear()

        # Step 1: TF-IDF candidates
        if not _ss.is_ready():
            self.report({'WARNING'}, "Indicizza prima il prezzario con il pulsante Semantic Search")
            return {'CANCELLED'}

        tfidf_hits = _ss.search(query, n=_llm.CANDIDATES_N)
        rate_list  = context.scene.xml_rate_list
        candidates = []
        for rate_idx, _ in tfidf_hits:
            attrib = json.loads(rate_list[rate_idx].attributes)
            attrib['_rate_idx'] = rate_idx
            candidates.append(attrib)

        if not candidates:
            context.scene.xml_llm_status = "Nessun candidato trovato — prova a indicizzare il prezzario"
            return {'FINISHED'}

        # Step 2: LLM ranking
        try:
            results = _llm.suggest(query, candidates)
        except Exception as e:
            self.report({'ERROR'}, f"Errore Ollama: {e}")
            context.scene.xml_llm_status = f"Errore: {e}"
            return {'CANCELLED'}

        # Build id→rate_idx map
        id_to_idx = {json.loads(rate_list[c['_rate_idx']].attributes)['id']: c['_rate_idx']
                     for c in candidates}

        for r in results:
            item_id = r.get('id', '')
            rate_idx = id_to_idx.get(item_id)
            if rate_idx is None:
                continue
            item = context.scene.xml_llm_results.add()
            item.name    = f"{item_id} – {r.get('name', '')}"
            item.item_id = item_id
            item.rate_index = rate_idx
            item.motivo  = r.get('motivo', '')

        if len(context.scene.xml_llm_results) > 0:
            context.scene.xml_llm_active_index = 0
            context.scene.xml_rate_list_active_index = context.scene.xml_llm_results[0].rate_index
            context.scene.xml_llm_status = ""
        else:
            context.scene.xml_llm_status = "Nessun risultato pertinente trovato"

        return {'FINISHED'}


class LLMConfirmChoice(Operator):
    """Confirm the selected AI suggestion and save it to the preference store."""

    bl_idname = "rate_list.llm_confirm"
    bl_label = "Conferma scelta"

    def execute(self, context):
        from ...core import llm_search as _llm
        results = context.scene.xml_llm_results
        idx     = context.scene.xml_llm_active_index
        if not (0 <= idx < len(results)):
            return {'CANCELLED'}
        chosen  = results[idx]
        query   = context.scene.xml_llm_query.strip()
        _llm.save_pref(query, chosen.item_id, chosen.name)
        context.scene.xml_llm_status = f"Salvato: {chosen.item_id}"
        return {'FINISHED'}


class BuildSearchIndex(Operator):
    """Build the semantic search index for the currently loaded price list."""

    bl_idname = "rate_list.build_search_index"
    bl_label = "Semantic Search"

    @classmethod
    def poll(cls, context):
        return len(getattr(context.scene, "xml_rate_list", [])) > 0

    def execute(self, context):
        from ...core import semantic_search as _ss
        rates = [json.loads(item.attributes) for item in context.scene.xml_rate_list]
        _ss.build_index(rates, key=_data._current_search_key)
        return {"FINISHED"}


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
    LLMSuggestRates,
    LLMConfirmChoice,
]
