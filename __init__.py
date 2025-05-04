bl_info = {
    "name": "DMC 3 Tools",
    "author": "",
    "version": (1, 0, 2),
    "blender": (4, 0, 0),
    "location": "File > Import > DMC HD",
    "description": "Import DMC 3 models/stages and animations.",
    "category": "Import-Export",
}

import bpy
from bpy.types import Operator, Menu
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty

# Auto-reload internal modules
if "DMC3" in locals():
    import importlib
    importlib.reload(DMC3)
    importlib.reload(DMC3.model)
    importlib.reload(DMC3.motion)
else:
    from . import DMC3
    from .DMC3 import model, motion

# ----------------------------
# Import Operators
# ----------------------------

class DMC3_OT_import_model(Operator, ImportHelper):
    bl_idname = "import_scene.dmc3_model"
    bl_label = "DMC3 Model (.mod/.scm)"
    filename_ext = ".mod"
    filter_glob: StringProperty(default="*.mod;*.scm", options={'HIDDEN'})

    def execute(self, context):
        model.Import(context, self.filepath)
        return {'FINISHED'}


class DMC3_OT_import_motion(Operator, ImportHelper):
    bl_idname = "import_scene.dmc3_motion"
    bl_label = "DMC3 Motion (.mot)"
    filename_ext = ".mot"
    filter_glob: StringProperty(default="*.mot", options={'HIDDEN'})

    def execute(self, context):
        motion.Import(context, self.filepath)
        return {'FINISHED'}


class DMC3_OT_import_stage(Operator, ImportHelper):
    bl_idname = "import_scene.dmc3_stage"
    bl_label = "DMC3 Stage (.scm)"
    filename_ext = ".scm"
    filter_glob: StringProperty(default="*.scm", options={'HIDDEN'})

    def execute(self, context):
        model.Import(context, self.filepath)
        return {'FINISHED'}


# ----------------------------
# Import Submenu
# ----------------------------

class DMC_HD_MT_import_submenu(Menu):
    bl_idname = "DMC_HD_MT_import_submenu"
    bl_label = "DMC HD"

    def draw(self, context):
        layout = self.layout
        layout.operator(DMC3_OT_import_model.bl_idname)
        layout.operator(DMC3_OT_import_motion.bl_idname)
        layout.operator(DMC3_OT_import_stage.bl_idname)


def menu_func_import(self, context):
    self.layout.menu(DMC_HD_MT_import_submenu.bl_idname)


# ----------------------------
# Registration
# ----------------------------

classes = (
    DMC3_OT_import_model,
    DMC3_OT_import_motion,
    DMC3_OT_import_stage,
    DMC_HD_MT_import_submenu,
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
