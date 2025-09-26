#common\meshutils.py:
from __future__ import annotations
from io import BufferedReader, BufferedWriter
from mathutils import Vector
from typing import TYPE_CHECKING

# relative import to the common package
from .io import ReadFloat, ReadSInt16, ReadByte, ReadUByte
from . import scene as cs

if TYPE_CHECKING:
    # use relative import for type checking
    from ..DMC3 import model

# Triangle strip to tris
def GetTris(verts: list[Vector], nrmls: list[Vector], triSkip: list[int], numVerts: int) -> list:
    tris = []
    p1, p2 = 0, 1
    wnd = 1
    for i in range(2, numVerts):
        p3 = i
        if not triSkip[i]:
            v1, v2, v3 = Vector(verts[p1]), Vector(verts[p2]), Vector(verts[p3])
            faceEdge1 = (v3 - v1).normalized()
            faceEdge2 = (v2 - v1).normalized()
            z = faceEdge1.cross(faceEdge2).normalized()
            normal = (Vector(nrmls[p1]) + Vector(nrmls[p2]) + Vector(nrmls[p3])).normalized()
            wnd = 1 if normal.dot(z) > 0.0 else -1
            tris.append([p1, p3, p2] if wnd == 1 else [p1, p2, p3])
        p1, p2 = p2, p3
    return tris

# Vertex decoding
def ParseVerts(self: DMC3.model.Mesh, f: BufferedReader, modelHdr) -> None:
    # positions
    f.seek(self.positionsOffs)
    self.positions = [Vector([ReadFloat(f), ReadFloat(f), ReadFloat(f)]) for _ in range(self.vertCount)]

    # normals
    f.seek(self.normalsOffs)
    self.normals = [Vector([ReadFloat(f), ReadFloat(f), ReadFloat(f)]) for _ in range(self.vertCount)]

    # UVs
    f.seek(self.UVsOffs)
    self.UVs = [Vector([ReadSInt16(f)/4096., 1. - ReadSInt16(f)/4096.]) for _ in range(self.vertCount)]

    # bone indices / weights
    if modelHdr.Id != "SCM ":
        f.seek(self.boneIndiciesOffs)

        def _decode_index(raw, bone_count):
            # Alguns ficheiros codificam bone index como raw*4. Tentamos //4,
            # se exceder bone_count tentamos raw cru, por fim aplicamos clamp.
            idx = raw // 4
            if bone_count and idx >= bone_count:
                if raw < bone_count:
                    idx = raw
                else:
                    idx = max(0, bone_count - 1)
            return idx

        for _ in range(self.vertCount):
            ReadByte(f)  # padding/unknown
            raw0 = ReadUByte(f)
            raw1 = ReadUByte(f)
            raw2 = ReadUByte(f)

            bone_count = getattr(modelHdr, "boneCount", 0)
            i0 = _decode_index(raw0, bone_count)
            i1 = _decode_index(raw1, bone_count)
            i2 = _decode_index(raw2, bone_count)

            self.boneIndicies.append([i0, i1, i2])

        f.seek(self.weightsOffs)
        for _ in range(self.vertCount):
            w = ReadSInt16(f)
            w1, w2, w3 = (w & 0x1f)/31., ((w >> 5) & 0x1f)/31., ((w >> 10) & 0x1f)/31.
            self.triSkip.append((w >> 15) & 1)
            self.boneWeights.append([w1, w2, w3])
        self.faces = GetTris(self.positions, self.normals, self.triSkip, self.vertCount)


