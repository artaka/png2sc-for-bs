import re
import os
import sys
import lzma
import struct
import sqlite3
import binascii
import subprocess
import random

from PIL import Image, ImageDraw
from modules import *

mode = int(input("What mode to use?\nCompress-1\nDecompress-2\n"))

if mode == 1:
    compileDir = './compile/'
    compiledDir = './compiled/'

    findFiles = {}
    picCount = 0

    dbcon = sqlite3.connect("PixelData.db")
    dbcon.isolation_level = None
    dbcur = dbcon.cursor()
    dbcon.row_factory = sqlite3.Row
    dbcon.text_factory = str

    def _(message):
        print(u"[RELEASE] %s" % message)

    def checkAlreadyExists(filename):
        dbcur.execute('select * from PixelType where filename = ?', [filename])
        rrf = dbcur.fetchone()
        
        if rrf is None:
            return None
        
        return rrf

    def file2bytes(fileName):
        with open(fileName, "rb+") as handle:
            bytes = handle.read()

        return bytes

    def bytes2file(bytes, fileName):
        handler = open(fileName, "wb+")
        handler.write(bytes)
        handler.close()

    def convert_pixel(pixels, type):
        value = None
        
        if type == 0:  # RGB8888
            return pixels
        
        elif type == 2:  # RGB4444
            r = (pixels[0] >> 4) << 12
            g = (pixels[1] >> 4) << 8
            b = (pixels[2] >> 4) << 4
            a = (pixels[3] >> 4)
            
            value = r | g | b | a
        
        elif type == 4:  # RGB565
            r = (pixels[0] >> 3) << 11
            g = (pixels[1] >> 2) << 5
            b = (pixels[2] >> 3)

            value = r | g | b
        
        elif type == 6:  # LA88
            r = pixels[0] << 8
            g = pixels[1] << 8
            b = pixels[2] << 8
            a = pixels[3]

            value = r | g | b | a
        
        elif type == 10:  # L8
            value = pixels[0] | pixels[1] | pixels[2]
        else:
            raise Exception("Unknown pixel type {}.".format(type))

        return value

    def writeImage(file, baseName, fileName, pp = 1):
        _("Collecting information...")

        image = Image.open(file)
        data = checkAlreadyExists(baseName)

        if not data is None:
            fileType = data[1]
            subType = data[2]
        else:
            _("Sorry, we can\'t find this texture in out database... May be you changed filename?")
            _("We will use standart fileType, subType and headerBytes. (1, 0, None)" + "\n")
            
            fileType = 1
            subType = 0
        
        width  = image.size[0]
        height = image.size[1]

        pixels = []
        iSrcPix = 0

        if subType == 0:
            BFPXFormat = 4
        elif subType == 2 or subType == 4 or subType == 6:
            BFPXFormat = 2
        elif subType == 10:
            BFPXFormat = 1
        else:
            _("Unknown pixel type %s" % (subType))
            sys.exit(0)
            
        if BFPXFormat:
            packetSize = ((width) * (height) * BFPXFormat) + 5;
        
        _("About: fileType %s, fileSize: %s, subType: %s, width: %s, height: %s" % (fileType, packetSize, subType, width, height))
        
        imgl = image.load()
        
        if fileType == 28 or fileType == 27:
            for y in range(0, height):
                for x in range(0, width):
                    c = image.getpixel((x, y))
                    pixels.append(c)

            for l in range(int(height / 32)):
                for k in range(int(width / 32)):
                    for j in range(32):
                        for h in range(32):
                            pixels[iSrcPix] = imgl[h + (k * 32), j + (l * 32)]
                            iSrcPix += 1
                            
                for j in range(32):
                    for h in range(width % 32):
                        pixels[iSrcPix] = imgl[h + (width - (width % 32)), j + (l * 32)]
                        iSrcPix += 1

            for k in range(int(width / 32)):
                for j in range(int(height % 32)):
                    for h in range(32):
                        pixels[iSrcPix] = imgl[h + (k * 32), j + (height - (height % 32))]
                        iSrcPix += 1

            for j in range(height % 32):
                for h in range(width % 32):
                    pixels[iSrcPix] = imgl[h + (width - (width % 32)), j + (height - (height % 32))]
                    iSrcPix += 1

        image.putdata(pixels)
        
        # Create new packet
        p = BytesWriter(fileName)

        # Start Handler
        p.WStart()

        # Packet
        p.WByte(28)
        p.WUnsignedInt(packetSize)
        p.WByte(subType)
        p.WUnsignedShort(width)
        p.WUnsignedShort(height)

        for y in range(0, height):
            for x in range(0, width):
                pixels = image.getpixel((x, y))
                converted = convert_pixel(pixels, subType)

                if subType == 0:
                    p.W4Bytes(*converted)
                    
                elif subType == 2: # RGB4444 to RGB8888
                    p.WUnsignedShort(converted)
                    
                elif subType == 4: # RGB565 to RGB8888
                    p.WUnsignedShort(converted)

                elif subType == 6: # RGB555 to RGB8888                
                    p.WUnsignedShort(converted)

                elif subType == 10:
                    p.WUnsignedByte(converted)
                    
        if fileName.endswith((pp * "_") + "tex.sc"):
            p.WByte(0)
            p.WByte(0)
            p.WByte(0)
            p.WByte(0)
            p.WByte(0)

        p.WStop()

    def compressLZMA(fileName):
        _("Saving as sprite...")
        
        result = subprocess.check_output(["lzma.exe", "e", "temp_tex.sc", "temp_.tex_sc"])
        
        os.remove("temp_tex.sc")
        os.rename("temp_.tex_sc", "temp_tex.sc")
        
        # Module with LZMA
        with open("temp_tex.sc", "rb") as lz:
            lzModule = lz.read()
            lzModule = lzModule[0:9] + lzModule[13:]

            mModule = open("./compiled/" + re.sub("\_*tex\_*", "_tex.sc", fileName), "wb+")
            mModule.write(lzModule)
            mModule.close()
            
            lz.close()
            os.remove("temp_tex.sc")

            _("Saving completed" + "\n")
            
    def generateFilesList(dir):
        if findFiles.get(dir) is None:
            findFiles[dir] = []
                    
        toCompile = os.listdir(dir)

        for file in toCompile:
            fullname = dir + file
            if os.path.isdir(fullname):
                dir_ = fullname + "/"
                
                if findFiles.get(dir_) is None:
                    findFiles[dir_] = []
                    
                generateFilesList(dir_)
            else:
                if file.endswith("png"):
                    findFiles[dir].append(file)

    generateFilesList(compileDir)

    for dirName in findFiles:
        for file in findFiles[dirName]:
            file = dirName + file
            baseName, ext = os.path.splitext(os.path.basename(file))
            
            # If we will compile 2 files in one
            if not dirName == compileDir:            
                fileName = "temp_" + ("_" * picCount) + "tex.sc"
                writeImage(file, baseName, fileName, len(findFiles[dirName]))

                picCount += 1

                if picCount == len(findFiles[dirName]):
                    b_bytes = b''
                    
                    for j in range(picCount):
                        f_name = "temp_" + ("_" * j) + "tex.sc"
                        b_bytes += file2bytes(f_name)
                        os.remove(f_name)
                        
                    bytes2file(b_bytes, "temp_tex.sc")
                    compressLZMA(baseName)
                        
            # if we have standart file (1 file)
            elif file.endswith("png"):
                
                fileName = "temp_tex.sc"
                writeImage(file, baseName, fileName)
                
                compressLZMA(baseName)
elif mode == "2":
    folder = "./decompile/"
    folder_export = "./decompiled/"

    dbcon = sqlite3.connect("PixelData.db")
    dbcon.isolation_level = None
    dbcur = dbcon.cursor()
    dbcon.row_factory = sqlite3.Row
    dbcon.text_factory = str

    def _(message):
        print(u"[RELEASE] %s" % message)

    def checkAlreadyExists(filename):
        dbcur.execute("select * from PixelType where filename = ?", [filename])
        rrf = dbcur.fetchone()
        
        if rrf is None:
            return None
        
        return 1

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

    def decompileSC(fileName):
        baseName = os.path.splitext(os.path.basename(fileName))[0]
        
        with open(fileName, "rb") as fh:
            data = fh.read()
            
            if data[0] != 93:
                data = data[26:]
                
            data = data[0:9] + (b"\x00" * 4) + data[9:]
            decompressed = lzma.LZMADecompressor().decompress(data)
            
            i = 0
            picCount = 0

            _("Collecting information...")
            
            while len(decompressed[i:]) > 5:
                fileType = decompressed[i]
                fileSize, = struct.unpack("<I", decompressed[i + 1:i + 5])
                subType = decompressed[i + 5]
                width, = struct.unpack("<H", decompressed[i + 6:i + 8])
                height, = struct.unpack("<H", decompressed[i + 8:i + 10])
                
                i += 10
                
                if subType == 0:
                    pixelSize = 4
                elif subType == 2 or subType == 4 or subType == 6:
                    pixelSize = 2
                elif subType == 10:
                    pixelSize = 1
                else:
                    raise Exception("Unknown pixel type {}.".format(subType))

                _("About: fileName %s, fileType %s, fileSize: %s, subType: %s, width: %s, height: %s" % (fileName, fileType, fileSize, subType, width, height))
                _("Creating picture...")
                
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
                    for l in range(int(height / 32)):
                        for k in range(int(width / 32)):
                            for j in range(32):
                                for h in range(32):
                                    imgl[h + (k * 32), j + (l * 32)] = pixels[iSrcPix]
                                    iSrcPix += 1
                        for j in range(32):
                            for h in range(width % 32):
                                imgl[h + (width - (width % 32)), j + (l * 32)] = pixels[iSrcPix]
                                iSrcPix += 1
                                
                    for k in range(int(width / 32)):
                        for j in range(int(height % 32)):
                            for h in range(32):
                                imgl[h + (k * 32), j + (height - (height % 32))] = pixels[iSrcPix]
                                iSrcPix += 1

                    for j in range(height % 32):
                        for h in range(width % 32):
                            imgl[h + (width - (width % 32)), j + (height - (height % 32))] = pixels[iSrcPix]
                            iSrcPix += 1
                            
                fullname = baseName + ('_' * picCount)

                if checkAlreadyExists(fullname) is None:
                    dbcur.execute('INSERT INTO PixelType (filename, fileType, pixel, hexsc) values (?, ?, ?, ?)', [fullname, fileType, subType, ''])
                    
                _("Saving as png...")
                img.save(folder_export + fullname + ".png", "PNG")
                picCount += 1
                _("Saving completed" + "\n")

    if __name__ == "__main__":
        files = os.listdir(folder)
        for file in files:
            if file.endswith("_tex.sc"):
                decompileSC(folder + file)