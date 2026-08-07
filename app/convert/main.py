"""Convert Litematica (.litematic) files into WorldEdit-compatible Sponge Schematic v2 (.schem) files."""
import gzip
import io
import math

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from nbtlib import ByteArray, Compound, Int, IntArray, Short

router = APIRouter(tags=["Convert"])

SPONGE_VERSION = 2
FALLBACK_DATA_VERSION = 2586  # used when the litematic does not carry MinecraftDataVersion
MIN_BITS_PER_ENTRY = 2  # Litematica's LitematicaBitArray never packs with fewer than 2 bits


def _read_nbt(data: bytes):
    from nbtlib import File as NbtFile

    buffer = io.BytesIO(data)
    if data[:2] == b"\x1f\x8b":
        with gzip.GzipFile(fileobj=buffer) as gz:
            return NbtFile.from_fileobj(gz)
    return NbtFile.from_fileobj(buffer)


def _write_nbt_gzipped(root: Compound) -> bytes:
    from nbtlib import File as NbtFile

    buffer = io.BytesIO()
    # FAWE/Sponge v1+v2 identify the format by the *name* of the root NBT tag, not a nested key
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
        NbtFile(root, root_name="Schematic").write(gz)
    return buffer.getvalue()


def _unsigned_longs(values) -> list:
    mask = (1 << 64) - 1
    return [int(v) & mask for v in values]


def _unpack_block_states(long_array, bits_per_entry: int, size: int) -> list:
    """Unpack Litematica's continuous (unpadded) bit-packed long array into block indices."""
    longs = _unsigned_longs(long_array)
    mask = (1 << bits_per_entry) - 1
    indices = [0] * size
    for i in range(size):
        start_offset = i * bits_per_entry
        start_long = start_offset >> 6
        end_long = ((i + 1) * bits_per_entry - 1) >> 6
        start_bit = start_offset & 63
        if start_long == end_long:
            value = longs[start_long] >> start_bit
        else:
            end_offset = 64 - start_bit
            value = (longs[start_long] >> start_bit) | (longs[end_long] << end_offset)
        indices[i] = value & mask
    return indices


def _block_state_to_string(entry: Compound) -> str:
    name = str(entry["Name"])
    properties = entry.get("Properties")
    if not properties:
        return name
    props = ",".join(f"{key}={value}" for key, value in sorted(properties.items()))
    return f"{name}[{props}]"


def encode_varint(val: int) -> bytes:
    """Minecraft-style VarInt (LEB128, 1-5 bytes) as required for Sponge v2 BlockData entries."""
    buf = bytearray()
    while True:
        tobytes = val & 0x7F
        val >>= 7
        if val != 0:
            buf.append(tobytes | 0x80)
        else:
            buf.append(tobytes)
            break
    return bytes(buf)


def _build_block_data(indices: list) -> ByteArray:
    """Concatenate the VarInt-encoded palette index of every block, in Sponge's x/z/y iteration order."""
    raw = bytearray()
    for index in indices:
        raw.extend(encode_varint(index))
    # TAG_Byte_Array entries are signed in NBT/Java, so unsigned 0-255 bytes must wrap to -128..127
    return ByteArray([b - 256 if b > 127 else b for b in raw])


def _select_main_region(regions: Compound) -> Compound:
    def volume(region: Compound) -> int:
        size = region["Size"]
        return abs(int(size["x"]) * int(size["y"]) * int(size["z"]))

    return max(regions.values(), key=volume)


def convert_litematic_to_schem(data: bytes) -> bytes:
    root = _read_nbt(data)

    regions = root.get("Regions")
    if not regions:
        raise ValueError("Litematic file does not contain any 'Regions' data")

    region = _select_main_region(regions)

    size = region["Size"]
    width = abs(int(size["x"]))
    height = abs(int(size["y"]))
    length = abs(int(size["z"]))
    volume = width * height * length

    palette_nbt = region.get("BlockStatePalette")
    if not palette_nbt:
        raise ValueError("Region does not contain a 'BlockStatePalette'")
    palette = [_block_state_to_string(entry) for entry in palette_nbt]

    bits_per_entry = max(MIN_BITS_PER_ENTRY, math.ceil(math.log2(len(palette))))

    block_states = region.get("BlockStates")
    if block_states is None:
        raise ValueError("Region does not contain 'BlockStates'")

    expected_longs = math.ceil(volume * bits_per_entry / 64)
    if len(block_states) != expected_longs:
        raise ValueError(
            f"Unexpected BlockStates length: expected {expected_longs} longs, got {len(block_states)}"
        )

    indices = _unpack_block_states(block_states, bits_per_entry, volume)

    data_version = int(root.get("MinecraftDataVersion", FALLBACK_DATA_VERSION))

    schem = Compound()
    schem["Version"] = Int(SPONGE_VERSION)
    schem["DataVersion"] = Int(data_version)
    schem["Width"] = Short(width)
    schem["Height"] = Short(height)
    schem["Length"] = Short(length)
    schem["Offset"] = IntArray([0, 0, 0])

    palette_compound = Compound()
    for palette_index, block_state in enumerate(palette):
        palette_compound[block_state] = Int(palette_index)
    schem["PaletteMax"] = Int(len(palette))
    schem["Palette"] = palette_compound
    schem["BlockData"] = _build_block_data(indices)

    return _write_nbt_gzipped(schem)


@router.post("/api/v1/convert")
async def convert(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".litematic"):
        raise HTTPException(status_code=400, detail="Only .litematic files are supported")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        schem_bytes = convert_litematic_to_schem(raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to convert schematic: {exc}") from exc

    output_name = file.filename.rsplit(".", 1)[0] + ".schem"
    return StreamingResponse(
        io.BytesIO(schem_bytes),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
    )
