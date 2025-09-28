#__init__.py:
bl_info = {
    "name": "DMC3 Import",
    "author": "K0BR4",
    "version": (0, 3, 0),
    "blender": (4, 0, 0),
    "location": "File > Import > DMC3 Import",
    "description": "Import DMC3 models and animations (HD Collection compatible).",
    "category": "Import-Export",
    "support": "COMMUNITY",
    "doc_url": "https://github.com/HansLichtner/DMC3-Blender-Tools",
}



import os
from pathlib import Path
import importlib
import traceback
import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty

# try relative imports (works when installed as add-on) and fallback to top-level (dev)
try:
    from .DMC3 import model, motion
except Exception:
    import DMC3.model as model
    import DMC3.motion as motion

# Auto-reload while developing (Blender keeps modules loaded between installs)
if "importlib" in globals():
    try:
        importlib.reload(model)
        importlib.reload(motion)
    except Exception:
        pass

class DMC3_OT_import(Operator, ImportHelper):
    bl_idname = "import_scene.dmc3"
    bl_label = "Import DMC3 (.mod/ .mot/ .scm)"
    filename_ext = ".mod"
    filter_glob: StringProperty(default="*.mod;*.scm;*.mot", options={'HIDDEN'})

    def execute(self, context):
        fp = Path(self.filepath)
        ext = fp.suffix.lower()
        try:
            if ext in ('.mod', '.scm'):
                # model.Import expects a pathlib.Path in this addon
                return model.Import(context, fp)
            elif ext == '.mot':
                return motion.Import(context, fp)
            else:
                self.report({'WARNING'}, f"No importer for extension: {ext}")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
            return {'CANCELLED'}


def menu_func_import(self, context):
    # single, top-level menu entry (no submenu)
    self.layout.operator(DMC3_OT_import.bl_idname, text="DMC 3 (HD) Import (.mod/.scm/.mot)")

classes = (
    DMC3_OT_import,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()


