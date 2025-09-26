#common\io.py:
import enum
from io import BufferedReader, BufferedWriter
from struct import pack, unpack
from typing import NewType

import mathutils
import numpy as np

# numpy-based types (mais modernos)
byte = np.int8
ubyte = np.uint8
int16 = np.int16
int32 = np.int32
int64 = np.int64
uint16 = np.uint16
uint32 = np.uint32
uint64 = np.uint64

offs_t = NewType('offs_t', int)

class Endian:
    LITTLE = '<'
    BIG = '>'

# Write
def WriteString(f: BufferedWriter, s: str, endian = Endian.LITTLE) -> None:
    if isinstance(s, bytes):
        f.write(s)
    else:
        f.write(bytes(s, 'utf-8'))

def WriteUByte(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack('B', int(v)))

def WriteSByte(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack('b', int(v)))

def WriteBytes(f: BufferedWriter, v, count) -> None:
    for _ in range(count):
        WriteSByte(f, v)

def WriteUInt16(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack(str(endian) + 'H', int(v)))

def WriteSInt16(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack(str(endian) + 'h', int(v)))

def WriteUInt32(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack(str(endian) + 'L', int(v)))

def WriteSInt32(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack(str(endian) + 'l', int(v)))

def WriteUInt64(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack(str(endian) + 'Q', int(v)))

def WriteSInt64(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack(str(endian) + 'q', int(v)))

def WriteFloat(f: BufferedWriter, v, endian=Endian.LITTLE) -> None:
    f.write(pack(str(endian) + 'f', v))

# Read
def ReadString(f: BufferedReader, size: int = 0, encoding="utf-8") -> str:
    if size == 0:
        ret = ReadCString(f)
    else:
        ret = unpack("<" + f"{size}s", f.read(size))[0]
    return ret.decode(encoding)

def ReadCString(f: BufferedReader) -> bytes:
    ret = []
    while True:
        c = f.read(1)
        if not c or c == b"\0":
            break
        ret.append(c)
    return b"".join(ret)

def ReadUByte(f: BufferedReader, endian=Endian.LITTLE) -> ubyte:
    return unpack('B', f.read(1))[0]

def ReadByte(f: BufferedReader, endian=Endian.LITTLE) -> byte:
    return unpack('b', f.read(1))[0]

def ReadUInt16(f: BufferedReader, endian=Endian.LITTLE) -> uint16:
    return unpack(str(endian) + 'H', f.read(2))[0]

def ReadSInt16(f: BufferedReader, endian=Endian.LITTLE) -> int16:
    return unpack(str(endian) + 'h', f.read(2))[0]

def ReadUInt32(f: BufferedReader, endian=Endian.LITTLE) -> uint32:
    return unpack(str(endian) + 'L', f.read(4))[0]

def ReadSInt32(f: BufferedReader, endian=Endian.LITTLE) -> int32:
    return unpack(str(endian) + 'l', f.read(4))[0]

def ReadUInt64(f: BufferedReader, endian=Endian.LITTLE) -> uint64:
    return unpack(str(endian) + 'Q', f.read(8))[0]

def ReadSInt64(f: BufferedReader, endian=Endian.LITTLE) -> int64:
    return unpack(str(endian) + 'q', f.read(8))[0]

def ReadFloat(f: BufferedReader, endian=Endian.LITTLE) -> float:
    return unpack(str(endian) + 'f', f.read(4))[0]

def ReadMatrix(f: BufferedReader) -> mathutils.Matrix:
    Mat = mathutils.Matrix()
    Mat[0] = (ReadFloat(f), ReadFloat(f), ReadFloat(f), ReadFloat(f))
    Mat[1] = (ReadFloat(f), ReadFloat(f), ReadFloat(f), ReadFloat(f))
    Mat[2] = (ReadFloat(f), ReadFloat(f), ReadFloat(f), ReadFloat(f))
    tYZ = [-ReadFloat(f), -ReadFloat(f), ReadFloat(f)]
    Mat[3] = (tYZ[0], tYZ[1], tYZ[2], ReadFloat(f))
    return Mat


