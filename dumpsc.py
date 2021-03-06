import argparse
import os
import struct
import lzma
from PIL import Image

"""
Tool for extracting Clash Royale "*_tex.sc" files

Download .apk from the net and extract with 7zip.

Linux / Mac:
find ./assets/sc -name "*_tex.sc" | xargs python dumpsc.py

Windows:
for %v in (*tex.sc) do dumpsc.py %v

Will save all png files.
"""


def convert_pixel(pixel, type):
    if type == 0:  # RGB8888
        return struct.unpack('4B', pixel)
    elif type == 2:  # RGB4444
        pixel, = struct.unpack('<H', pixel)
        return (((pixel >> 12) & 0xF) << 4, ((pixel >> 8) & 0xF) << 4,
                ((pixel >> 4) & 0xF) << 4, ((pixel >> 0) & 0xF) << 4)
    elif type == 4:  # RGB565
        pixel, = struct.unpack("<H", pixel)
        return (((pixel >> 11) & 0x1F) << 3, ((pixel >> 5) & 0x3F) << 2, (pixel & 0x1F) << 3)
    elif type == 6:  # LA88
        pixel, = struct.unpack("<H", pixel)
        return ((pixel >> 8), (pixel >> 8), (pixel >> 8), (pixel & 0xFF))
    elif type == 10:  # L8
        pixel, = struct.unpack("<B", pixel)
        return (pixel, pixel, pixel)
    else:
        raise Exception("Unknown pixel type {}.".format(type))


def process_sc(baseName, data, path):
    # Fix header and decompress
    data = data[0:9] + (b'\x00' * 4) + data[9:]
    decompressed = lzma.LZMADecompressor().decompress(data)

    i = 0
    picCount = 0
    while len(decompressed[i:]) > 5:
        fileType, = struct.unpack('<b', bytes([decompressed[i]]))
        fileSize, = struct.unpack('<I', decompressed[i + 1:i + 5])
        subType, = struct.unpack('<b', bytes([decompressed[i + 5]]))
        width, = struct.unpack('<H', decompressed[i + 6:i + 8])
        height, = struct.unpack('<H', decompressed[i + 8:i + 10])
        i += 10
        if subType == 0:
            pixelSize = 4
        elif subType == 2 or subType == 4 or subType == 6:
            pixelSize = 2
        elif subType == 10:
            pixelSize = 1
        else:
            raise Exception("Unknown pixel type {}.".format(subType))

        print('fileType: {}, fileSize: {}, subType: {}, width: {}, '
              'height: {}'.format(fileType, fileSize, subType, width, height))

        img = Image.new("RGBA", (width, height))
        pixels = []
        for y in range(height):
            for x in range(width):
                pixels.append(convert_pixel(decompressed[i:i + pixelSize], subType))
                i += pixelSize
        img.putdata(pixels)

        if fileType == 28 or fileType == 27:
            imgl = img.load()
            iSrcPix = 0
            for l in range(height // 32):  # block of 32 lines
                # normal 32-pixels blocks
                for k in range(width // 32):  # 32-pixels blocks in a line
                    for j in range(32):  # line in a multi line block
                        for h in range(32):  # pixels in a block
                            imgl[h + (k * 32), j + (l * 32)] = pixels[iSrcPix]
                            iSrcPix += 1
                # line end blocks
                for j in range(32):
                    for h in range(width % 32):
                        imgl[h + (width - (width % 32)), j + (l * 32)] = pixels[iSrcPix]
                        iSrcPix += 1
            # final lines
            for k in range(width // 32):  # 32-pixels blocks in a line
                for j in range(height % 32):  # line in a multi line block
                    for h in range(32):  # pixels in a 32-pixels-block
                        imgl[h + (k * 32), j + (height - (height % 32))] = pixels[iSrcPix]
                        iSrcPix += 1
            # line end blocks
            for j in range(height % 32):
                for h in range(width % 32):
                    imgl[h + (width - (width % 32)), j + (height - (height % 32))] = pixels[iSrcPix]
                    iSrcPix += 1

        img.save(path + baseName + ('_' * picCount) + '.png', 'PNG')
        picCount += 1

folder = "./decompile/"

if __name__ == "__main__":
    files = os.listdir(folder)
    for file in files:
        if file.endswith('_tex.sc'):
            baseName, ext = os.path.splitext(os.path.basename(file))
            with open(folder + file, 'rb') as f:
                print('{}'.format(f.name))
                data = f.read()
                process_sc(baseName, data[26:], folder)
        else:
            print('{} not supported.'.format(file))
