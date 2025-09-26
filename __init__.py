#__init__.py:
bl_info = {
    "name": "DMC3 Tools",
    "author": "K0BR4",
    "version": (0, 3, 0),
    "blender": (4, 0, 0),
    "location": "File > Import > DMC3 Tools",
    "description": "Import DMC3 models and animations (HD Collection compatible).",
    "category": "Import-Export",
}

import bpy
import importlib, sys

def safe_reload(module_name: str):
    m = sys.modules.get(module_name)
    if m:
        try:
            importlib.reload(m)
        except Exception as e:
            cs.log_warn(f"Could not reload {module_name}: {e}")

# Use relative import to guarantee we get the local `common` package inside the addon
try:
    from .common import scene as cs
except Exception as e:
    # fallback: avoid crashing registration if logging can't be imported
    cs = None
    print(f"[DMC3] Could not import local common.scene: {e}")

# Try to import DMC3 package and reload for dev iteration
try:
    from . import DMC3
    from .DMC3 import model, motion
    safe_reload(DMC3)
    safe_reload(DMC3.model)
    safe_reload(DMC3.motion)
except Exception as e:
    if cs:
        cs.log_error(f"DMC3 import failed: {e}")
    else:
        print(f"[DMC3] DMC3 import failed: {e}")

# Import the operator classes that actually exist in DMC3/operators.py
# Import operator classes and callback from operators module
from .DMC3.operators import (
    DMC3_OT_importer,
    DMC3_OT_importer_filter,
    update_filter,
)

def menu_func_import(self, context):
    self.layout.operator(DMC3_OT_importer.bl_idname, text="DMC3 Models (.mod/.scm/.mot)")

classes = (
    DMC3_OT_importer,
    DMC3_OT_importer_filter,
)

def register():
    # register classes once — tolerante a re-registro (recarregamento de addon)
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # já registrado (possivelmente por reload); tente desempilhar e registrar de novo
            try:
                bpy.utils.unregister_class(cls)
                bpy.utils.register_class(cls)
            except Exception:
                # se falhar, ignore para evitar travar a inicialização do addon
                pass
        except Exception:
            # qualquer outro erro não bloqueia os demais registros
            pass

    # append menu (protegido contra duplicação)
    try:
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    except Exception:
        pass

    # properties on Scene (only if not present) — centralizado aqui
    if not hasattr(bpy.types.Scene, "FileType"):
        bpy.types.Scene.FileType = bpy.props.EnumProperty(
            items=(
                ('MODEL', 'Model', 'model'),
                ('MOTION', 'Motion', 'motion')
            ),
            name="File type",
            default='MODEL',
            update=update_filter
        )

def unregister():
    # remove menu safely
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
        pass

    # unregister classes in reverse order
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    # remove scene property
    if hasattr(bpy.types.Scene, "FileType"):
        try:
            delattr(bpy.types.Scene, "FileType")
        except Exception:
            pass

if __name__ == "__main__":
    register()


