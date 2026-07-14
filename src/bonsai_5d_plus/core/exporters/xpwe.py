# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.
#
# Bonsai5D+ is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai5D+ is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai5D+.  If not, see <http://www.gnu.org/licenses/>.

"""XPWE (PriMus) exporter — IFC cost schedule(s) → XPWE XML string.

Inverse of ``core/parsers/xpwe.py``. Drives off a CME schedule
(``PRICEDBILLOFQUANTITIES``) and produces a PriMus computo document:

* ``PweElencoPrezzi`` — the price list (EPItem).
* ``PweVociComputo`` — the measured items (VCItem) with RGItem rows,
  each linked to its price via ``IDEP``.

Two source layouts are supported (see ``_collect``):

1. **BoQ alone** — the CME items carry their own rate (no linked SoR). One EP
   is synthesised per CME article (deduplicated by Identification).
2. **BoQ + SoR linked via IfcRelAssignsToControl** — each CME item points at a
   Schedule-of-Rates item. The *whole* SoR is exported as the price list (it may
   contain more prices than the CME uses); VCItems reference their linked EP.

PweEPAnalisi (price analysis detail) is intentionally left empty for now — it
will be implemented once the populated PweEPAR schema is confirmed from a sample.
"""

import xml.etree.ElementTree as ET

from ..formula import split_formula as _split_formula


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _num(v, places=6):
    """Format a number the PriMus way: plain decimal, trailing zeros trimmed."""
    try:
        f = round(float(v), places)
    except (TypeError, ValueError):
        return "0"
    if f == int(f):
        return str(int(f))
    return ("%.*f" % (places, f)).rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# IFC reading helpers (ifcopenshell only — no bpy)
# ---------------------------------------------------------------------------

def _children(item):
    return [
        o
        for rel in (item.IsNestedBy or [])
        for o in (rel.RelatedObjects or [])
        if o.is_a("IfcCostItem")
    ]


def _is_chapter(item):
    """A cost item is a chapter (category/capitolo) when it nests other items."""
    return bool(_children(item))


def _rate_controller(item):
    """The Schedule-of-Rates cost item controlling this one, or None."""
    for rel in (item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl"):
            ctrl = rel.RelatingControl
            if ctrl.is_a("IfcCostItem"):
                return ctrl
    return None


def _schedule_of(item):
    """The IfcCostSchedule a cost item belongs to (walks up the nesting)."""
    for rel in (item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl") and rel.RelatingControl.is_a("IfcCostSchedule"):
            return rel.RelatingControl
    for rel in (item.Nests or []):
        return _schedule_of(rel.RelatingObject)
    return None


def _applied(cv):
    try:
        v = cv.AppliedValue
        if v is None:
            return 0.0
        return float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
    except Exception:
        return 0.0


def _unit_symbol(unit_entity):
    if unit_entity is None:
        return ""
    try:
        import ifcopenshell.util.unit
        sym = ifcopenshell.util.unit.get_unit_symbol(unit_entity)
        if sym:
            return sym
    except Exception:
        pass
    return str(getattr(unit_entity, "Name", "") or "")


# IFC IfcCostValue.Category → XPWE incidence key.
_CAT_TO_INC = {
    "Labor": "labor",
    "Equipment": "equipment",
    "Material": "materials",
    "Safety": "safety",
}


def _read_price(item):
    """Read unit price, per-category incidences and unit from top-level CostValues.

    Returns (prezzo, {labor, equipment, materials, safety}, unit). SUM aggregators
    (Category '*') on chapters are ignored. Incidence amounts are absolute
    (currency), matching how the importer stored them.
    """
    prezzo = 0.0
    inc = {"labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0}
    unit = ""
    for cv in (item.CostValues or []):
        cat = getattr(cv, "Category", None)
        if cat == "*":
            continue
        amount = _applied(cv)
        prezzo += amount
        if cat in _CAT_TO_INC:
            inc[_CAT_TO_INC[cat]] += amount
        if not unit:
            ub = getattr(cv, "UnitBasis", None)
            if ub is not None:
                unit = _unit_symbol(ub.UnitComponent)
    if unit == "1":
        unit = ""
    return round(prezzo, 6), inc, unit


def _quantities(item):
    """Measurement rows from CostQuantities: list of {desc, value, formula}."""
    rows = []
    for q in (item.CostQuantities or []):
        if not q.is_a("IfcPhysicalSimpleQuantity"):
            continue
        try:
            value = float(q[3]) if q[3] is not None else 0.0
        except Exception:
            value = 0.0
        rows.append({
            "desc": q.Name or "",
            "value": value,
            "formula": getattr(q, "Formula", None) or "",
        })
    return rows


# ---------------------------------------------------------------------------
# Project header (PweDatiGenerali) from the IFC project
# ---------------------------------------------------------------------------

def _person_name(person):
    if person is None:
        return ""
    parts = [getattr(person, "GivenName", None), getattr(person, "FamilyName", None)]
    name = " ".join(p for p in parts if p)
    return name or (getattr(person, "Identification", None) or "")


def _actor_name(actor):
    """Display name of an IfcActorSelect (Organization / Person / both)."""
    if actor is None:
        return ""
    if actor.is_a("IfcOrganization"):
        return actor.Name or ""
    if actor.is_a("IfcPerson"):
        return _person_name(actor)
    if actor.is_a("IfcPersonAndOrganization"):
        org = actor.TheOrganization.Name if actor.TheOrganization else ""
        return org or _person_name(actor.ThePerson)
    return ""


def _role_str(actor_role):
    if actor_role is None:
        return ""
    role = actor_role.Role or ""
    if role == "USERDEFINED":
        return (actor_role.UserDefinedRole or "").upper()
    return role.upper()


def _first_postal_address(file):
    for site in file.by_type("IfcSite"):
        if site.SiteAddress:
            return site.SiteAddress
    for building in file.by_type("IfcBuilding"):
        if building.BuildingAddress:
            return building.BuildingAddress
    addresses = file.by_type("IfcPostalAddress")
    return addresses[0] if addresses else None


def _read_actors(file):
    """Best-effort (committente, impresa) from IfcRelAssignsToActor roles."""
    committente = ""
    impresa = ""
    client_roles = {"CLIENT", "OWNER", "COMMITTENTE"}
    contractor_roles = {"CONTRACTOR", "CONSTRUCTIONMANAGER", "IMPRESA"}
    for rel in file.by_type("IfcRelAssignsToActor"):
        role = _role_str(rel.ActingRole)
        name = _actor_name(rel.RelatingActor)
        if not name:
            continue
        if role in client_roles and not committente:
            committente = name
        elif role in contractor_roles and not impresa:
            impresa = name
    return committente, impresa


def _read_currency(file):
    """ISO currency from the project's IfcMonetaryUnit, lowercased (PriMus style)."""
    for mu in file.by_type("IfcMonetaryUnit"):
        cur = getattr(mu, "Currency", None)
        if cur:
            return str(cur).lower()
    return "eur"


def _read_project_header(file, schedule):
    """Build the PweDatiGenerali fields from the IFC project, not from a template."""
    header = {
        "oggetto": "", "comune": "", "provincia": "",
        "committente": "", "impresa": "", "parte_opera": "",
        "divisa": _read_currency(file),
    }

    projects = file.by_type("IfcProject")
    project = projects[0] if projects else None
    if project is not None:
        header["oggetto"] = project.LongName or project.Description or project.Name or ""
    if not header["oggetto"]:
        header["oggetto"] = schedule.Name or ""

    addr = _first_postal_address(file)
    if addr is not None:
        header["comune"] = addr.Town or ""
        header["provincia"] = addr.Region or ""

    header["committente"], header["impresa"] = _read_actors(file)
    return header


# ---------------------------------------------------------------------------
# Model collection
# ---------------------------------------------------------------------------

_SUBCAT_SEP = " - "


def _traverse(schedule, level_defs, ctx):
    """Pre-order DFS of a schedule onto XPWE's fixed 3 grouping levels.

    XPWE has exactly three category slots (SuperCat / Cat / SubCat), so an IFC
    hierarchy deeper than three is compacted: chapter depth 0 → SuperCat, depth 1
    → Cat, and every chapter at depth ≥2 is **merged into a single SubCat** whose
    description concatenates the deep chapter titles (e.g. "Murature - Tramezzi -
    Interni"). No leaf loses its grouping and no chapter title is lost; only the
    intermediate subtotal lines beyond the third level are not represented.

    ``level_defs`` is a tuple of 3 dicts {assigned_id: {codice, desc}}; ``ctx``
    carries the shared counter list and the SubCat path-dedup map so ids stay
    unique across multiple schedules. Yields (leaf_item, (sp, cat, sub)), each id
    being 0 when that level is absent.
    """
    import ifcopenshell.util.cost as cost_util

    sp_def, cat_def, sub_def = level_defs
    counters = ctx["counters"]
    sub_paths = ctx["sub_paths"]

    def rec(item, depth, sp_id, cat_id, deep):
        if _is_chapter(item):
            name = item.Name or ""
            code = item.Identification or ""
            if depth == 0:
                counters[0] += 1
                sp_id = counters[0]
                sp_def[sp_id] = {"codice": code, "desc": name}
            elif depth == 1:
                counters[1] += 1
                cat_id = counters[1]
                cat_def[cat_id] = {"codice": code, "desc": name}
            else:
                deep = deep + [(item.id(), name, code)]
            for child in _children(item):
                yield from rec(child, depth + 1, sp_id, cat_id, deep)
        else:
            sub_id = 0
            if deep:
                key = tuple(d[0] for d in deep)
                sub_id = sub_paths.get(key)
                if sub_id is None:
                    counters[2] += 1
                    sub_id = counters[2]
                    sub_paths[key] = sub_id
                    sub_def[sub_id] = {
                        "codice": deep[-1][2],
                        "desc": _SUBCAT_SEP.join(d[1] for d in deep),
                    }
            yield item, (sp_id, cat_id, sub_id)

    for root in cost_util.get_root_cost_items(schedule):
        yield from rec(root, 0, 0, 0, [])


def _ep_entry(xml_id, item, prezzo, inc, unit, chain):
    ident = (item.Identification or "").strip()
    return {
        "xml_id": xml_id,
        "tariffa": ident,
        "name": item.Name or "",
        "desc": item.Description or "",
        "unit": unit,
        "prezzo": prezzo,
        "inc": inc,
        "spcap": chain[0],
        "cap": chain[1],
        "sbcap": chain[2],
    }


def _collect(file, cme_schedule):
    """Build the plain export model from a CME schedule. See module docstring."""
    import ifcopenshell.util.cost as cost_util

    model = {
        "header": _read_project_header(file, cme_schedule),
        "ep": [],
        "vc": [],
        "capitoli": ({}, {}, {}),
        "categorie": ({}, {}, {}),
    }

    # Detect linked SoR/EPU schedules (case 2).
    epu_schedules = []
    seen = set()

    def scan(item):
        if _is_chapter(item):
            for child in _children(item):
                scan(child)
            return
        ctrl = _rate_controller(item)
        if ctrl is not None:
            sch = _schedule_of(ctrl)
            if sch is not None and sch.id() not in seen:
                seen.add(sch.id())
                epu_schedules.append(sch)

    for root in cost_util.get_root_cost_items(cme_schedule):
        scan(root)

    # Case 2: export the whole price list from the linked SoR schedule(s).
    ep_id_by_entity = {}
    ep_n = 0
    if epu_schedules:
        cap_ctx = {"counters": [0, 0, 0], "sub_paths": {}}
        for sch in epu_schedules:
            for leaf, chain in _traverse(sch, model["capitoli"], cap_ctx):
                ep_n += 1
                prezzo, inc, unit = _read_price(leaf)
                model["ep"].append(_ep_entry(ep_n, leaf, prezzo, inc, unit, chain))
                ep_id_by_entity[leaf.id()] = ep_n

    # Walk the CME building VCItems; synthesise EPs for unlinked items (case 1,
    # and any orphan leaf in case 2).
    cat_ctx = {"counters": [0, 0, 0], "sub_paths": {}}
    synth = {}
    for leaf, chain in _traverse(cme_schedule, model["categorie"], cat_ctx):
        prezzo, inc, unit = _read_price(leaf)
        rows = _quantities(leaf)
        total = round(sum(r["value"] for r in rows), 6)

        ep_id = None
        ctrl = _rate_controller(leaf)
        if ctrl is not None:
            ep_id = ep_id_by_entity.get(ctrl.id())
        if ep_id is None:
            key = (leaf.Identification or "").strip() or f"#{leaf.id()}"
            if key in synth:
                ep_id = synth[key]
            else:
                ep_n += 1
                model["ep"].append(_ep_entry(ep_n, leaf, prezzo, inc, unit, chain))
                synth[key] = ep_n
                ep_id = ep_n

        model["vc"].append({
            "ep_xml_id": ep_id,
            "quantita": total,
            "rows": rows,
            "cats": chain,
        })

    # Case 1: there is no separate price list, so the synthesised EPs were filed
    # under the computo chapters — mirror those as capitoli so IDSpCap/IDCap/
    # IDSbCap resolve.
    if not epu_schedules:
        model["capitoli"] = model["categorie"]

    return model


# ---------------------------------------------------------------------------
# XML serialisation
# ---------------------------------------------------------------------------

def _sub(parent, tag, text=None, **attrib):
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in attrib.items()})
    if text is not None and text != "":
        el.text = str(text)
    return el


def _id_str(value):
    """Category reference: empty string when the level is absent (id 0)."""
    return str(value) if value else ""


def _write_categories(parent, level_defs, item_tag_prefix):
    """Write a 3-level chapter/category block (SuperX / X / SubX)."""
    sp, mid, sb = level_defs
    sections = (
        (f"PweDGSuper{item_tag_prefix}", f"DGSuper{item_tag_prefix}Item", sp),
        (f"PweDG{item_tag_prefix}",      f"DG{item_tag_prefix}Item",      mid),
        (f"PweDGSub{item_tag_prefix}",   f"DGSub{item_tag_prefix}Item",   sb),
    )
    for section_tag, item_tag, defs in sections:
        section = ET.SubElement(parent, section_tag)
        for aid in sorted(defs):
            d = defs[aid]
            item = ET.SubElement(section, item_tag, {"ID": str(aid)})
            _sub(item, "DesSintetica", d["desc"])
            _sub(item, "DesEstesa", d["desc"])
            if d["codice"]:
                _sub(item, "Codice", d["codice"])


def _write_header(doc, model, filename):
    _sub(doc, "CopyRight")
    _sub(doc, "TipoDocumento", "1")          # 1 = computo
    _sub(doc, "TipoFormato", "XMLPwe")
    _sub(doc, "Versione", "5.01")
    _sub(doc, "SourceVersione", "Bonsai5D+")
    _sub(doc, "SourceNome", "Bonsai5D+")
    _sub(doc, "FileNameDocumento", filename)

    dg = ET.SubElement(doc, "PweDatiGenerali")

    for wbs_tag, item_tag in (("PweDGWBS", "DGWBSItem"), ("PweDGWBSCAP", "DGWBSCAPItem")):
        wbs = ET.SubElement(dg, wbs_tag)
        _sub(wbs, "DGWBSAttiva" if wbs_tag == "PweDGWBS" else "DGWBSCAPAttiva", "0")
        item = ET.SubElement(wbs, item_tag, {"ID": "1"})
        _sub(item, "CU", "00000000-0000-0000-0000-000000000001")
        _sub(item, "CUParent")
        _sub(item, "TITOLO", "Work Breakdown Structure")
        _sub(item, "CODICE")
        _sub(item, "CodiceExt")

    hdr = model["header"]
    prog = ET.SubElement(dg, "PweDGProgetto")
    dati = ET.SubElement(prog, "PweDGDatiGenerali")
    _sub(dati, "PercPrezzi", "0")
    _sub(dati, "Comune", hdr["comune"])
    _sub(dati, "Provincia", hdr["provincia"])
    _sub(dati, "Oggetto", hdr["oggetto"])
    _sub(dati, "Committente", hdr["committente"])
    _sub(dati, "Impresa", hdr["impresa"])
    _sub(dati, "ParteOpera", hdr["parte_opera"])

    cfg = ET.SubElement(dg, "PweDGConfigurazione")
    numeri = ET.SubElement(cfg, "PweDGConfigNumeri")
    for tag, text in (
        ("Divisa", hdr["divisa"]), ("ConversioniIN", "lire"),
        ("FattoreConversione", "1936.27"), ("Cambio", "1"),
        ("PartiUguali", "8.3|0"), ("Lunghezza", "9.3|0"),
        ("Larghezza", "9.3|0"), ("HPeso", "10.3|0"),
        ("Quantita", "11.2|0"), ("Prezzi", "10.2|0"),
        ("PrezziTotale", "14.2|0"), ("ConvPrezzi", "11.2|0"),
        ("ConvPrezziTotale", "15.2|0"), ("IncidenzaPercentuale", "7.4|0"),
        ("Aliquote", "7.4|0"),
    ):
        _sub(numeri, tag, text)

    cap_cat = ET.SubElement(dg, "PweDGCapitoliCategorie")
    _write_categories(cap_cat, model["capitoli"], "Capitoli")
    _write_categories(cap_cat, model["categorie"], "Categorie")


def _write_elenco_prezzi(mis, model):
    ep_root = ET.SubElement(mis, "PweElencoPrezzi")
    for ep in model["ep"]:
        prezzo = ep["prezzo"]
        item = ET.SubElement(ep_root, "EPItem", {"ID": str(ep["xml_id"])})
        _sub(item, "TipoEP", "0")
        _sub(item, "Tariffa", ep["tariffa"])
        _sub(item, "Articolo", ep["tariffa"])
        _sub(item, "DesRidotta", ep["name"])
        _sub(item, "DesEstesa", ep["desc"] or ep["name"])
        _sub(item, "UnMisura", ep["unit"])
        _sub(item, "Prezzo1", _num(prezzo))
        for n in range(2, 6):
            _sub(item, f"Prezzo{n}", "0")

        def pct(amount):
            return _num(amount / prezzo * 100, places=4) if prezzo else "0"

        _sub(item, "IncMAT", pct(ep["inc"]["materials"]))
        _sub(item, "IncMDO", pct(ep["inc"]["labor"]))
        _sub(item, "IncATTR", pct(ep["inc"]["equipment"]))
        _sub(item, "IncSIC", pct(ep["inc"]["safety"]))
        _sub(item, "IDSpCap", _id_str(ep["spcap"]))
        _sub(item, "IDCap", _id_str(ep["cap"]))
        _sub(item, "IDSbCap", _id_str(ep["sbcap"]))
        # PweEPAnalisi left empty for now (price-analysis detail not yet exported).
        ET.SubElement(item, "PweEPAnalisi")


def _write_voci_computo(mis, model):
    vc_root = ET.SubElement(mis, "PweVociComputo")
    for n, vc in enumerate(model["vc"], start=1):
        total = vc["quantita"]
        item = ET.SubElement(vc_root, "VCItem", {"ID": str(n)})
        _sub(item, "IDEP", str(vc["ep_xml_id"]))
        _sub(item, "Quantita", _num(total))
        sp, cat, sb = vc["cats"]
        _sub(item, "IDSpCat", _id_str(sp))
        _sub(item, "IDCat", _id_str(cat))
        _sub(item, "IDSbCat", _id_str(sb))
        misure = ET.SubElement(item, "PweVCMisure")
        for r, row in enumerate(vc["rows"], start=1):
            pu, lu, la, hp, faithful = _split_formula(row["formula"], row["value"])
            desc = row["desc"]
            if not faithful and row["formula"].strip():
                # Formula couldn't be split into the 4 columns — keep it visible
                # next to the description so the derivation isn't lost.
                desc = (desc + "  [" + row["formula"].strip() + "]").strip()
            rg = ET.SubElement(misure, "RGItem", {"ID": str(r)})
            _sub(rg, "IDVV", "-2")
            _sub(rg, "Descrizione", desc)
            _sub(rg, "PartiUguali", pu)
            _sub(rg, "Lunghezza", lu)
            _sub(rg, "Larghezza", la)
            _sub(rg, "HPeso", hp)
            # RGItem.Quantita carries the VCItem total, as PriMus expects.
            _sub(rg, "Quantita", _num(total))
            _sub(rg, "Flags", "0")


def build_xpwe_xml(model, filename=""):
    """Serialise an export model (from ``_collect``) into an XPWE XML string."""
    doc = ET.Element("PweDocumento")
    _write_header(doc, model, filename)
    mis = ET.SubElement(doc, "PweMisurazioni")
    _write_elenco_prezzi(mis, model)
    _write_voci_computo(mis, model)

    ET.indent(doc, space="  ")
    body = ET.tostring(doc, encoding="unicode")
    return '<?xml version="1.0"?>\n' + body


def export_cost_schedule_to_xpwe(file, schedule, filename=""):
    """Read an IFC cost schedule and return the XPWE document as a string.

    ``file`` is an ``ifcopenshell.file``; ``schedule`` the driving CME
    ``IfcCostSchedule`` (PRICEDBILLOFQUANTITIES).
    """
    model = _collect(file, schedule)
    return build_xpwe_xml(model, filename=filename)
