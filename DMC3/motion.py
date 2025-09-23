from __future__ import annotations

import os
import sys
import bpy
import importlib
import math

from enum import IntEnum
from io import BufferedReader
from mathutils import Vector, Matrix, Euler
from typing import NewType

# Path Hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import and reload common utilities
import common
from common.io import ReadUInt16, ReadUInt32, ReadFloat, ReadSInt32
from common.scene import frame_timeline
importlib.reload(common.io)

#=====================================================================

# Track type flags
class TrackFlags(IntEnum):
    TRANSLATION_X = 1 << 8
    TRANSLATION_Y = 1 << 7
    TRANSLATION_Z = 1 << 6
    ROTATION_X    = 1 << 5
    ROTATION_Y    = 1 << 4
    ROTATION_Z    = 1 << 3
    SCALE_X       = 1 << 2
    SCALE_Y       = 1 << 1
    SCALE_Z       = 1 << 0

# Compression types
class Compression(IntEnum):
    LINEAR_FLOAT32   = 0
    HERMITE_FLOAT32  = 1
    LINEAR_INT16     = 2
    HERMITE_INT16    = 3

# Track types
class TrackType(IntEnum):
    POSITION = 0
    ROTATION = 1
    SCALE    = 2

Position = NewType('Position', TrackType.POSITION)
Rotation = NewType('Rotation', TrackType.ROTATION)
Scale    = NewType('Scale', TrackType.SCALE)

# Axes
class Axis(IntEnum):
    X = 0
    Y = 1
    Z = 2

AxisX = NewType('AxisX', Axis.X)
AxisY = NewType('AxisY', Axis.Y)
AxisZ = NewType('AxisZ', Axis.Z)
        
EPSILON_16 = (0.000015259022) # 1./65535.

#=====================================================================
#   Hermite spline interpolation
#=====================================================================
def Hermite(currentFrameTime: float, p0_value: float, p0_time: float, p0_outTangent: float, p1_value: float, p1_time: float, p1_inTangent: float) -> float:
    t: float = currentFrameTime - p0_time
    timeStep: float = 1.0 / (p1_time - p0_time)
    time0a: float = t * t * (timeStep * timeStep)
    time1a: float = t * t * timeStep
    tCubed: float = time0a * t

    return (t + tCubed - time1a - time1a) * p0_outTangent \
         + (timeStep * tCubed + timeStep * tCubed - time0a * 3.0 + 1.0) * p0_value \
         + (time0a * 3.0 - (timeStep * tCubed + timeStep * tCubed)) * p1_value \
         + (tCubed - time1a) * p1_inTangent

# Adicione esta função de interpolação linear:
def linear_interpolate(a: float, b: float, factor: float) -> float:
    return a + (b - a) * factor

#=====================================================================
#   Keyframe
#=====================================================================
class Keyframe:
    timeIndex: uint16
    uknFlag: int
    value: float
    inTangent: float
    outTanget: float

    
    def __init__(self, track: Track, f: BufferedReader):
        tmp: int = ReadUInt16(f)
        self.timeIndex = tmp & 0x7fff
        self.uknFlag = tmp >> 15
        self.value = ReadUInt16(f) * track.range * EPSILON_16 + track.min

        # if 'rotation_euler' in track.transformType:
        #     self.value = 180. - self.value
        #     self.value = degrees(self.value)

        if track.comprsnType == Compression.HERMITE_INT16:
            self.inTangent = ReadUInt16(f) * track.inRange * EPSILON_16 + track.inTMin
            self.outTanget = ReadUInt16(f) * track.outRange * EPSILON_16 + track.outTMin


#=====================================================================
#   Track
#=====================================================================
class Track:
    transformType: tuple[str, TRACK_TYPE]
    trackAxis: Axis
    size: uint16
    keyCount: uint16
    comprsnType: Compression
    startTime: uint16
    min: float
    range: float
    inTMin: float
    inRange: float
    outTMin: float
    outRange: float
    keys: list[Keyframe]


    def __init__(self, type: tuple[str, TRACK_TYPE], trackAxis: Axis, f: BufferedReader):
        # print( f"   Reading track at {hex( f.tell() )}" )
        self.size = ReadUInt16(f)
        self.keyCount = ReadUInt16(f)
        self.comprsnType = Compression( ReadUInt16(f) )
        self.startTime = ReadUInt16(f)
        self.min = ReadFloat(f)
        self.range = ReadFloat(f)
        self.transformType = type
        self.trackAxis = trackAxis

        if self.comprsnType == Compression.HERMITE_INT16:
            self.inTMin = ReadFloat(f)
            self.inRange = ReadFloat(f)
            self.outTMin = ReadFloat(f)
            self.outRange = ReadFloat(f)
    
            self.keys = [ Keyframe(self, f) for _ in range(self.keyCount) ]

        elif self.comprsnType != Compression.LINEAR_INT16:
            print( f" Unsupported compression type at {hex( f.tell() )}" )
            return

    
    def SampleKeyframe(self, frameTime: float, i: int, t: float):
        p0 = self.keys[i-1]
        p1 = self.keys[i]

        match self.comprsnType:
            case Compression.HERMITE_INT16 | Compression.HERMITE_FLOAT32:
                return Hermite(float(frameTime), p0.value, p0.timeIndex, p0.outTanget, p1.value, p1.timeIndex, p1.inTangent)

            case Compression.LINEAR_INT16 | Compression.LINEAR_FLOAT32:
                return linear_interpolate(p0.value, p1.value, t)


#=====================================================================
#   Track groups per bone
#=====================================================================
class TrackGroup:
    def __init__(self, motion: Motion, track_flags: int, bone_idx: int, f: BufferedReader):
        self.boneIdx = bone_idx
        self.trackFlags = track_flags
        self.tracks: list[Track] = []

        mapping = [
            (TrackFlags.TRANSLATION_X, "location", TrackType.POSITION, Axis.X),
            (TrackFlags.TRANSLATION_Y, "location", TrackType.POSITION, Axis.Y),
            (TrackFlags.TRANSLATION_Z, "location", TrackType.POSITION, Axis.Z),
            (TrackFlags.ROTATION_X,    "rotation_euler", TrackType.ROTATION, Axis.X),
            (TrackFlags.ROTATION_Y,    "rotation_euler", TrackType.ROTATION, Axis.Y),
            (TrackFlags.ROTATION_Z,    "rotation_euler", TrackType.ROTATION, Axis.Z),
            (TrackFlags.SCALE_X,       "scale", TrackType.SCALE, Axis.X),
            (TrackFlags.SCALE_Y,       "scale", TrackType.SCALE, Axis.Y),
            (TrackFlags.SCALE_Z,       "scale", TrackType.SCALE, Axis.Z),
        ]

        for flag, transform, track_type, axis in mapping:
            if track_flags & flag:
                self.tracks.append(Track((transform, track_type), trackAxis=axis, f=f))

#=====================================================================
#   Motion
#=====================================================================
class Motion:
    f: BufferedReader
    size: uint32
    Id: int32
    startFrame: float
    endFrame: float
    startFrame2: float
    endFrame2: float
    ukn: uint16
    ukn1: uint16
    boneCount: uint16
    ukn2: list[uint16]
    trackGroups: list[TrackGroup]
    trackTypes: list[uint16]


    def __init__(self, f: BufferedReader):
        self.f = f
        self.size = ReadUInt32(f)
        self.Id = ReadSInt32(f)
        self.startFrame = ReadFloat(f)
        self.endFrame = ReadFloat(f)
        self.startFrame2 = ReadFloat(f)
        self.endFrame2 = ReadFloat(f)
        self.ukn = ReadUInt16(f)
        self.ukn1 = ReadUInt16(f)
        self.boneCount = ReadUInt16(f)
        self.ukn2 = []
        self.trackGroups = []

        self.trackTypes = [ ReadUInt16(f) for _ in range(self.boneCount) ]

        while f.tell() < self.size:
            self.ukn2.append( ReadUInt16(f) )


    def ParseTracks(self):
        for boneIdx, trackFlags in enumerate(self.trackTypes):
            
            if trackFlags:
                # print(boneIdx)
                self.trackGroups.append(TrackGroup(self, trackFlags, boneIdx, self.f))

#=====================================================================
#   Setup parsed animations
#=====================================================================
def setup_animation(context: bpy.types.Context, filepath: Path, Mot: Motion) -> None:
    scene: bpy.types.Scene = bpy.data.scenes["Scene"]
    scene.render.fps = 60
    scene.frame_start = int(Mot.startFrame)
    scene.frame_end = int(Mot.endFrame)

    # Get rig (armature object)
    rig = (
        context.object if context.object.type == 'ARMATURE'
        else context.scene.objects["Armature_object"]
    )
    bpy.context.view_layer.objects.active = rig

    # Set rotation mode for pose bones
    for bone in rig.pose.bones:
        bone.rotation_mode = "XYZ"

    # Store rest matrices in edit mode
    bpy.ops.object.mode_set(mode='EDIT')
    rest_matrices = {bone.name: bone.matrix.copy() for bone in rig.data.edit_bones}
    bpy.ops.object.mode_set(mode='POSE')
    rest_quaternions = {name: mat.to_quaternion() for name, mat in rest_matrices.items()}
    bpy.ops.object.mode_set(mode='OBJECT')

    # Create new action
    action_name = os.path.basename(filepath)
    action = bpy.data.actions.new(action_name)

    for track_group in Mot.trackGroups:
        bone_name = f"bone_{track_group.boneIdx}"
        bone = rig.pose.bones[bone_name]
        rest_mat = rest_matrices[bone_name]
        rest_quat = rest_quaternions[bone_name]

        # Initialize empty track samples: [position, rotation, scale]
        track_samples = [
            [Vector((0., 0., 0.)) for _ in range(scene.frame_end + 1)]
            for _ in range(3)
        ]

        for track in track_group.tracks:
            keys = track.keys
            for i in range(1, len(keys)):
                start, end = keys[i - 1].timeIndex, keys[i].timeIndex
                frame_range = end - start

                for frame in range(start, end + 1):
                    t = (frame - start) / frame_range
                    sample = track.SampleKeyframe(frame, i, t)

                    if track.transformType[1] == TrackType.POSITION:
                        sample *= 0.01  # scale position

                    track_samples[track.transformType[1]][frame][track.trackAxis] = sample

        # Create FCurves for each track
        for track in track_group.tracks:
            transform_type, component_type = track.transformType
            axis = track.trackAxis
            data_path = f'pose.bones["{bone_name}"].{transform_type}'
            fcurve = action.fcurves.new(data_path=data_path, index=axis)
            keys = track.keys

            for i in range(1, len(keys)):
                start, end = keys[i - 1].timeIndex, keys[i].timeIndex
                for frame in range(start, end + 1):
                    vec = track_samples[component_type][frame]

                    if component_type == TrackType.POSITION:
                        sample = (rest_mat.inverted() @ Matrix.Translation(vec)).to_translation()[axis]
                    elif component_type == TrackType.ROTATION:
                        quat = Euler(vec).to_quaternion()
                        sample = (rest_quat.inverted() @ quat @ rest_quat).to_euler('XYZ')[axis]
                    elif component_type == TrackType.SCALE:
                        sample = vec[axis]
                    else:
                        continue

                    fcurve.keyframe_points.insert(frame, sample)

    # Assign action and update timeline
    rig.animation_data_create().action = action
    frame_timeline(context)

#=====================================================================
#   Import
#=====================================================================
def Import(context, filepath):
    with open(filepath, 'rb') as file:
        motion = Motion(file)
        file.seek(motion.size, os.SEEK_SET)

        track_count = ReadUInt32(file)
        motion.ParseTracks()

        setup_animation(context, filepath, motion)

    return {'FINISHED'}
