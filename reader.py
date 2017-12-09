import os.path
import binascii
from deflate import Deflate

SUPPORTED_CHUNKS = {'IHDR', 'IDAT', 'IEND', 'PLTE',
                    'bKGD', 'cHRM', 'gAMA', 'iTXt',
                    'pHYs', 'sBIT', 'sPLT', 'sRGB',
                    'sTER', 'tEXt', 'tIME', 'tRNS',
                    'zTXt', 'iCCP', 'hIST'}

INDEXED_COLOR = 'indexed-color'
GRAYSCALE = 'grayscale'
TRUECOLOR = 'truecolor'


class Picture:
    def __init__(self, name, chunks):
        self.name = name
        self.width = None
        self.height = None
        self.bit_depth = None
        self.sample_depth = None
        # The sample depth is the same as the bit depth except in the case of color type 3 (indexed-color),
        # in which the sample depth is always 8 bits
        # (in that case bit depth determines the maximum number of palette entries)
        self.color_type = None
        self.type_of_pixel = None  # indexed-color, grayscale or truecolor
        self.alpha_channel = None
        self.compression_method = None
        self.filter_method = None
        self.interlace_method = None
        self.chunks = []
        self.analyze_chunks(chunks)

    def __str__(self):
        return 'Name: {}, {}x{}, Bit depth: {}, Sample depth: {}, Pixel: {},\r\n' \
               'Alpha: {}, Compression: {}, Filter: {}, Interlace: {}\r\n'.format(self.name, self.width, self.height,
                                                                                  self.bit_depth, self.sample_depth,
                                                                                  self.type_of_pixel,
                                                                                  self.alpha_channel,
                                                                                  self.compression_method,
                                                                                  self.filter_method,
                                                                                  self.interlace_method)

    def __repr__(self):
        return self.__str__()

    def analyze_chunks(self, chunks):
        self.check_chunk_order(chunks)

        for chunk in chunks:
            chunk_bits = self.identify_chunk(chunk.name)
            new_chunk = ExtendedChunk(chunk, chunk_bits)
            if new_chunk.unknown:
                continue
            self.chunks.append(new_chunk)

        self.read_header()

    def check_chunk_order(self, chunks):
        # TODO: http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html#C.Summary-of-standard-chunks
        pass

    def identify_chunk(self, chunk_name):
        ancillary = False if (65 <= chunk_name[0] <= 90) else True
        private = False if (65 <= chunk_name[1] <= 90) else True
        reserved = False if (65 <= chunk_name[2] <= 90) else True
        safe = False if (65 <= chunk_name[3] <= 90) else True
        unknown = False if chunk_name.decode() in SUPPORTED_CHUNKS else True

        if not ancillary and unknown:
            raise LookupError('Unknown critical chunk faced, terminating')  # TODO: exception type

        return ancillary, private, reserved, safe, unknown

    def read_header(self):
        header_chunk = self.chunks[0]  # IHDR chunk must be FIRST

        width, height = map(lambda x: int(binascii.hexlify(x), 16), (header_chunk.data[0:4], header_chunk.data[4:8]))
        bit_depth, color_type = header_chunk.data[8], header_chunk.data[9]
        compression_method = header_chunk.data[10]
        filter_method, interlace_method = header_chunk.data[11], header_chunk.data[12]

        self.width, self.height = width, height
        self.bit_depth, self.color_type = bit_depth, color_type
        self.compression_method = compression_method
        self.filter_method, self.interlace_method = filter_method, interlace_method

        self.get_type_of_pixel()

    def get_type_of_pixel(self):
        bit_depth, color_type = self.bit_depth, self.color_type

        if color_type == 0:
            if bit_depth in {1, 2, 4, 8, 16}:
                self.sample_depth = self.bit_depth
                self.type_of_pixel = GRAYSCALE
                self.alpha_channel = False
                return
        elif color_type == 2:
            if bit_depth in {8, 16}:
                self.sample_depth = self.bit_depth
                self.type_of_pixel = TRUECOLOR
                self.alpha_channel = False
                return
        elif color_type == 3:
            if bit_depth in {1, 2, 4, 8}:
                self.sample_depth = 8
                self.type_of_pixel = INDEXED_COLOR
                self.alpha_channel = False
                return
        elif color_type == 4:
            if bit_depth in {8, 16}:
                self.sample_depth = self.bit_depth
                self.type_of_pixel = GRAYSCALE
                self.alpha_channel = True
                return
        elif color_type == 6:
            if bit_depth in {8, 16}:
                self.sample_depth = self.bit_depth
                self.type_of_pixel = TRUECOLOR
                self.alpha_channel = True
                return

        raise LookupError('Illegal bit depth or color type faced.')  # TODO: exception type

        # Color type codes represent sums of the following values:
        # 1 (palette used), 2 (color used), and 4 (alpha channel used)
        # Valid values are 0, 2, 3, 4, and 6

        # Color    Allowed     Interpretation
        # Type    Bit Depths
        #
        #  0       1,2,4,8,16  Each pixel is a grayscale sample.
        #
        #  2       8,16        Each pixel is an R,G,B triple.
        #
        #  3       1,2,4,8     Each pixel is a palette index;
        #                      a PLTE chunk must appear.
        #
        #  4       8,16        Each pixel is a grayscale sample,
        #                      followed by an alpha sample.
        #
        #  6       8,16        Each pixel is an R,G,B triple,
        #                      followed by an alpha sample.


class Chunk:
    def __init__(self, name, length, data, crc):
        self.name = name
        self.length = length
        self.data = data
        self.crc = crc

    def __str__(self):
        return 'name: {}, len: {}'.format(self.name.decode(), self.length)

    def __repr__(self):
        return self.__str__()


class ExtendedChunk(Chunk):
    def __init__(self, chunk, chunk_bits):
        super().__init__(chunk.name, chunk.length, chunk.data, chunk.crc)
        self.ancillary_bit, self.private_bit, self.reserved_bit, self.safe_to_copy_bit, self.unknown = chunk_bits


class Reader:
    def __init__(self):
        self.name = None
        self.file = None
        self.chunks = []

    def open(self, file):
        if os.path.isfile(file):
            self.file = open(file, 'rb')
            self.name = os.path.basename(file)
        else:
            raise ReferenceError('File not found')
        return self

    def close(self):
        if self.file:
            self.file.close()
        else:
            raise ReferenceError('Nothing is opened')

    def read(self, n):
        return self.file.read(n)

    def read_next_chunk(self):
        b_length = self.file.read(4)
        length = int(binascii.hexlify(b_length), 16)
        name = self.read(4)
        data = self.read(length)
        crc = self.read(4)
        chunk = Chunk(name, length, data, crc)
        if not self.check_crc(chunk):
            raise TypeError('File seems to be corrupted')
        return chunk

    def check_crc(self, chunk):
        data = chunk.name + chunk.data
        return binascii.crc32(data) == int(binascii.hexlify(chunk.crc), 16)

    def is_png(self):
        if self.file:
            info = self.file.read(8)
            self.file.seek(0)
            return all(x == y for x, y in zip(info, (137, 80, 78, 71, 13, 10, 26, 10)))
        return False

    def read_all_chunks(self):
        chunk = self.read_next_chunk()
        while chunk.name != b'IEND':
            self.chunks.append(chunk)
            chunk = self.read_next_chunk()
        self.chunks.append(chunk)

    def get_picture(self):
        if not self.file:
            raise ReferenceError('Nothing is opened')

        self.file.seek(0)
        if not self.is_png():
            raise TypeError('File seems to be corrupted')
        self.file.read(8)  # PNG signature
        self.read_all_chunks()

        return Picture(self.name, self.chunks)


def main():
    reader = Reader()
    pic = reader.open('pics/mario.png').get_picture()
    data_chunks = []
    for chunk in pic.chunks:
        if chunk.name == b'IDAT':
            data_chunks.append(chunk)

    for chunk in data_chunks:
        coded = binascii.hexlify(chunk.data)
        decoded = Deflate.decode(coded)
        print(decoded)

if __name__ == '__main__':
    main()
