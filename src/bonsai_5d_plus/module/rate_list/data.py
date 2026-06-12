# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import os
import json
import textwrap
import bpy

from ...core.parsers import PriceListParser, ParserIfcCostSchedule, _find_xml_parser


# Module-level state ─────────────────────────────────────────────────────────

_recent_cache = []   # prevents GC of enum item strings
_importing = False   # guard against recursive import on xml_rate_recent_path update
_ifc_schedules_cache = []
_current_search_key = None  # key of the currently loaded price list, for the index operator

# Replaces RateListPanel.active_item_info (class var) — accessed by ui.py
active_item_info = "no item selected"

# Filter cache invalidation counter — incremented whenever list data or
# expand/collapse state changes so filter_items can skip recomputation.
_filter_gen = 0


def _invalidate_filter_cache():
    global _filter_gen
    _filter_gen += 1


# Recent files ────────────────────────────────────────────────────────────────

def _recent_file_path():
    return os.path.join(bpy.utils.user_resource('CONFIG'), 'RateListImporter_recent.json')


def _load_recent():
    try:
        with open(_recent_file_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _save_recent(path, title, year):
    entries = _load_recent()
    entries = [e for e in entries if e['path'] != path]
    entries.insert(0, {'path': path, 'title': title, 'year': year})
    entries = entries[:10]
    try:
        with open(_recent_file_path(), 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _refresh_recent_cache():
    global _recent_cache
    entries = _load_recent()
    if entries:
        _recent_cache = [
            (
                e['path'],
                f"{e['title']} ({e['year']})" if e.get('year') else e['title'],
                e['path'],
            )
            for e in entries
        ]
    else:
        _recent_cache = [('__NONE__', '— nessun prezzario recente —', '')]


def _get_recent_items(self, context):
    return _recent_cache or [('__NONE__', '— nessun prezzario recente —', '')]


def _on_recent_select(self, context):
    global _importing
    if _importing:
        return
    path = self.xml_rate_recent_path
    if path and path != '__NONE__':
        _do_import(path, context)


# IFC schedule source ────────────────────────────────────────────────────────

def _refresh_ifc_schedules_cache():
    global _ifc_schedules_cache
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        if file is None:
            _ifc_schedules_cache = [('__NONE__', '— nessun schedule IFC —', '')]
            return
        schedules = file.by_type("IfcCostSchedule")
        _ifc_schedules_cache = [
            (str(s.id()), s.Name or f"Schedule {s.id()}", "")
            for s in schedules
        ] or [('__NONE__', '— nessun schedule IFC —', '')]
    except Exception:
        _ifc_schedules_cache = [('__NONE__', '— nessun schedule IFC —', '')]


def _get_ifc_schedules(self, context):
    return _ifc_schedules_cache or [('__NONE__', '— nessun schedule IFC —', '')]


def _on_ifc_schedule_select(self, context):
    schedule_id = self.ifc_rate_source_schedule
    if schedule_id and schedule_id != '__NONE__':
        _do_import_ifc(schedule_id, context)
    else:
        context.scene.xml_rate_list.clear()


def _on_source_mode_change(self, context):
    if self.rate_source_mode == 'FILE':
        path = context.scene.xml_rate_recent_path
        if path and path != '__NONE__':
            _do_import(path, context)
        else:
            context.scene.xml_rate_list.clear()
    else:
        _refresh_ifc_schedules_cache()
        schedule_id = context.scene.ifc_rate_source_schedule
        if schedule_id and schedule_id != '__NONE__':
            _do_import_ifc(schedule_id, context)
        else:
            context.scene.xml_rate_list.clear()


# Rate list population ────────────────────────────────────────────────────────

def _on_search_query_change(self, context):
    import json
    from ...core import semantic_search as _ss
    if not _ss.is_ready():
        return
    query = self.xml_rate_search_query.strip()
    context.scene.xml_rate_search_results.clear()
    if not query:
        return
    results = _ss.search(query, n=10)
    rate_list = context.scene.xml_rate_list
    for rate_idx, score in results:
        item = context.scene.xml_rate_search_results.add()
        attrib = json.loads(rate_list[rate_idx].attributes)
        item.name = f"[{score:.0%}] {attrib['id']} – {attrib['name']}"
        item.rate_index = rate_idx
        item.score = score
    if len(context.scene.xml_rate_search_results) > 0:
        context.scene.xml_rate_search_active_index = 0


def _on_llm_result_select(self, context):
    results = context.scene.xml_llm_results
    idx = context.scene.xml_llm_active_index
    if 0 <= idx < len(results):
        context.scene.xml_rate_list_active_index = results[idx].rate_index


def _on_search_result_select(self, context):
    results = context.scene.xml_rate_search_results
    idx = context.scene.xml_rate_search_active_index
    if 0 <= idx < len(results):
        context.scene.xml_rate_list_active_index = results[idx].rate_index


def _on_rate_selection_change(self, context):
    """Called when xml_rate_list_active_index changes — updates active_item_info."""
    global active_item_info
    try:
        selected_rate = bpy.context.scene.xml_rate_list[
            bpy.context.scene.xml_rate_list_active_index
        ]
        attrib = json.loads(selected_rate.attributes)
        new_label = ""
        new_label += attrib["id"] + "\n"
        new_label += attrib["name"] + "\n"
        new_label += str(attrib["unit"] or "-") + "\n"
        new_label += str(round(attrib["value"], 2) or "-") + "\n"
        new_label += str(round(attrib["labor"], 2) or "-") + "\n"
        new_label += str(round(attrib["equipment"], 2) or "-") + "\n"
        new_label += str(round(attrib["materials"], 2) or "-") + "\n"
        new_label += str(round(attrib["safety"], 2) or "-") + "\n"
        new_label += "Description:\n"
        for row in textwrap.wrap(attrib["desc"], 100):
            new_label += row + "\n"
        active_item_info = new_label
    except Exception:
        pass


def _populate_list_from_parser(parser, context, key=None):
    global _current_search_key
    _current_search_key = key
    _invalidate_filter_cache()
    context.scene.xml_rate_title = parser.title
    context.scene.xml_rate_year = parser.year
    context.scene.xml_rate_list.clear()

    rates = parser.xml_rate_list
    wm = context.window_manager
    try:
        wm.progress_begin(0, len(rates))
        for i, rate in enumerate(rates):
            if i % 100 == 0:
                wm.progress_update(i)
            item = context.scene.xml_rate_list.add()
            if rate["is_parent"] and rate["name"].startswith("Group "):
                item.name = rate["id"]
            else:
                item.name = (rate["id"] + " - " + rate["name"]).strip(" -") or f"Item {rate['index']}"
            item.level = rate["level"]
            item.is_parent = rate["is_parent"]
            item.parents = rate["parents"]
            item.attributes = json.dumps(rate)
            if item.is_parent:
                item.is_expanded = False
    finally:
        wm.progress_end()

    if len(context.scene.xml_rate_list) > 0:
        context.scene.xml_rate_list_active_index = 0

    from ...core import semantic_search as _ss
    _ss.try_activate_cached(key)


def _do_import(filepath, context, report=None):
    import re
    xml_content = PriceListParser.get_xml_content(filepath)
    parser_class = _find_xml_parser(xml_content)
    if parser_class is None:
        if report:
            report({'ERROR'}, "Cannot automatically find a parser for selected file")
        return False

    parser = parser_class()
    parser.parse_items(xml_content)

    filename = os.path.basename(filepath)
    name = os.path.splitext(filename)[0]
    match = re.search(r'\b(\d{4})\b', name)
    parser.year = match.group(1) if match else ""
    parser.title = name

    _populate_list_from_parser(parser, context, key=filepath)

    _save_recent(filepath, parser.title, parser.year)
    _refresh_recent_cache()
    global _importing
    _importing = True
    try:
        context.scene.xml_rate_recent_path = filepath
    finally:
        _importing = False
    return True


def _do_import_ifc(schedule_id, context, report=None):
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        if file is None:
            if report:
                report({'ERROR'}, "No IFC file loaded")
            return False
    except Exception as e:
        if report:
            report({'ERROR'}, str(e))
        return False

    parser = ParserIfcCostSchedule()
    parser.parse_schedule(file, schedule_id)
    _populate_list_from_parser(parser, context, key=f"ifc:{schedule_id}")
    return True
