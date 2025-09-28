#DMC3\model.py:
from __future__ import annotations

import sys
import os
import re
import random
import importlib
from pathlib import Path

import struct
import bpy
import mathutils
from math import radians
from mathutils import Vector, Matrix

# Path Hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import internal modules
import common
from common.meshutils import ParseVerts
from common.io import (
    ReadSInt16, ReadSInt32, ReadSInt64,
    ReadUByte, ReadByte, ReadFloat, ReadString
)

importlib.reload(common.io)

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

    def __init__(self, f: BufferedReader, meshIdx: int, parentModel: "Model"):
        self.meshIdx = meshIdx
        self.f = f
        self.parentModel = parentModel
        self.vertCount = ReadSInt16(f)
        self.texInd = ReadSInt16(f)
        f.seek(12, 1)
        self.positionsOffs = ReadSInt64(f)
        self.normalsOffs = ReadSInt64(f)
        self.UVsOffs = ReadSInt64(f)

        if self.parentModel.Id != "SCM ":
            self.boneIndiciesOffs = ReadSInt64(f)
            self.weightsOffs = ReadSInt64(f)
            f.seek(8, 1)
        else:
            f.seek(16, 1)
            self.uknOffs = ReadSInt64(f)

        self.ukn = ReadSInt64(f)
        f.seek(8, 1)

        self.positions = []
        self.normals = []
        self.UVs = []
        self.boneIndicies = []
        self.boneWeights = []
        self.vertColour = []
        self.triSkip = []
        self.faces = []
        self.vertGrp = [None] * self.parentModel.boneCount


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

    def ParseMeshes(self, parentModel: "Model"):
        f = self.f
        f.seek(self.mshOffs)
        self.meshes = [Mesh(f, i, parentModel) for i in range(self.meshCount)]


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
        self.hierarchy = [ReadByte(f) for _ in range(boneCount)]

        # Collect hierarchy indices
        f.seek(base_offset + self.hierarchyOrderOffs)
        self.hierarchyOrder = [ReadByte(f) for _ in range(boneCount)]

        # Collect child object indices
        f.seek(base_offset + self.childIdxOffs)
        self.childIndices = [ReadByte(f) for _ in range(boneCount)]

        # Collect bone transforms
        f.seek(base_offset + self.transformsOffs)

        for i in range(boneCount):
            self.bones.append(Bone(Vector([ReadFloat(f), ReadFloat(f), ReadFloat(f)]), i))
            f.seek(0x14, os.SEEK_CUR)

        self.parents = [-1 for _ in range(boneCount)]
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
        self.objects = []
        self.skeleton: Skeleton

    def ParseObjects(self):
        self.f.seek(0x40)
        for i in range(self.objectCount):
            self.objects.append(Object(self.f, i))

    def ParseMeshes(self):
        for obj in self.objects:
            obj.ParseMeshes(self)

    def ParseVerts(self):
        for obj in self.objects:
            self.ParseObjectVerts(obj)

    def ParseObjectVerts(self, obj: Object):
        for mesh in obj.meshes:
            ParseVerts(mesh, self.f, self)

    def ParseSkeleton(self):
        self.f.seek(self.skeletonOffs)
        self.skeleton = Skeleton(self.f, self.boneCount)


#=====================================================================
basis_mat: Matrix = Matrix([
    [0.01, 0.0, 0.0, 0.0],
    [0.0, 0.01, 0.0, 0.0],
    [0.0, 0.0, 0.01, 0.0],
    [0.0, 0.0, 0.0, 1.0]
])

correction_mat: Matrix = Matrix([
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, -1.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 1.0]
])

correction_local = mathutils.Euler((radians(90), 0, radians(0))).to_matrix().to_4x4()
correction_global = mathutils.Euler((radians(-90), radians(0), 0)).to_matrix().to_4x4()

#=====================================================================
def setup_bones(context, armature: bpy.types.Armature, joints: list[Bone],
                armature_object: bpy.types.Object) -> list[bpy.types.EditBone]:
    bones: list[bpy.types.EditBone] = []

    bpy.ops.object.mode_set(mode='EDIT')

    for joint in joints:
        bone = armature.edit_bones.new(f"bone_{joint.idx}")
        bone.head = Vector([joint.position.x, joint.position.y, joint.position.z])
        bone.use_relative_parent = True
        bones.append(bone)

    for i, joint in enumerate(joints):
        bone = bones[i]
        if joint.parent != -1:
            bone.parent = bones[joint.parent]
            bone.head += bone.parent.head

    for bone in armature.edit_bones:
        if bone.children:
            avg = Vector((0.0, 0.0, 0.0))
            for child in bone.children:
                avg += child.head
            avg /= len(bone.children)
            bone.tail = avg.lerp(bone.head, 0.5 if len(bone.children) > 1 else 0.0)
        else:
            if bone.parent:
                bone.tail = bone.head + (bone.head - bone.parent.head) * 0.5
            else:
                bone.tail = bone.head + Vector((0.0, 10.0, 0.0))

        if bone.length <= 0.0005:
            bone.tail += Vector((0.0, 10.0, 0.0))

    if 'basis_mat' in globals():
        armature.transform(basis_mat)

    bpy.ops.object.mode_set(mode='OBJECT')
    return bones


#=====================================================================
def setup_objects(Mod: Model, model_collection: bpy.types.Collection,
                  armature_object: bpy.types.Object) -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []

    # Material para vertex colors (apenas para SCM sem texturas)
    material_vert_col: bpy.types.Material = bpy.data.materials.get("Baked Lighting")
    if material_vert_col is None:
        material_vert_col = bpy.data.materials.new(name="Baked Lighting")
        material_vert_col.use_nodes = True
        nodes = material_vert_col.node_tree.nodes
        # Limpar nós existentes
        nodes.clear()
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        vert_col_node = nodes.new(type='ShaderNodeVertexColor')
        vert_col_node.layer_name = "Baked Lighting"
        diffuse_node = nodes.new(type='ShaderNodeBsdfDiffuse')
        links = material_vert_col.node_tree.links
        links.new(vert_col_node.outputs['Color'], diffuse_node.inputs['Color'])
        links.new(diffuse_node.outputs['BSDF'], output_node.inputs['Surface'])
        
        # Organizar nós
        vert_col_node.location = (0, 0)
        diffuse_node.location = (300, 0)
        output_node.location = (600, 0)
        
        # Cor aleatória para o material Baked Lighting
        material_vert_col.diffuse_color = (
            random.uniform(0.2, 0.8),
            random.uniform(0.2, 0.8), 
            random.uniform(0.2, 0.8),
            1.0
        )

    for i, obj in enumerate(Mod.objects):
        for j, msh in enumerate(obj.meshes):
            name = f"Object:{i}_Mesh:{j}_Tex:{msh.texInd}"
            mesh_data = bpy.data.meshes.new(name)
            mesh_data.from_pydata(msh.positions, [], msh.faces)
            mesh_object = bpy.data.objects.new(name, mesh_data)

            if j > 0:
                mesh_object.parent = object
            else:
                object = mesh_object
                objects.append(object)

            model_collection.objects.link(mesh_object)
            bpy.context.view_layer.objects.active = mesh_object

            # Aplicar Auto Smooth
            mesh_data.use_auto_smooth = True
            mesh_data.auto_smooth_angle = radians(30)

            custom_normals = []
            for face in mesh_data.polygons:
                for vert_index in face.vertices:
                    custom_normals.append(msh.normals[vert_index])
                face.use_smooth = True
            mesh_data.normals_split_custom_set(custom_normals)

            # Verificar e criar UVs apenas se existirem dados de UV
            if hasattr(msh, 'UVs') and msh.UVs and len(msh.UVs) == len(mesh_data.vertices):
                try:
                    uv_layer = mesh_data.uv_layers.new(name="UV_0")
                    uv_data = uv_layer.data
                    for u, loop in enumerate(mesh_data.loops):
                        uv_data[u].uv = msh.UVs[loop.vertex_index]
                    
                    # Calcular tangentes apenas se a UV map foi criada com sucesso
                    # e se há faces no mesh
                    if len(mesh_data.polygons) > 0 and "UV_0" in mesh_data.uv_layers:
                        try:
                            mesh_data.calc_tangents(uvmap="UV_0")
                        except Exception as e:
                            print(f"AVISO: Não foi possível calcular tangentes para {name}: {e}")
                except Exception as e:
                    print(f"AVISO: Não foi possível criar UV map para {name}: {e}")
            else:
                print(f"AVISO: Dados de UV ausentes ou incompatíveis para {name}")

            for b in range(Mod.skeleton.boneCount):
                mesh_object.vertex_groups.new(name=f"bone_{b}")

            if Mod.Id != "SCM ":
                for vert in mesh_data.vertices:
                    v = vert.index
                    bone_indices = msh.boneIndicies[v]
                    weights = msh.boneWeights[v]
                    for idx, b in enumerate(bone_indices):
                        # Verificar se o índice do osso é válido antes de atribuir
                        if b < Mod.skeleton.boneCount and weights[idx] > 0:
                            try:
                                vgroup = mesh_object.vertex_groups[b]
                                vgroup.add([v], weights[idx], 'REPLACE')
                            except Exception as e:
                                print(f"AVISO: Não foi possível atribuir peso ao osso {b} para vértice {v}: {e}")
                        else:
                            if b >= Mod.skeleton.boneCount:
                                print(f"AVISO: Índice de osso {b} fora do range (max: {Mod.skeleton.boneCount-1}) para vértice {v}")
            else:
                # Para SCM, criar vertex colors mas NÃO aplicar material ainda
                # O material será aplicado posteriormente na seção de texturas
                vcol_layer = mesh_data.vertex_colors.new(name='Baked Lighting')
                for loop, col in zip(mesh_data.loops, vcol_layer.data):
                    col.color = msh.vertColour[loop.vertex_index]

            mesh_data.transform(basis_mat)
            bpy.ops.object.mode_set(mode='OBJECT')
            modifier = mesh_object.modifiers.new(type='ARMATURE', name="Armature")
            modifier.object = armature_object

        object.parent = armature_object

    return objects


#=====================================================================
def setup_model(context: bpy.types.Context, filepath: Path, Mod: Model) -> None:
    file_name = Path(filepath).name
    model_collection = bpy.data.collections.new(file_name)
    context.scene.collection.children.link(model_collection)

    armature = bpy.data.armatures.new("Armature")
    armature_object = bpy.data.objects.new("Armature_object", armature)
    armature_object.show_in_front = True
    armature.show_axes = True
    armature.display_type = 'STICK'

    model_collection.objects.link(armature_object)
    context.view_layer.objects.active = armature_object

    joints = Mod.skeleton.bones
    setup_bones(context, armature, joints, armature_object)

    objects = setup_objects(Mod, model_collection, armature_object)

    if Mod.Id != "MOD ":
        bpy.context.view_layer.objects.active = armature_object
        bpy.ops.object.mode_set(mode='POSE')
        for i, child_idx in enumerate(Mod.skeleton.childIndices):
            if child_idx != -1:
                bone = armature_object.pose.bones[f"bone_{i}"]
                obj = objects[child_idx]
                obj.parent_type = 'BONE'
                obj.parent = armature_object
                obj.parent_bone = bone.name
                obj.matrix_world = mathutils.Matrix.Translation(
                    (bone.matrix @ obj.matrix_local).translation)
        bpy.ops.object.mode_set(mode='OBJECT')

    armature_object.rotation_euler.rotate_axis('X', radians(90.))


#=====================================================================
def Import(context: bpy.types.Context, filepath: Path):
    with open(filepath, 'rb') as f:
        model = Model(f)
        model.ParseObjects()
        model.ParseMeshes()
        model.ParseVerts()
        model.ParseSkeleton()
        setup_model(context, filepath, model)

    # ---------- AUTO TEXTURE LOAD ----------

    def _extract_base_key(mod_path: Path) -> str:
        """Retorna a chave-base para procurar texturas"""
        name = mod_path.stem.lower()  # ex.: em028_001, plwp_guitar_002

        # padrão plwp_<arma>_NNN
        m = re.match(r'^(plwp_[a-z0-9]+)_[0-9]+$', name)
        if m:
            return m.group(1)  # plwp_guitar, plwp_sword2 etc.

        # padrão geral xxNNN_MMM
        m = re.match(r'^([a-z]{2}\d{3})_[0-9]+$', name)
        if m:
            return m.group(1)  # em028, pl015, st209 etc.

        # fallback: retorna tudo antes do último underline
        if '_' in name:
            return name.rsplit('_', 1)[0]
        return name

    def _find_index_for_mod(mod_path: Path, max_ancestors=6):
        """
        Procura um arquivo .index que contenha o nome do mod.
        Vai subindo até max_ancestors níveis e também procura recursivamente.
        Trata também nomes criados pelo extractor que contêm backslashes literal.
        """
        mod_simple = mod_path.name.split("\\")[-1]  # lida com nomes que já têm '\' dentro
        search_dirs = [mod_path.parent] + list(mod_path.parent.parents)[:max_ancestors]
        for anc in search_dirs:
            # procura índices normais
            for idx in anc.glob("*.index"):
                try:
                    txt = idx.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    continue
                if mod_simple in txt.splitlines():
                    return idx
            # procura arquivos cujo nome literal contém backslashes (extrator original no Windows)
            for f in anc.iterdir():
                if "\\" in f.name and f.name.endswith(".index"):
                    try:
                        txt = f.read_text(encoding='utf-8', errors='ignore')
                    except Exception:
                        continue
                    if mod_simple in txt.splitlines():
                        return f
        # busca recursiva no diretório do mod
        for idx in mod_path.parent.rglob("*.index"):
            try:
                if mod_simple in idx.read_text(encoding='utf-8', errors='ignore').splitlines():
                    return idx
            except Exception:
                continue
        return None
    
    def _find_file_by_simple_name(simple_name: str, root: Path):
        """
        Procura por qualquer ficheiro cujo nome contenha "simple_name" sob 'root'.
        (isso também cobre os arquivos gerados com backslashes como parte do nome).
        Retorna Path ou None.
        """
        for f in root.rglob("*"):
            try:
                if simple_name in f.name:
                    return f
            except Exception:
                continue
        return None

    def _collect_textures_from_index(index_path: Path):
        """
        Lê o index e constrói uma lista ordenada de arquivos de textura (Paths).
        Expande entries do tipo 'folder' (PTX) lendo sub-indexes.
        """
        base_dir = index_path.parent
        try:
            lines = index_path.read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception:
            return []
    
        textures = []
        for line in lines:
            if not line or line == "PNST":
                continue
            parts = line.split()
            name = parts[0]
            # entrada direta .dds/.tm2 no index
            if name.lower().endswith((".dds", ".tm2")):
                f = _find_file_by_simple_name(name, base_dir)
                if f:
                    textures.append(f)
                continue
            # folder / ptx / ipum -> expand procurando um sub-index
            if len(parts) > 1 and parts[-1] in ("folder", "vid") or "folder" in line.lower():
                folder_name = name
                # procura sub-indexes que mencionem esse folder_name
                sub_idx_candidates = list(base_dir.rglob(f"*{folder_name}*.index"))
                for sub_idx in sub_idx_candidates:
                    try:
                        sub_lines = sub_idx.read_text(encoding='utf-8', errors='ignore').splitlines()
                    except Exception:
                        continue
                    for sline in sub_lines:
                        sline = sline.strip()
                        if not sline:
                            continue
                        if sline.lower().endswith((".dds", ".tm2")):
                            f = _find_file_by_simple_name(sline, base_dir)
                            if f:
                                textures.append(f)
        # deduplicate while preserving order
        seen = set(); unique = []
        for t in textures:
            s = str(t)
            if s not in seen:
                seen.add(s); unique.append(t)
        return unique
    
    def _convert_tm2_to_dds(tm2_path: Path) -> Path | None:
        """
        Conversão simples TM2→DDS: procura assinatura 'DDS ' no arquivo TM2 e grava a partir daí.
        Se não encontrar, recorta um header provável (112 bytes).
        Retorna Path para .dds ou None.
        """
        try:
            data = tm2_path.read_bytes()
            idx = data.find(b"DDS ")
            if idx == -1:
                idx = 112
            dds_out = tm2_path.with_suffix(".dds")
            dds_out.write_bytes(data[idx:])
            return dds_out
        except Exception as e:
            print(f"[TM2->DDS] Falha em {tm2_path}: {e}")
            return None

    # --- executar busca/atribuição executando após setup_model(...)
    model_collection_name = Path(filepath).name
    # buscar a collection criada por setup_model (ela foi criada com o nome do arquivo)
    model_collection = bpy.data.collections.get(model_collection_name)
    if model_collection is None:
        # fallback: procurar collection com nome começando pelo filename
        for c in bpy.data.collections:
            if c.name == model_collection_name or c.name.startswith(model_collection_name):
                model_collection = c
                break
    
    # localiza index do pac (ex.: em028.index) que descreve este mod
    base_key = _extract_base_key(Path(filepath))
    index_path = _find_index_for_mod(Path(filepath))
    textures = []
    
    if index_path:
        all_textures = _collect_textures_from_index(index_path)
        # filtrar apenas as texturas que contêm a base_key
        textures = [t for t in all_textures if base_key in t.stem.lower()]
        print(f"[DMC3 Import] Encontradas {len(textures)} texturas para base_key '{base_key}'")
    else:
        # tentativas adicionais: procurar qualquer .index no parent
        print(f"[DMC3 Import] Procurando por arquivos .index no diretório...")
        for cand in Path(filepath).parent.glob("*.index"):
            all_textures = _collect_textures_from_index(cand)
            filtered_textures = [t for t in all_textures if base_key in t.stem.lower()]
            if filtered_textures:
                textures = filtered_textures
                index_path = cand
                print(f"[DMC3 Import] Encontradas {len(textures)} texturas no índice {cand.name}")
                break

    # Material para vertex colors (apenas para SCM sem texturas)
    material_vert_col: bpy.types.Material = bpy.data.materials.get("Baked Lighting")
    if material_vert_col is None:
        material_vert_col = bpy.data.materials.new(name="Baked Lighting")
        material_vert_col.use_nodes = True
        nodes = material_vert_col.node_tree.nodes
        # Limpar nós existentes
        nodes.clear()
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        vert_col_node = nodes.new(type='ShaderNodeVertexColor')
        vert_col_node.layer_name = "Baked Lighting"
        diffuse_node = nodes.new(type='ShaderNodeBsdfDiffuse')
        links = material_vert_col.node_tree.links
        links.new(vert_col_node.outputs['Color'], diffuse_node.inputs['Color'])
        links.new(diffuse_node.outputs['BSDF'], output_node.inputs['Surface'])
        
        # Organizar nós
        vert_col_node.location = (0, 0)
        diffuse_node.location = (300, 0)
        output_node.location = (600, 0)
        
        # Cor aleatória para o material Baked Lighting
        material_vert_col.diffuse_color = (
            random.uniform(0.2, 0.8),
            random.uniform(0.2, 0.8), 
            random.uniform(0.2, 0.8),
            1.0
        )

    if not textures:
        print(f"[DMC3 Import] Nenhuma textura encontrada para base_key '{base_key}'; verifique se o .pac foi extraido com extract_pac.py")
        # Tentar carregar qualquer textura disponível como fallback
        if index_path:
            textures = _collect_textures_from_index(index_path)
            print(f"[DMC3 Import] Carregando {len(textures)} texturas disponíveis como fallback")
    else:
        # cache de imagens já carregadas
        image_cache = {}
        # aplicar texturas por mesh: nomes gerados por setup_objects:
        for i_obj, obj in enumerate(model.objects):
            for j_msh, msh in enumerate(obj.meshes):
                tex_index = msh.texInd if hasattr(msh, "texInd") else None
                # defensivo: algumas entradas usam -1 ou valores inválidos
                if tex_index is None or tex_index < 0:
                    chosen_tex = textures[0] if textures else None
                else:
                    # se tex_index estiver dentro do range de textures -> pega direto,
                    # senão usa modulo como fallback
                    if tex_index < len(textures):
                        chosen_tex = textures[tex_index]
                    else:
                        chosen_tex = textures[tex_index % len(textures)] if textures else None
    
                if chosen_tex is None:
                    print(f"[DMC3 Import] Nenhuma textura disponível para mesh {i_obj}_{j_msh}")
                    # Para SCM sem textura, aplicar material de vertex colors
                    if model.Id == "SCM ":
                        expected_name = f"Object:{i_obj}_Mesh:{j_msh}_Tex:{msh.texInd}"
                        mesh_obj = None
                        if model_collection:
                            mesh_obj = model_collection.objects.get(expected_name)
                        if mesh_obj is None:
                            # fallback: procurar por nome que comece igual
                            for o in (model_collection.objects if model_collection else bpy.data.objects):
                                if o.name.startswith(f"Object:{i_obj}_Mesh:{j_msh}"):
                                    mesh_obj = o
                                    break
                        if mesh_obj and mesh_obj.type == 'MESH':
                            # Aplicar material de vertex colors apenas se não houver materiais
                            if not mesh_obj.data.materials:
                                mesh_obj.data.materials.append(material_vert_col)
                                print(f"[DMC3 Import] Material Baked Lighting aplicado a {mesh_obj.name}")
                    continue
    
                # se for tm2 converte
                if chosen_tex.suffix.lower() == ".tm2":
                    print(f"[DMC3 Import] Convertendo TM2 para DDS: {chosen_tex}")
                    dds_p = _convert_tm2_to_dds(chosen_tex)
                    if dds_p:
                        chosen_tex = dds_p
    
                # carrega/recicla image
                key = str(chosen_tex)
                if key in image_cache:
                    img = image_cache[key]
                else:
                    try:
                        print(f"[DMC3 Import] Carregando textura: {chosen_tex}")
                        img = bpy.data.images.load(str(chosen_tex))
                    except Exception as e:
                        print(f"[DMC3 Import] Erro carregando imagem {chosen_tex}: {e}")
                        continue
                    image_cache[key] = img
    
                # prepara material - usar nome baseado na textura
                texture_name = chosen_tex.stem  # Nome do arquivo sem extensão
                mat_name = f"DMC3_Mat_{texture_name}"
                
                # Verificar se o material já existe para reutilizar
                mat = bpy.data.materials.get(mat_name)
                if mat is None:
                    mat = bpy.data.materials.new(name=mat_name)
                    mat.use_nodes = True
                    nodes = mat.node_tree.nodes
                    links = mat.node_tree.links
    
                    # Limpar nós existentes
                    nodes.clear()
    
                    # Criar novos nós
                    output_node = nodes.new(type='ShaderNodeOutputMaterial')
                    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
                    tex_node = nodes.new(type='ShaderNodeTexImage')
                    tex_node.image = img
    
                    # Configurar Roughness para 1.0
                    bsdf.inputs['Roughness'].default_value = 1.0
    
                    # Configurar IOR para 1.0
                    bsdf.inputs['IOR'].default_value = 1.0
    
                    # Conectar nós
                    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
                    links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
                    links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
    
                    # Organizar nós com posicionamento adequado
                    tex_node.location = (0, 0)
                    bsdf.location = (300, 0)
                    output_node.location = (600, 0)
                    
                    # Adicionar cor aleatória ao material
                    mat.diffuse_color = (
                        random.uniform(0.2, 0.8),
                        random.uniform(0.2, 0.8), 
                        random.uniform(0.2, 0.8),
                        1.0
                    )
    
                    print(f"[DMC3 Import] Criado material: {mat_name}")
    
                # buscar o objeto mesh criado na collection e aplicar o material
                expected_name = f"Object:{i_obj}_Mesh:{j_msh}_Tex:{msh.texInd}"
                mesh_obj = None
                if model_collection:
                    mesh_obj = model_collection.objects.get(expected_name)
                if mesh_obj is None:
                    # fallback: procurar por nome que comece igual
                    for o in (model_collection.objects if model_collection else bpy.data.objects):
                        if o.name.startswith(f"Object:{i_obj}_Mesh:{j_msh}"):
                            mesh_obj = o
                            break
                if mesh_obj and mesh_obj.type == 'MESH':
                    # Verificar se o material já está aplicado
                    material_already_applied = False
                    for existing_mat in mesh_obj.data.materials:
                        if existing_mat and existing_mat.name == mat_name:
                            material_already_applied = True
                            break
                    
                    if not material_already_applied:
                        # Se já houver materiais, substituir o primeiro, senão adicionar
                        if mesh_obj.data.materials:
                            mesh_obj.data.materials[0] = mat
                        else:
                            mesh_obj.data.materials.append(mat)
                        print(f"[DMC3 Import] Material {mat_name} aplicado a {mesh_obj.name}")
    
    print("[DMC3 Import] Texture assignment finished.")
    # ---------- FIM AUTO TEXTURE LOAD ----------

    return {'FINISHED'}


