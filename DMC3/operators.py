#DMC3\operators.py:
import time
import bpy
import os
from enum import Enum

from bpy_extras.io_utils import (
    ImportHelper,
    path_reference_mode,
    ExportHelper
)

from bpy.types import (
    Operator,
)

from bpy.props import (
    BoolProperty,
    CollectionProperty,
    StringProperty,
    EnumProperty,
    IntProperty
)

import importlib, sys

def safe_reload(module_name: str):
    m = sys.modules.get(module_name)
    if m:
        try:
            importlib.reload(m)
        except Exception as e:
            cs.log_warn(f"Could not reload {module_name}: {e}")

# relative imports inside package
from . import model as dmc3_model
from . import motion as dmc3_motion
safe_reload(dmc3_model)
safe_reload(dmc3_motion)

# import local scene logging
from ..common import scene as cs

# Callback para atualização do filter 
def update_filter(self, context):
    try:
        val = context.scene.FileType
        try:
            cs.log_info(f"Scene.FileType updated to: {val}")
        except Exception:
            print(f"[DMC3] Scene.FileType updated to: {val}")
    except Exception:
        # fallback seguro
        try:
            print(f"[DMC3] Scene.FileType updated to: {getattr(context.scene, 'FileType', None)}")
        except Exception:
            print("[DMC3] Scene.FileType updated (unknown)")

# import operator class
class DMC3_OT_importer(Operator, ImportHelper):
    """Import models and animations from DMC3 of any version"""
    bl_idname: str = "import_scene.dmc3"
    bl_label: str = "DMC3 HDC models (.mod, .scm)"

    filename_ext: str = ".mod, .scm"

    filter_glob: StringProperty(
        default="*.mod;*.scm",
        options={'HIDDEN'},
        maxlen=255,
    )

    type: EnumProperty(
        items=(
            ('MODEL', 'Model', 'model'),
            ('MOTION', 'Motion', 'motion')
        ),
        name="Asset type",
        default='MODEL',
    )

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    def execute(self, context):
        startTime = time.perf_counter()
        files = self.files
        import_dir = os.path.dirname(self.filepath)
        # safe logging
        try:
            cs.log_info(self.type)
        except Exception:
            print(f"[DMC3] import type: {self.type}")

        for file in files:
            filepath = (os.path.join(import_dir, file.name))

            if self.type == 'MODEL':
                dmc3_model.Import(context, filepath)
            elif self.type == 'MOTION':
                dmc3_motion.Import(context, filepath)

        try:
            cs.log_info(f"Import took {time.perf_counter() - startTime:.3f}s")
        except Exception:
            print(f"[DMC3] Import took {time.perf_counter() - startTime:.3f}s")

        return {'FINISHED'}
        
    def invoke(self, context, event):
        if self.type == 'MODEL':
            self.filter_glob = "*.mod;*.scm"
            self.filename_ext = ".mod, .scm"
        elif self.type == 'MOTION':
            self.filter_glob = "*.mot"
            self.filename_ext = ".mot"
        return super().invoke(context, event)

bpy.types.Scene.my_filtered_filepath = StringProperty(
    name='Filtered',
    description="Import a model or animation",
    default="",
    subtype='NONE'  # important
)

class DMC3_OT_importer_filter(Operator, ImportHelper):
    """Import models and animations from DMC3 of any version"""
    bl_idname: str = "import_scene.dmc3_filter"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label: str = "DMC3 HDC models (.mod, .scm)"
    
    # ImportHelper mixin class uses this
    filename_ext: str = ".mod, .scm"

    filter_glob: StringProperty(
        default="",
        options={'HIDDEN'},
        maxlen=255  # Max internal buffer length, longer would be clamped.
    )

    type: EnumProperty(
        items=(
            ('MODEL', 'Model', 'model'),
            ('MOTION', 'Motion', 'motion')
        )
    )
    
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    def execute(self, context):
        try:
            setattr(context.scene, self.string_prop_name, bpy.path.relpath(self.filepath))
        except Exception:
            print(f"[DMC3] Failed to set filtered path for {self.string_prop_name}")

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filter_glob = "*" + ";*".join(self.ext)

        return super().invoke(context, event)

    @classmethod
    def add(cls, layout, scene, string_prop_name, *ext):
        cls.ext = ext
        cls.scene = scene
        cls.string_prop_name = string_prop_name

        col = layout.split(factor=.33)
        col.label(text=scene.bl_rna.properties[string_prop_name].name)

        row = col.row(align=True)

        if scene.bl_rna.properties[string_prop_name].subtype != 'NONE':
            row.label("ERROR: Change subtype of {} property to 'NONE'".format(string_prop_name), icon='ERROR')
        else:
            row.prop(scene, string_prop_name, icon_only=True)
            row.operator(cls.bl_idname, icon='FILEBROWSER')


