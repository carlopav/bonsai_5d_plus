# Requires pytest: pip install pytest
#
# Stubs the parts of `bpy` (and `bpy_extras`/`mathutils`) that
# bonsai_5d_plus touches at *import* time, so `import bonsai_5d_plus...`
# works under plain CPython without a real Blender install. Runtime
# behaviour (draw/execute methods) is never exercised by these tests.

import os
import sys
import types

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


def _ensure_odf_importable():
    try:
        import odf  # noqa: F401

        return
    except ImportError:
        pass
    # Same Bonsai wheels path fallback as _ensure_odf() in prints_manager/operator.py.
    appdata = os.environ.get("APPDATA", "")
    site = os.path.join(
        appdata,
        r"Blender Foundation\Blender\5.1\extensions\.local\lib\python3.13\site-packages",
    )
    if os.path.isdir(site) and site not in sys.path:
        sys.path.insert(0, site)


def _install_bpy_stub():
    if "bpy" in sys.modules:
        return

    bpy = types.ModuleType("bpy")

    # ---- bpy.types ----
    bpy_types = types.ModuleType("bpy.types")

    class Panel:
        pass

    class Operator:
        pass

    class UIList:
        pass

    class PropertyGroup:
        pass

    class Menu:
        pass

    class AddonPreferences:
        pass

    class Scene:
        pass

    class WindowManager:
        pass

    class Object:
        pass

    bpy_types.Panel = Panel
    bpy_types.Operator = Operator
    bpy_types.UIList = UIList
    bpy_types.UI_UL_list = UIList
    bpy_types.PropertyGroup = PropertyGroup
    bpy_types.Menu = Menu
    bpy_types.AddonPreferences = AddonPreferences
    bpy_types.Scene = Scene
    bpy_types.WindowManager = WindowManager
    bpy_types.Object = Object

    # ---- bpy.props ----
    bpy_props = types.ModuleType("bpy.props")

    def _placeholder_property(*args, **kwargs):
        return ("_bpy_prop_placeholder", args, kwargs)

    for _name in (
        "BoolProperty",
        "IntProperty",
        "FloatProperty",
        "StringProperty",
        "EnumProperty",
        "PointerProperty",
        "CollectionProperty",
        "FloatVectorProperty",
        "IntVectorProperty",
        "BoolVectorProperty",
    ):
        setattr(bpy_props, _name, _placeholder_property)

    # ---- bpy.utils ----
    bpy_utils = types.ModuleType("bpy.utils")
    _registered_idnames = set()

    def register_class(cls):
        bl_idname = getattr(cls, "bl_idname", None)
        if bl_idname is not None:
            if bl_idname in _registered_idnames:
                raise ValueError(f"Duplicate bl_idname on register: {bl_idname}")
            _registered_idnames.add(bl_idname)
        return cls

    def unregister_class(cls):
        bl_idname = getattr(cls, "bl_idname", None)
        if bl_idname is not None:
            _registered_idnames.discard(bl_idname)

    def register_classes_factory(classes):
        def register():
            for cls in classes:
                register_class(cls)

        def unregister():
            for cls in reversed(classes):
                unregister_class(cls)

        return register, unregister

    bpy_utils.register_class = register_class
    bpy_utils.unregister_class = unregister_class
    bpy_utils.register_classes_factory = register_classes_factory
    bpy_utils.user_resource = lambda *a, **k: _REPO_ROOT

    # ---- bpy.app ----
    bpy_app = types.ModuleType("bpy.app")
    bpy_app_handlers = types.ModuleType("bpy.app.handlers")
    bpy_app_handlers.depsgraph_update_post = []

    def persistent(fn):
        return fn

    bpy_app_handlers.persistent = persistent

    bpy_app_timers = types.ModuleType("bpy.app.timers")
    bpy_app_timers.register = lambda *a, **k: None

    bpy_app.handlers = bpy_app_handlers
    bpy_app.timers = bpy_app_timers

    # ---- bpy.data ----
    class _TextsCollection(dict):
        def new(self, name):
            text = types.SimpleNamespace(name=name, _lines=[""])
            text.as_string = lambda: "\n".join(text._lines)
            self[name] = text
            return text

        def remove(self, text):
            self.pop(getattr(text, "name", text), None)

    bpy_data = types.SimpleNamespace(texts=_TextsCollection())

    # ---- bpy.context ----
    bpy_context = types.SimpleNamespace(scene=Scene(), window_manager=WindowManager())

    # ---- bpy.ops ----
    class _OpsNamespace(types.SimpleNamespace):
        def __getattr__(self, item):
            raise AttributeError(item)

    bpy_ops = _OpsNamespace()

    bpy.types = bpy_types
    bpy.props = bpy_props
    bpy.utils = bpy_utils
    bpy.app = bpy_app
    bpy.data = bpy_data
    bpy.context = bpy_context
    bpy.ops = bpy_ops

    sys.modules["bpy"] = bpy
    sys.modules["bpy.types"] = bpy_types
    sys.modules["bpy.props"] = bpy_props
    sys.modules["bpy.utils"] = bpy_utils
    sys.modules["bpy.app"] = bpy_app
    sys.modules["bpy.app.handlers"] = bpy_app_handlers
    sys.modules["bpy.app.timers"] = bpy_app_timers

    # ---- bpy_extras.io_utils ----
    bpy_extras = types.ModuleType("bpy_extras")
    io_utils = types.ModuleType("bpy_extras.io_utils")

    class ExportHelper:
        pass

    class ImportHelper:
        pass

    io_utils.ExportHelper = ExportHelper
    io_utils.ImportHelper = ImportHelper
    bpy_extras.io_utils = io_utils
    sys.modules["bpy_extras"] = bpy_extras
    sys.modules["bpy_extras.io_utils"] = io_utils

    # ---- mathutils ----
    mathutils = types.ModuleType("mathutils")

    class Vector(list):
        pass

    mathutils.Vector = Vector
    sys.modules["mathutils"] = mathutils


_ensure_odf_importable()
_install_bpy_stub()
