# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import os
import ifcopenshell
import ifcopenshell.api.classification
import ifcopenshell.util.classification
import ifcopenshell.util.cost

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_CLASSIFICATIONS_DIR = os.path.normpath(
    os.path.join(_THIS_DIR, "..", "..", "data", "classifications")
)


def _load_systems():
    """Return {key: (ifc_name, label, [(code, name), ...], {code: desc})} from IFC files."""
    systems = {}
    if not os.path.isdir(_CLASSIFICATIONS_DIR):
        return systems
    for fname in sorted(os.listdir(_CLASSIFICATIONS_DIR)):
        if not fname.lower().endswith(".ifc"):
            continue
        key = os.path.splitext(fname)[0]
        path = os.path.join(_CLASSIFICATIONS_DIR, fname)
        try:
            f = ifcopenshell.open(path)
            clss = f.by_type("IfcClassification")
            if not clss:
                continue
            ifc_name = clss[0].Name or key
            cats = []
            descs = {}
            for ref in f.by_type("IfcClassificationReference"):
                ident = getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None) or ""
                name = ref.Name or ident
                desc = getattr(ref, "Description", None) or ""
                if ident:
                    cats.append((ident, name))
                    if desc:
                        descs[ident] = desc
            systems[key] = (ifc_name, key, cats, descs)
        except Exception as e:
            print(f"[CostClassification] Cannot load {fname}: {e}")
    return systems


# Extended descriptions per TOL categories (not exposed via IFC4)
_BUILTIN_DESCRIPTIONS = {
    "TOL": {
        "TOL.1": (
            "Riguarda la nuova costruzione, la manutenzione, la ristrutturazione o il consolidamento di edifici civili "
            "e industriali non soggetti a tutela dei beni culturali quali, in via esemplificativa, le residenze, le "
            "carceri, le scuole, le caserme, gli uffici, i teatri, gli ospedali, gli stadi, gli edifici per le "
            "industrie, gli edifici per parcheggi, le stazioni ferroviarie e metropolitane e gli edifici aeroportuali. "
            "Include, in via esemplificativa e non esaustiva: infissi e rivestimenti interni ed esterni, "
            "pavimentazioni, massetti e sottofondi, solai (esclusi quelli interamente in cemento armato), altri "
            "manufatti in materie plastiche, materiali vetrosi e simili, murature e tramezzature comprensive di "
            "intonacatura, rasatura, tinteggiatura, verniciatura, opere di finitura quali isolamenti termici e "
            "acustici, controsoffittature, barriere al fuoco e opere di impermeabilizzazione, facciate continue e "
            "coperture in alluminio, apparecchi di appoggio in gomma. Sono da escludere: impianti elettrici, "
            "tecnologici, radiotelefonici, antintrusione, meccanici, termici, di condizionamento, idrico sanitari e "
            "trasportatori, le strutture e i manufatti in legno, in acciaio (travi, coperture, ecc.), in cemento "
            "armato gettato in opera o prefabbricato (pilastri, travi, pozzetti, serbatoi pensili e silos), gli scavi "
            "e i movimenti terra, le demolizioni, la raccolta di materiali di risulta e il loro smaltimento e "
            "qualsiasi lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
        ),
        "TOL.2": (
            "Riguarda la manutenzione, la ristrutturazione o il consolidamento di edifici civili e industriali "
            "soggetti a tutela dei beni culturali quali, in via esemplificativa, le residenze, le carceri, le scuole, "
            "gli ospedali, le caserme, gli uffici, i teatri, gli stadi, gli edifici per le industrie, gli edifici per "
            "parcheggi, le stazioni ferroviarie e metropolitane e gli edifici aeroportuali. Include, in via "
            "esemplificativa e non esaustiva: infissi e rivestimenti interni ed esterni, pavimentazioni, massetti e "
            "sottofondi, solai (esclusi quelli interamente in cemento armato), altri manufatti in materie plastiche, "
            "materiali vetrosi e simili, murature e tramezzature comprensive di intonacatura, rasatura, tinteggiatura, "
            "verniciatura, opere di finitura quali isolamenti termici e acustici, controsoffittature, barriere al "
            "fuoco e opere di impermeabilizzazione, facciate continue e coperture in alluminio, apparecchi di "
            "appoggio in gomma. Sono da escludere: impianti elettrici, tecnologici, radiotelefonici, antintrusione, "
            "meccanici, termici, di condizionamento, idrico sanitari e trasportatori, le strutture e i manufatti in "
            "legno, in acciaio (travi, coperture, ecc.), in cemento armato gettato in opera o prefabbricato "
            "(pilastri, travi, pozzetti, serbatoi pensili e silos), gli scavi e i movimenti terra, le demolizioni, "
            "la raccolta di materiali di risulta e il loro smaltimento e qualsiasi lavorazione o materiale "
            "direttamente riconducibile alle TOL Specializzate."
        ),
        "TOL.3": (
            "Riguarda gli scavi archeologici e le attività strettamente connesse da eseguirsi sia in aree dichiarate "
            "di interesse culturale sia in aree non dichiarate, condotti secondo normativa vigente."
        ),
        "TOL.4": (
            "Riguarda lo scavo e i movimenti terra di qualsiasi genere, trincee e rilevati, ripristino, modifica e "
            "bonifica di volumi di terra, realizzati qualunque sia la natura del terreno da scavare, ripristinare e "
            "bonificare."
        ),
        "TOL.5": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di pavimentazioni in conglomerato "
            "bituminoso."
        ),
        "TOL.6": (
            "Riguarda la produzione in stabilimenti industriali, il montaggio in situ e più in generale la nuova "
            "costruzione, la manutenzione e la ristrutturazione di strutture, opere di ingegneria e manufatti "
            "realizzati in acciaio."
        ),
        "TOL.7": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di strutture, opere di ingegneria "
            "e manufatti realizzati in cemento armato normale o precompresso, gettato in opera o prefabbricato."
        ),
        "TOL.8": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di strutture, opere di ingegneria "
            "e manufatti realizzati interamente o nella maggior parte in legno."
        ),
        "TOL.9": (
            "Riguarda la nuova costruzione attraverso il metodo di scavo tradizionale e la manutenzione, la "
            "ristrutturazione e la messa in sicurezza delle opere d'arte in sotterraneo."
        ),
        "TOL.10": (
            "Riguarda la nuova costruzione attraverso il metodo di scavo meccanizzato."
        ),
        "TOL.11": (
            "Riguarda la costruzione, la manutenzione o la ristrutturazione di interventi a rete, gli acquedotti, le "
            "fognature, i gasdotti, gli oleodotti, le torri piezometriche."
        ),
        "TOL.12": (
            "Riguarda la costruzione, la manutenzione o la ristrutturazione di interventi comunque realizzati in "
            "acque dolci e salate."
        ),
        "TOL.13": (
            "Riguarda la costruzione, la manutenzione o la ristrutturazione degli interventi a rete che sono "
            "necessari per la produzione, distribuzione ed energia elettrica."
        ),
        "TOL.14": (
            "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di un insieme di impianti "
            "elettrici, tecnologici, antintrusione, antincendio."
        ),
        "TOL.15": (
            "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di impianti meccanici, "
            "idro-sanitari, del gas, antincendio."
        ),
        "TOL.16": (
            "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di impianti di "
            "potabilizzazione e depurazione."
        ),
        "TOL.17": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di impianti di "
            "telecomunicazioni e gli impianti automatici per la segnaletica luminosa."
        ),
        "TOL.18": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione dei binari per qualsiasi ferrovia, "
            "metropolitana o linea tranviaria."
        ),
        "TOL.19": (
            "Riguarda la costruzione di opere destinate a trasferire i carichi di manufatti poggianti su terreni non "
            "idonei a reggere i carichi stessi."
        ),
        "TOL.20": (
            "Riguarda lo smaltimento o recupero a discarica di qualsiasi tipo di rifiuto pericoloso o non pericoloso."
        ),
    },
}

# Built once at import time
_SYSTEMS = _load_systems()

_BY_CODE = {
    key: {code: name for code, name in cats}
    for key, (_, _, cats, _) in _SYSTEMS.items()
}

_DESCRIPTIONS = {
    key: descs
    for key, (_, _, _, descs) in _SYSTEMS.items()
}

_ENUM_ITEMS = {
    key: [("", "—", "")] + [
        (code, f"{code}  –  {name}", _DESCRIPTIONS.get(key, {}).get(code, name))
        for code, name in cats
    ]
    for key, (_, _, cats, _) in _SYSTEMS.items()
}


def _prop_name(key):
    return f"cc_{key}_category"


# ---------------------------------------------------------------------------
# IFC classification helpers
# ---------------------------------------------------------------------------

def _get_or_create_classification(file, ifc_name):
    for cls in file.by_type("IfcClassification"):
        if cls.Name == ifc_name:
            return cls
    return ifcopenshell.api.classification.add_classification(file, classification=ifc_name)


def _get_code(cost_item, ifc_name):
    for ref in ifcopenshell.util.classification.get_references(cost_item):
        cls = ifcopenshell.util.classification.get_classification(ref)
        if cls and cls.Name == ifc_name:
            return getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None) or ""
    return ""


def _set_code(file, cost_item, ifc_name, code, code_names):
    for ref in list(ifcopenshell.util.classification.get_references(cost_item)):
        cls = ifcopenshell.util.classification.get_classification(ref)
        if cls and cls.Name == ifc_name:
            ifcopenshell.api.classification.remove_reference(file, reference=ref, products=[cost_item])

    if not code:
        return

    classification = _get_or_create_classification(file, ifc_name)
    ifcopenshell.api.classification.add_reference(
        file,
        products=[cost_item],
        classification=classification,
        identification=code,
        name=code_names.get(code, code),
    )


# ---------------------------------------------------------------------------
# Total + summary traversal
# ---------------------------------------------------------------------------

def _get_item_total(cost_item):
    rate = 0.0
    for cv in (cost_item.CostValues or []):
        try:
            v = cv.AppliedValue
            if v is not None:
                rate += float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
        except Exception:
            pass
    qty = 0.0
    for cq in (cost_item.CostQuantities or []):
        for attr in ("LengthValue", "AreaValue", "VolumeValue", "WeightValue", "CountValue", "TimeValue"):
            v = getattr(cq, attr, None)
            if v is not None:
                try:
                    qty += float(v)
                except Exception:
                    pass
                break
    return rate * qty if qty else rate


def _collect_totals(cost_item, inherited_code, ifc_name, accumulator):
    """Traverse propagating classification code downward; only leaf values counted."""
    code = _get_code(cost_item, ifc_name) or inherited_code
    children = [c for rel in (cost_item.IsNestedBy or []) for c in rel.RelatedObjects]
    if not children:
        key = code or "__none__"
        accumulator[key] = accumulator.get(key, 0.0) + _get_item_total(cost_item)
    else:
        for child in children:
            _collect_totals(child, code, ifc_name, accumulator)


def _build_summary(file, schedule_id, ifc_name):
    schedule = file.by_id(int(schedule_id))
    acc = {}
    for root in ifcopenshell.util.cost.get_root_cost_items(schedule):
        _collect_totals(root, "", ifc_name, acc)
    return acc
