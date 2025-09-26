#common\import_setup.py:
from random import sample
import sys
import bpy
import os
import importlib
import mathutils
from mathutils import Matrix, Vector

def safe_reload(module_name: str):
    m = sys.modules.get(module_name)
    if m:
        try:
            importlib.reload(m)
        except Exception as e:
            cs.log_warn(f"Could not reload {module_name}: {e}")
# Path hack (if need to import sibling modules during development)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# relative imports inside the common package
from . import io as common_io
safe_reload(common_io)
from . import scene as cs

# Matrix
mat = Matrix([[1.0, 0.0, 0.0, 0.0],
              [0.0, 0.0, -1., 0.0],
              [0.0, 1.0, 0.0, 0.0],
              [0.0, 0.0, 0.0, 0.0]])

matId = Matrix([[1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 0.0]])

# Setup parsed models
def setup_model(context, filepath, Mod):

    # Setup collection
    fileName = os.path.basename(filepath)
    model_collection = bpy.data.collections.new(fileName)
    context.scene.collection.children.link(model_collection)

    # create an empty to parent the model to
    empty = bpy.data.objects.new(fileName, None)

    model_collection.objects.link(empty)

    empty.empty_display_size = 2
    empty.empty_display_type = 'SPHERE' 

    # Setup armature
    armature = bpy.data.armatures.new("Armature")
    armature_object = bpy.data.objects.new("Armature_object", armature)
    armature.show_axes = True
    armature.display_type = 'OCTAHEDRAL'
    # armature.show_names = True

    model_collection.objects.link(armature_object)
    context.view_layer.objects.active = armature_object
    armature_object.parent = empty
    armature_object.select_set(True)

    cs.safe_set_mode(context, armature_object, 'EDIT')

    # Setup bones
    joints = Mod.skeleton.bones

    for joint in joints:
        bone = armature.edit_bones.new(f"bone_{joint.idx}")
        bone.head = joint.transform
        bone.use_relative_parent = True

        if joint.parent != -1:
            bone.parent = armature.edit_bones[joint.parent]
            bone.head += bone.parent.head
    

    # calculate bone tails
    for bone in armature.edit_bones:
        children = bone.children
        
        if children:
            childrenPosAverage = Vector([.0, .0, .0])

            for c in children:
                childrenPosAverage += c.head

            childrenPosAverage /= len(children)

            bone.tail = childrenPosAverage.lerp(bone.head, 0.5) if children else bone.head + Vector((0.0, 0.01, 0.0))
            
        else:
            bone.tail = bone.head + (bone.head - bone.parent.head) * .5

    # Create view for manual alignment along baseline.
    bpy.ops.transform.create_orientation(name="BASELINE", overwrite=True)
    ### Set baseline
    slot = context.scene.transform_orientation_slots[0]
    # Save current orientation setting
    last_slot = slot.type
    # Set new orientation (custom_orientation isn't available until we set the type to a custom orientation)
    slot.type = 'BASELINE'
    slot.custom_orientation.matrix = mat.to_3x3()
    # Set orientation back to what it was
    # slot.type = last_slot

    # hack to get around blender not allowing 0-length bones
    # for bone in armature_object.pose.bones:
    #     bone.matrix_basis = mat

    for bone in armature.edit_bones:
        # cs.log_info(ff"{bone.name}\n{bone.matrix}\n\n")
        # bone.transform(mat)
        bone.tail = bone.head + Vector([.0, 1.0, .0])

        if bone.length <= 0.00005:
            bone.tail += Vector([.000001, .0, .0])
            # cs.log_info(ff"\n  {bone.name}, {bone.length}")

    # Apply transform on the armature object, not the data block
    # armature.transform(mat)
    armature_object.matrix_world = mat

    # Setup objects 
    for i, obj in enumerate(Mod.objects):

        objName = f"Object_{i}"
        object = bpy.data.objects.new(objName, None)
        model_collection.objects.link(object)
        object.parent = empty

        for j, msh in enumerate(obj.meshes):
            name = f"Object_{i}.Mesh_{j}"

            mesh_data = bpy.data.meshes.new(name)
            mesh_data.from_pydata(msh.positions, [], msh.faces)

            mesh_object = ( bpy.data.objects.new(name, mesh_data) )            

            mesh_object.parent = object
            model_collection.objects.link(mesh_object)

            # Apply normals
            custom_normals = []
            
            for face in mesh_data.polygons:
                
                for vert_index in face.vertices:
                    custom_normals.append(msh.normals[vert_index])

                face.use_smooth = True

            mesh_data.use_auto_smooth = True
            mesh_data.normals_split_custom_set(custom_normals)

            # Apply uvs
            if len(msh.UVs) != 0:
                mesh_data.uv_layers.new(name='UV_0') # 2.8 change
                uv_data = mesh_data.uv_layers[0].data
                
                for u in range( len(uv_data) ):
                    uv_data[u].uv = msh.UVs[mesh_data.loops[u].vertex_index]

                mesh_data.calc_tangents(uvmap = "UV_0")

            # Create vertex groups 
            for b in range(Mod.skeleton.boneCount):
                mesh_object.vertex_groups.new(name = f"bone_{b}")

            # Assign vertices to vertex groups
            for vert in mesh_data.vertices:
                v = vert.index
                bone_indices = msh.boneIndicies[v]
                weights = msh.boneWeights[v]

                for idx, b in enumerate(bone_indices):
                    # Normalizar b -> int
                    if isinstance(b, int):
                        bone_idx = b
                    else:
                        try:
                            bone_idx = int(b[0])
                        except Exception:
                            bone_idx = 0

                    # Clamp
                    if bone_idx >= len(mesh_object.vertex_groups):
                        import common.scene as cs
                        cs.log_warn(f"bone index {bone_idx} out of range for mesh {mesh_object.name}. Clamping to {len(mesh_object.vertex_groups)-1}")
                        bone_idx = max(0, len(mesh_object.vertex_groups) - 1)

                    vgroup = mesh_object.vertex_groups[bone_idx]
                    weight = weights[idx] if idx < len(weights) else 1.0
                    vgroup.add([v], weight, "REPLACE")

            # Link the armature to the object
            cs.safe_set_mode(context, armature_object, 'OBJECT')

            # object.parent = armature_object
            modifier = mesh_object.modifiers.new(type='ARMATURE', name="Armature")
            modifier.object = armature_object

    # rotate the model upright
    empty.rotation_euler = mathutils.Matrix.to_euler(mat, 'XYZ')

    # cs.log_info(f"\nPOSE MATS:\n")
    # for bone in armature_object.pose.bones:
    #     cs.log_info(ff"{bone.name}\n{bone.matrix}\n\n")
    #     cs.log_info(ff"Basis {bone.name}\n{bone.matrix_basis}\n\n")

#   Setup parsed animations
def clear_animations():
    for action in bpy.data.actions:
        action.user_clear()
        bpy.data.actions.remove(action)

def setup_animation(context, filepath, Mot):
    clear_animations()

    scene = bpy.data.scenes["Scene"]
    scene.render.fps = 60

    if len(bpy.data.actions) > 0:
        if scene.frame_start > Mot.startFrame:
            scene.frame_start = int(Mot.startFrame)
        
        if scene.frame_end < Mot.endFrame:
            scene.frame_end = int(Mot.endFrame)

    else:
        scene.frame_start = int(Mot.startFrame)
        scene.frame_end = int(Mot.endFrame)

    # Determine rig: use selected armature if present, otherwise search for the default Armature_object
    if getattr(context, 'object', None) is not None and getattr(context.object, 'type', '') == 'ARMATURE':
        rig = context.object
    else:
        rig = context.scene.objects.get("Armature_object")
        if rig is None:
            cs.log_error("Armature_object not found in scene; aborting animation setup.")
            return {'CANCELLED'}

    for bone in rig.pose.bones:
        # cs.log_info(fbone.name)
        bone.rotation_mode = "XYZ"

    fileName = os.path.basename(filepath)
    action = bpy.data.actions.new(fileName)

    for trackGroup in Mot.trackGroups:
        # cs.log_info(ftrackGroup.boneIdx)

        for track in trackGroup.tracks:
            fcurve = action.fcurves.new(data_path=track.transformType, index=track.trackIdx)
            keys = track.keys
            
            for i in range(1, len(keys)):
                frame_time_range = (keys[i].timeIndex - keys[i-1].timeIndex)
            
                for frame_time in range(keys[i-1].timeIndex, keys[i].timeIndex):
                    t = (float(frame_time) - keys[i-1].timeIndex) / frame_time_range
            
                    sample_value = track.SampleKeyframe(frame_time, i, t)
                    fcurve.keyframe_points.insert(frame_time, sample_value)

    ad = rig.animation_data_create()
    ad.action = action
    
    for window in context.window_manager.windows:
        screen = window.screen

        for area in screen.areas:
            if area.type == 'DOPESHEET_EDITOR':

                for region in area.regions:
                    if region.type == 'WINDOW':
                        with context.temp_override(window=window, area=area, region=region):
                            bpy.ops.action.view_all()
                        
                        return


