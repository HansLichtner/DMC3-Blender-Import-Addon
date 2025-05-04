import enum
from io import BufferedReader, BufferedWriter
from struct import pack, unpack
from typing import NewType, TypeVar

from mathutils import *
from numpy import byte, int16, int32, int64, ubyte, uint16, uint32, uint64

offs_t = NewType('offs_t', int)


#=====================================================================

class Endian(enum.StrEnum):
    LITTLE = '<'
    BIG = '>'


#=====================================================================
#   Write
#=====================================================================
#region
# String
def WriteString(f: BufferedWriter, s: str, endian: Endian = Endian.LITTLE) -> None:
    if type(s) is bytes:
        f.write(s)
    else:
        f.write( bytes(s, 'utf-8') )


# Byte
def WriteUByte(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:      
    # f.write( pack( endian + 'B', int(v) ) )
    f.write( pack( 'B', int(v) ) )

def WriteSByte(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:  #signed    
    # f.write(pack ( endian + 'b', int(v) ) )
    f.write( pack ( 'b', int(v) ) )

def WriteBytes(f: BufferedWriter, v, count) -> None:
    for _ in range(count):
        WriteSByte(f, v)


# Short
def WriteUInt16(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:      
    f.write( pack( endian + 'H', int(v) ) )

def WriteSInt16(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:  #signed
    f.write( pack( endian + 'h', int(v) ) )


# Int
def WriteUInt32(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:      
    f.write( pack( endian + 'L', v) )

def WriteSInt32(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:  #signed    
    f.write( pack( endian + 'l', v) )


# Int64
def WriteUInt64(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:      
    f.write( pack( endian + 'Q', v) )

def WriteSInt64(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:  #signed
    f.write( pack( endian + 'q', v) )


# Float
def WriteFloat(f: BufferedWriter, v, endian: Endian = Endian.LITTLE) -> None:
    f.write( pack( endian + 'f', v) )

#endregion    


#=====================================================================
#   Read
#=====================================================================
#region
# String
def ReadString(f: BufferedReader, size: int = 0, encoding: str = "utf-8") -> str:
		if size == 0:
			ret = ReadCString(f)
		else:
			ret = unpack( "<" + "%is" % (size), f.read(size) )[0]

		return ret.decode(encoding)

def ReadCString(f: BufferedReader) -> bytes:
		ret = []
		c = b""

		while c != b"\0":
			ret.append(c)
			c = f.read(1)

			if not c:
				raise ValueError("Unterminated string: %r" % (ret))

		return b"".join(ret)


# Byte
def ReadUByte(f: BufferedReader, endian: Endian = Endian.LITTLE) -> ubyte:   
    # return unpack( endian + 'B', f.read(1) )[0]
    return unpack( 'B', f.read(1) )[0]

def ReadByte(f: BufferedReader, endian: Endian = Endian.LITTLE) -> byte:  #signed
    # return unpack( endian + 'b', f.read(1) )[0]
    return unpack( 'b', f.read(1) )[0]


# Short
def ReadUInt16(f: BufferedReader, endian: Endian = Endian.LITTLE) -> uint16:
    return unpack( endian + 'H', f.read(2) )[0]

def ReadSInt16(f: BufferedReader, endian: Endian = Endian.LITTLE) -> int16: #signed
    return unpack( endian + 'h', f.read(2) )[0]


# Int
def ReadUInt32(f: BufferedReader, endian: Endian = Endian.LITTLE) -> uint32:
    return unpack( endian + 'L', f.read(4) )[0]
    
def ReadSInt32(f: BufferedReader, endian: Endian = Endian.LITTLE) -> int32:  #signed
    return unpack( endian + 'l', f.read(4) )[0]


# Int64
def ReadUInt64(f: BufferedReader, endian: Endian = Endian.LITTLE) -> uint64:  
    return unpack( endian + 'Q', f.read(8) )[0]

def ReadSInt64(f: BufferedReader, endian: Endian = Endian.LITTLE) -> int64:  #signed
    return unpack( endian + 'q', f.read(8) )[0]


# Float
def ReadFloat(f: BufferedReader, endian: Endian = Endian.LITTLE) -> float: 
    return unpack( endian + 'f', f.read(4) )[0]

#endregion


def ReadMatrix(f: BufferedReader) -> Matrix:
    Mat = mathutils.Matrix() # type: ignore
    Mat[0] = ( ReadFloat(f), ReadFloat(f), ReadFloat(f), ReadFloat(f) )
    Mat[1] = ( ReadFloat(f), ReadFloat(f), ReadFloat(f), ReadFloat(f) )
    Mat[2] = ( ReadFloat(f), ReadFloat(f), ReadFloat(f), ReadFloat(f) )
    tYZ = [-ReadFloat(f), -ReadFloat(f), ReadFloat(f)]
    Mat[3] = ( tYZ[0], tYZ[1], tYZ[2], ReadFloat (f) )

    return Mat
