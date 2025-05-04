from __future__ import annotations

import sys
import os
import bpy
import importlib
from io import BufferedReader
from mathutils import Vector
from typing import TYPE_CHECKING

# allow imports from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

if TYPE_CHECKING:
    import DMC3.model
    import DMC3.motion

import common.io
from common.io import ReadFloat, ReadSInt16, ReadByte, ReadUByte

importlib.reload(common.io)

#=====================================================================
#   Generate faces from triangle strips
#=====================================================================
def GetTris(verts: list[Vector], nrmls: list[Vector], triSkip: list[int], numVerts: int) -> list:
    tris: list[tuple] = []
    p1: int = 0
    p2: int = 1
    p3: int
    wnd: int = 1 # winding order

    for i in range(2, numVerts):
        p3 = i

        if not triSkip[i]:
            # compute the triangle's facing direction
            vert1 = Vector( verts[p1] )
            vert2 = Vector( verts[p2] )
            vert3 = Vector( verts[p3] )

            # get edges for the basis
            faceEdge1 = vert3 - vert1
            faceEdge2 = vert2 - vert1
            faceEdge1.normalize()
            faceEdge2.normalize()

            # calculate the face normal
            z = faceEdge1.cross(faceEdge2)
            z.normalize()
            
            # add imported vertex normals together to get the face normal
            normal1 = Vector( nrmls[p1] )
            normal2 = Vector( nrmls[p2] )
            normal3 = Vector( nrmls[p3] )
            
            normal = Vector( normal1 + normal2 + normal3 )
            normal.normalize()

            # check whether the triangle is facing in the imported normals direction and flip it otherwise
            wnd = 1 if normal.dot(z) > 0.0 else -1

            tris.append( [p1, p3, p2] if wnd == 1 else [p1, p2, p3] ) # type: ignore


        p1 = p2
        p2 = p3
    

    return tris


#=====================================================================
#   Vertex decoding
#=====================================================================
def ParseVerts(self: DMC3.model.Mesh, f: BufferedReader, modelHdr) -> None:
    #POSITIONS
    f.seek(self.positionsOffs)
    self.positions = [ Vector([ReadFloat(f), ReadFloat(f), ReadFloat(f)]) for _ in range(self.vertCount) ]
 
    #NORMALS
    f.seek(self.normalsOffs)
    self.normals = [ Vector([ReadFloat(f), ReadFloat(f), ReadFloat(f)]) for _ in range(self.vertCount) ]
    
    #TEXTURE COORDINATES
    f.seek(self.UVsOffs)
    self.UVs = [ Vector([ReadSInt16(f)/4096., (1. - ReadSInt16(f)/4096.)]) for _ in range(self.vertCount) ]


    #BONE INDICES
    if modelHdr.Id != "SCM ":
        f.seek(self.boneIndiciesOffs)

        for _ in range(self.vertCount):
            ReadByte(f)
            self.boneIndicies.append( [ReadUByte(f)//4, ReadUByte(f)//4, ReadUByte(f)//4] )


        #BONE WEIGHTS
        f.seek(self.weightsOffs)

        for _ in range(self.vertCount):
            w = ReadSInt16(f)

            w1 = (w & 0x1f) / 31.
            w2 = ( (w >> 5) & 0x1f) / 31.
            w3 = ( (w >> 10) & 0x1f) / 31.

            self.triSkip.append( (w >> 15) & 1 )
            self.boneWeights.append( [w1, w2, w3] )

        # FACES
        self.faces = GetTris(self.positions, self.normals, self.triSkip, self.vertCount)

    # VERTEX COLOUR
    else:
        f.seek(self.uknOffs)

        for _ in range(self.vertCount):
            self.vertColour.append( (ReadUByte(f)/255., ReadUByte(f)/255., ReadUByte(f)/255., 1.) )
            self.triSkip.append(ReadUByte(f) & 2)

        # FACES
        self.faces = GetTris(self.positions, self.normals, self.triSkip, self.vertCount)