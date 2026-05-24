bl_info = {
    "name": "Bonsai5D+",
    "author": "carlopav",
    "version": (0, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Rate List",
    "description": (
        "IFC cost management tools for Bonsai BIM: "
        "regional price list importer, rate analysis, BoQ-to-SoR conversion, bulk rate update."
    ),
    "category": "BIM",
}

import traceback

from . import RateListImporter
from . import RateAnalysis
from . import BoQToScheduleOfRates
from . import BulkUpdateCostSchedule
from . import CostClassification

_MODULES = [
    RateListImporter,
    RateAnalysis,
    BoQToScheduleOfRates,
    BulkUpdateCostSchedule,
    CostClassification,
]


def register():
    for mod in _MODULES:
        try:
            mod.register()
            print(f"[Bonsai5D+] registered: {mod.__name__}")
        except Exception:
            print(f"[Bonsai5D+] FAILED to register: {mod.__name__}")
            traceback.print_exc()


def unregister():
    for mod in reversed(_MODULES):
        try:
            mod.unregister()
        except Exception:
            print(f"[Bonsai5D+] FAILED to unregister: {mod.__name__}")
            traceback.print_exc()
