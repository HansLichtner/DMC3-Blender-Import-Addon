from __future__ import annotations

import sys
import os
from pathlib import Path
import imp
import random

import bpy
import mathutils
from mathutils import Vector, Matrix
from math import radians

from common.meshutils import ParseVerts
from common.io import (
    ReadSInt16, ReadSInt32, ReadSInt64,
    ReadUByte, ReadByte, ReadFloat, ReadString
)
      
#=====================================================================
#   Mesh
#=====================================================================
class Mesh:
    f: BufferedReader
    meshIdx: int
    vertCount: uint16
    texInd: uint16
    positionsOffs: offs_t
    normalsOffs: offs_t
    UVsOffs: offs_t
    boneIndiciesOffs: offs_t
    weightsOffs: offs_t
    uknOffs: offs_t
    ukn: ubyte
    positions: list[Vector]
    normals: list[Vector]
    UVs: list[Vector]
    boneIndicies: list[tuple]
    boneWeights: list[tuple]
    vertColour: list[tuple]
    triSkip: list[tuple]
    faces: list
    vertGrp: list


    def __init__(self, f: BufferedReader, meshIdx: int):
        self.meshIdx = meshIdx
        self.f = f
        self.vertCount = ReadSInt16(f)
        self.texInd = ReadSInt16(f)
        f.seek(12, 1)
        self.positionsOffs = ReadSInt64(f)
        self.normalsOffs = ReadSInt64(f)
        self.UVsOffs = ReadSInt64(f)
        
        if model.Id != "SCM ":
            self.boneIndiciesOffs = ReadSInt64(f)
            self.weightsOffs = ReadSInt64(f)
            f.seek(8, 1)
        else:
            f.seek(16, 1)
            self.uknOffs = ReadSInt64(f)
        
        self.ukn = ReadSInt64(f)
        f.seek(8, 1)
       
        self.positions = [Vector]*self.vertCount
        self.normals = []
        self.UVs = []
        self.boneIndicies = []
        self.boneWeights = []
        self.vertColour = []
        self.triSkip = []
        self.faces = []
        self.vertGrp = [None]*model.boneCount

        
    def ParseVerts(self):
        meshutils.ParseVerts(self, self.f, model)
        
    
#=====================================================================
#   Object
#=====================================================================
class Object:
    f: BufferedReader
    objectIdx: int
    meshCount: ubyte
    ukn: ubyte
    numVerts: uint16
    mshOffs: offs_t
    flags: uint32
    X: float
    Y: float
    Z: float
    radius: float
    meshes: list[Mesh]


    def __init__(self, f: BufferedReader, objectIdx: int):
        self.f = f
        self.objectIdx = objectIdx
        self.meshCount = ReadByte(f)
        self.ukn = ReadByte(f)
        self.numVerts = ReadSInt16(f)
        ReadSInt32(f)
        self.mshOffs = ReadSInt64(f)
        self.flags = ReadSInt32(f)
        f.seek(28, 1)
        self.X = ReadFloat(f)
        self.Y = ReadFloat(f)
        self.Z = ReadFloat(f)
        self.radius = ReadFloat(f)
        # self.meshes = []


    def ParseMeshes(self):
        f = self.f
        f.seek(self.mshOffs)

        self.meshes = [ Mesh(f, i) for i in range(self.meshCount) ]


    def ParseVerts(self):
        for mesh in self.meshes:
            mesh.ParseVerts()


#=====================================================================
#   Skeleton
#=====================================================================
class Bone:
    position: Vector
    idx: int
    parent: Bone

    
    def __init__(self, vec: Vector, idx: int):
        self.position = vec
        self.idx = idx
        self.parent = None


class Skeleton:
    bones: list[Bone]
    
    
    def __init__(self, f: BufferedReader, boneCount: int):
        base_offset = f.tell()
        self.f = f
        self.boneCount = boneCount
        self.hierarchyOffs = ReadSInt32(f)
        self.hierarchyOrderOffs = ReadSInt32(f)
        self.childIdxOffs = ReadSInt32(f)
        self.transformsOffs = ReadSInt32(f)
        self.bones = []

        # Collect bone hierarchy parents
        f.seek(base_offset + self.hierarchyOffs)
        self.hierarchy = [ ReadByte(f) for _ in range(boneCount) ]

        # Collect hierarchy indices
        f.seek(base_offset + self.hierarchyOrderOffs)
        self.hierarchyOrder = [ ReadByte(f) for _ in range(boneCount) ]

        # Collect child object indices
        f.seek(base_offset + self.childIdxOffs)
        self.childIndices = [ ReadByte(f) for _ in range(boneCount) ]

        # Collect bone transforms
        f.seek(base_offset + self.transformsOffs)

        for i in range(boneCount):
            self.bones.append( Bone( Vector( [ReadFloat(f), ReadFloat(f), ReadFloat(f)] ), i) )
            f.seek(0x14, os.SEEK_CUR)

        # remap the ownership
        self.parents = [ -1 for _ in range(boneCount)]

        for i in range(boneCount):
            self.bones[self.hierarchyOrder[i]].parent = self.hierarchy[i]


#=====================================================================
#   Model file
#=====================================================================
class Model:
    objectCount: ubyte
    objects: list[Object]
    
    
    def __init__(self, f: BufferedReader):
        self.f = f
        self.Id = ReadString(f, 4)
        self.version = ReadFloat(f)
        self.padding = ReadSInt64(f)
        self.objectCount = ReadUByte(f)
        self.boneCount = ReadByte(f)
        self.numTex = ReadByte(f)
        self.uknByte = ReadByte(f)
        self.ukn = ReadSInt32(f)
        self.ukn2 = ReadSInt64(f)
        self.skeletonOffs = ReadSInt64(f)
        self.objects = [] * self.objectCount
        self.skeleton: Skeleton


    def ParseObjects(self):
        f = self.f
        f.seek(0x40)

        for i in range(self.objectCount):
            self.objects.append( Object(f, i) )


    def ParseMeshes(self):
        for obj in self.objects:
            obj.ParseMeshes()
        

    def ParseVerts(self):
        for obj in self.objects:
            obj.ParseVerts()


    def ParseSkeleton(self):
        self.f.seek(self.skeletonOffs)
        self.skeleton = Skeleton(self.f, self.boneCount)

#=====================================================================
#region
#=====================================================================
basis_mat: Matrix = Matrix([
    [0.01, 0.0, 0.0, 0.0], 
    [0.0, 0.01, 0.0, 0.0], 
    [0.0, 0.0, 0.01, 0.0], 
    [0.0, 0.0, 0.0, 0.0]
])

correction_mat: Matrix = Matrix([
    [1.0, 0.0, 0.0, 0.0], 
    [0.0, 0.0, -1.0, 0.0], 
    [0.0, 1.0, 0.0, 0.0], 
    [0.0, 0.0, 0.0, 0.0]
])

# Local and global correction rotations
correction_local = mathutils.Euler((radians(90), 0, radians(0))).to_matrix().to_4x4()
correction_global = mathutils.Euler((radians(-90), radians(0), 0)).to_matrix().to_4x4()

#=====================================================================
#   Setup armature
#=====================================================================
def setup_bones(context, armature: bpy.types.Armature, joints: list[Bone], armature_object: bpy.types.Object) -> list[bpy.types.EditBone]:
    
    bones: list[bpy.types.EditBone] = []

    # Switch to Edit mode to create and modify bones
    bpy.ops.object.mode_set(mode='EDIT')

    # Create bones based on joint data
    for joint in joints:
        bone = armature.edit_bones.new(f"bone_{joint.idx}")
        bone.head = Vector([joint.position.x, joint.position.y, joint.position.z])
        bone.use_relative_parent = True
        bones.append(bone)

    # Set parent-child relationships
    for i, joint in enumerate(joints):
        bone: bpy.types.EditBone = armature.edit_bones[i]
        if joint.parent != -1:
            bone.parent = bones[joint.parent]
            bone.head += bone.parent.head

    # Calculate bone tails based on child positions or parent relationship
    for bone in armature.edit_bones:
        children = bone.children
        
        if children:
            # Average the positions of child bones
            child_pos_avg = Vector([0.0, 0.0, 0.0])
            for child in children:
                child_pos_avg += child.head

            child_pos_avg /= len(children)
            bone.tail = child_pos_avg.lerp(bone.head, 0.5 if len(children) > 1 else 0.0)
        else:
            # If no children, use the parent to set tail position
            bone.tail = bone.head + (bone.head - bone.parent.head) * 0.5

        # Ensure bone length is reasonable (avoid zero-length bones)
        if bone.length <= 0.0005:
            bone.tail += Vector([0.000, 10.000, 0.0])

    # Apply basis matrix transformation
    armature.transform(basis_mat)
    
    # Switch back to Object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return bones

#=====================================================================
# Setup objects 
#=====================================================================
def setup_objects(Mod: Model, model_collection: bpy.types.Collection, armature_object: bpy.types.Object) -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []
    
    # material: bpy.types.Material = bpy.data.materials.get("Material") or bpy.data.materials.new(name="Material")
    
    material_vert_col: bpy.types.Material = bpy.data.materials.get("Baked Lighting")
    
    if material_vert_col is None:
        material_vert_col: bpy.types.Material = bpy.data.materials.new(name="Baked Lighting")
        material_vert_col.use_nodes = True
        nodes: bpy.types.Nodes = material_vert_col.node_tree.nodes
        # bsdf: bpy.types.Node = nodes.get('Principled BSDF')
        mat_out: bpy.types.Node = nodes["Material Output"]

        vert_col_node: bpy.types.Node = nodes.new(type='ShaderNodeVertexColor')
        vert_col_node.layer_name = "Baked Lighting"
        
        links: bpy.types.NodeLinks = material_vert_col.node_tree.links
        # link: bpy.types.NodeLink = links.new(vert_col_node.outputs[0], bsdf.inputs[0])
        link: bpy.types.NodeLink = links.new(vert_col_node.outputs[0], mat_out.inputs[0])
        # bsdf.inputs[3].default_value = 1.
    

    for i, obj in enumerate(Mod.objects):
        # objName: str = f"Object:{i}_Mesh:0"
        object: bpy.types.Object

        for j, msh in enumerate(obj.meshes):
            name: str = f"Object:{i}_Mesh:{j}_Tex:{msh.texInd}"

            mesh_data: bpy.types.Mesh = bpy.data.meshes.new(name)
            mesh_data.from_pydata(msh.positions, [], msh.faces)

            mesh_object: bpy.types.Object = ( bpy.data.objects.new(name, mesh_data) )            

            if j > 0:
                mesh_object.parent = object
            
            else:
                object = mesh_object
                objects.append(object)
                
            model_collection.objects.link(mesh_object)
            
            bpy.context.view_layer.objects.active = mesh_object
            

            # Apply normals
            custom_normals: list = []
            
            for face in mesh_data.polygons:
                
                for vert_index in face.vertices:
                    custom_normals.append(msh.normals[vert_index])

                face.use_smooth = True


            # mesh_data.use_auto_smooth = True
            mesh_data.normals_split_custom_set(custom_normals)


            # Apply uvs
            if len(msh.UVs):
                mesh_data.uv_layers.new(name='UV_0') # 2.8 change
                uv_data: bpy.types.bpy_prop_collection[bpy.types.MeshUVLoop] = mesh_data.uv_layers[0].data
                
                for u in range( len(uv_data) ):
                    uv_data[u].uv = msh.UVs[mesh_data.loops[u].vertex_index]

                mesh_data.calc_tangents(uvmap = "UV_0")


            # Create vertex groups 
            for b in range(Mod.skeleton.boneCount):
                mesh_object.vertex_groups.new(name = f"bone_{b}")


            # Assign vertices to vertex groups
            if Mod.Id != "SCM ":
                
                for vert in mesh_data.vertices:
                    v = vert.index
                    bone_indices = msh.boneIndicies[v]
                    weights = msh.boneWeights[v]

                    for idx, b in enumerate(bone_indices):
                        vgroup = mesh_object.vertex_groups[b]
                        vgroup.add([v], weights[idx], 'REPLACE')

                # Add a material with a random colour
                material: bpy.types.Material = bpy.data.materials.new(name=mesh_object.name)
                material.diffuse_color = [random.uniform(.0, 1.) for i in range(3)] + [1.]
                mesh_data.materials.append(material)
                
            # Set vertex colour for stages and effects
            else:
                vcol_layer = mesh_data.vertex_colors.new(name='Baked Lighting')
                
                for loop, col in zip(mesh_data.loops, vcol_layer.data):
                    col.color = msh.vertColour[loop.vertex_index]
                    
                mesh_data.materials.append(material_vert_col)


            mesh_data.transform(basis_mat)

            # Link the armature to the object
            bpy.ops.object.mode_set(mode='OBJECT')

            # object.parent = armature_object
            modifier = mesh_object.modifiers.new(type='ARMATURE', name="Armature")
            modifier.object = armature_object


        object.parent = armature_object
        
        
    return objects

#=====================================================================
#   Setup parsed models
#=====================================================================
def setup_model(context: bpy.types.Context, filepath: Path, Mod: Model) -> None:
    # Setup collection
    file_name: str = Path(filepath).name
    model_collection: bpy.types.Collection = bpy.data.collections.new(file_name)
    context.scene.collection.children.link(model_collection)

    # Setup armature
    armature: bpy.types.Armature = bpy.data.armatures.new("Armature")
    armature_object: bpy.types.Object = bpy.data.objects.new("Armature_object", armature)
    armature.show_axes = True
    armature.display_type = 'OCTAHEDRAL'

    model_collection.objects.link(armature_object)
    context.view_layer.objects.active = armature_object

    # Setup bones
    joints: list[Bone] = Mod.skeleton.bones
    bones: list[bpy.types.EditBone] = setup_bones(context, armature, joints, armature_object)

    # Setup objects
    objects: list[bpy.types.Object] = setup_objects(Mod, model_collection, armature_object)

    if Mod.Id != "MOD ":
        bpy.context.view_layer.objects.active = armature_object
        bpy.ops.object.mode_set(mode='POSE')

        for i, child_idx in enumerate(Mod.skeleton.childIndices):
            if child_idx != -1:
                bone: bpy.types.PoseBone = armature_object.pose.bones[f"bone_{i}"]
                obj: bpy.types.Object = objects[child_idx]

                obj.parent_type = 'BONE'
                obj.parent = armature_object
                obj.parent_bone = bone.name
                obj.matrix_world = mathutils.Matrix.Translation((bone.matrix @ obj.matrix_local).translation)

        bpy.ops.object.mode_set(mode='OBJECT')

    # Rotate the model upright
    armature_object.rotation_euler.rotate_axis('X', radians(90.))

#=====================================================================
#   Import
#=====================================================================
def Import(context: bpy.types.Context, filepath: pathlib.Path):
    with open(filepath, 'rb') as f:

        # print("\nImporting model...")
        
        global model
        model = Model(f)
        model.ParseObjects()
        model.ParseMeshes()
        model.ParseVerts()
        model.ParseSkeleton()

        setup_model(context, filepath, model)
        
        # print("\nDone!\n")


    return {'FINISHED'}

