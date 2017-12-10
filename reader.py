import os.path
import binascii
import io
from itertools import repeat
from PIL import Image
from deflate import Deflate
from bit_input_stream import BitInputStream

SUPPORTED_CHUNKS = {'IHDR', 'IDAT', 'IEND', 'PLTE',
                    'bKGD', 'gAMA', 'iTXt', 'tEXt',
                    'tIME', 'tRNS', 'zTXt'}

INDEXED_COLOR = 'indexed-color'
GRAYSCALE = 'grayscale'
TRUECOLOR = 'truecolor'

GAP_MAP = {(GRAYSCALE, False, 1): 1, (GRAYSCALE, False, 2): 1, (GRAYSCALE, False, 3): 1,
           (GRAYSCALE, False, 4): 1, (GRAYSCALE, False, 8): 1, (GRAYSCALE, False, 16): 2,
           (GRAYSCALE, True, 8): 2, (GRAYSCALE, True, 16): 4,
           (INDEXED_COLOR, False, 1): 1, (INDEXED_COLOR, False, 2): 1, (INDEXED_COLOR, False, 3): 1,
           (INDEXED_COLOR, False, 4): 1, (INDEXED_COLOR, False, 8): 1,
           (TRUECOLOR, False, 8): 3, (TRUECOLOR, False, 16): 6,
           (TRUECOLOR, True, 8): 4, (TRUECOLOR, True, 16): 8}


def parametrized(dec):
    def layer(*args, **kwargs):
        def repl(f):
            return dec(f, *args, **kwargs)
        return repl
    return layer


@parametrized
def chunk_wrapper(func, is_critical):
    def wrapped(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            if is_critical:
                raise e
            else:
                return  # ignore any errors on non-critical chunk
    return wrapped


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
        self.background_color = None  # grayscale stores as RGB(gray, gray, gray)
        self.gamma = None
        self.text_info = None
        self.last_modification_time = None
        self.fully_transparent_color = None  # that color indicates fully transparent pixel (tRNS chunk)
        self.chunks = []
        self._chunks_set = set()
        self.palette = None
        self.__analyze_chunks(chunks)
        self._gap = GAP_MAP[(self.type_of_pixel, self.alpha_channel, self.bit_depth)]
        self._pixel_map = [[] for _ in repeat(0, self.width)]
        self._temp_output_stream = self.__decode_idat_stream()
        # self.__unfilter_image()

    def __str__(self):
        return 'Name: {}, {}x{}, Bit depth: {}, Sample depth: {}, Pixel type: {},\r\n' \
               'Alpha: {}, Compression: {}, Filter: {}, Interlace: {}\r\n'.format(self.name, self.width, self.height,
                                                                                  self.bit_depth, self.sample_depth,
                                                                                  self.type_of_pixel,
                                                                                  self.alpha_channel,
                                                                                  self.compression_method,
                                                                                  self.filter_method,
                                                                                  self.interlace_method)

    def __repr__(self):
        return self.__str__()

    def __analyze_chunks(self, chunks):
        self.__check_chunk_order(chunks)

        for chunk in chunks:
            chunk_bits = self.__identify_chunk(chunk.name)
            new_chunk = ExtendedChunk(chunk, chunk_bits)
            if new_chunk.unknown:
                continue
            self.chunks.append(new_chunk)
            self._chunks_set.add(new_chunk.name)

        self.__read_IHDR()
        if b'PLTE' in self._chunks_set:
            self.__read_PLTE()
        if b'bKGD' in self._chunks_set:
            self.__read_bKGD()
        if b'gAMA' in self._chunks_set:
            self.__read_gAMA()
        if b'tEXt' in self._chunks_set:
            self.__read_tEXt()
        if b'tIME' in self._chunks_set:
            self.__read_tIME()
        if b'tRNS' in self._chunks_set:
            self.__read_tRNS()
        if b'zTXt' in self._chunks_set:
            self.__read_zTXt()
        if b'iTXt' in self._chunks_set:
            self.__read_iTXt()

    def __check_chunk_order(self, chunks):
        # TODO: http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html#C.Summary-of-standard-chunks
        pass

    def __identify_chunk(self, chunk_name):
        ancillary = False if (65 <= chunk_name[0] <= 90) else True
        private = False if (65 <= chunk_name[1] <= 90) else True
        reserved = False if (65 <= chunk_name[2] <= 90) else True
        safe = False if (65 <= chunk_name[3] <= 90) else True
        unknown = False if chunk_name.decode() in SUPPORTED_CHUNKS else True

        if not ancillary and unknown:
            raise LookupError('Unknown critical chunk faced, terminating')  # TODO: exception type

        return ancillary, private, reserved, safe, unknown

    @chunk_wrapper(True)
    def __read_IHDR(self):
        header_chunk = self.chunks[0]  # IHDR chunk must be FIRST

        width, height = map(lambda x: int(binascii.hexlify(x), 16), (header_chunk.data[0:4], header_chunk.data[4:8]))
        bit_depth, color_type = header_chunk.data[8], header_chunk.data[9]
        compression_method = header_chunk.data[10]
        filter_method, interlace_method = header_chunk.data[11], header_chunk.data[12]

        self.width, self.height = width, height
        self.bit_depth, self.color_type = bit_depth, color_type
        self.compression_method = compression_method
        self.filter_method, self.interlace_method = filter_method, interlace_method

        self.__get_type_of_pixel()

    def __get_type_of_pixel(self):
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

    @chunk_wrapper(True)
    def __read_PLTE(self):
        if self.type_of_pixel == GRAYSCALE:
            return
        plte_chunk, faced = None, 0
        for chunk in self.chunks:
            if chunk.name == b'PLTE':
                plte_chunk = chunk
                faced += 1

        if faced == 0 and self.type_of_pixel == TRUECOLOR:
            return

        if faced != 1 or plte_chunk is None:
            raise ValueError('There must be 1 PLTE chunk in indexed-color image')
        if not (plte_chunk.length // 3 <= 2 ** self.bit_depth <= 2 ** 8) or plte_chunk.length % 3:
            raise ValueError('Illegal PLTE chunk data')

        self.palette = []
        for i in range(0, plte_chunk.length, 3):
            self.palette.append((plte_chunk.data[i], plte_chunk.data[i + 1], plte_chunk.data[i + 2]))

    @chunk_wrapper(False)
    def __read_bKGD(self):
        bkgd_chunk = self.__find_first_chunk('bKGD')

        if self.type_of_pixel == INDEXED_COLOR:
            self.background_color = self.palette[bkgd_chunk.data[0]]
        elif self.type_of_pixel == GRAYSCALE:
            gray_value = int(binascii.hexlify(bkgd_chunk.data), 16)
            self.background_color = tuple([gray_value] * 3)
        else:
            red, green, blue = map(lambda x: int(binascii.hexlify(x), 16), (bkgd_chunk.data[0:2],
                                                                            bkgd_chunk.data[2:4],
                                                                            bkgd_chunk.data[4:6]))
            self.background_color = (red, green, blue)

    @chunk_wrapper(False)
    def __read_gAMA(self):
        gamma_chunk = self.__find_first_chunk('gAMA')

        self.gamma = int(binascii.hexlify(gamma_chunk.data), 16) / 1e5

    @chunk_wrapper(False)
    def __read_tEXt(self):
        text_chunks = []
        for chunk in self.chunks:
            if chunk.name == b'tEXt':
                text_chunks.append(chunk)
        if self.text_info is None:
            self.text_info = ''

        for text_chunk in text_chunks:
            null_index = text_chunk.data.index(0)
            keyword, text = text_chunk.data[0:null_index].decode(), text_chunk.data[null_index+1:].decode()
            self.text_info += '{}: {}\n'.format(keyword, text)

    @chunk_wrapper(False)
    def __read_tIME(self):
        time_chunk = self.__find_first_chunk('tIME')

        year = int(binascii.hexlify(time_chunk.data[0:2]), 16)
        month, day, hour, minute, second = time_chunk.data[2:]
        minute, second = map(lambda x: '0' + str(x) if len(str(x)) == 1 else x, (minute, second))

        self.last_modification_time = '{}.{}.{} {}:{}:{}'.format(day, month, year, hour, minute, second)

    @chunk_wrapper(False)
    def __read_tRNS(self):
        trns_chunk = self.__find_first_chunk('tRNS')

        if self.type_of_pixel == INDEXED_COLOR:
            new_palette = []
            for i in range(0, len(self.palette)):
                value = (tuple(list(self.palette[i]) + [trns_chunk.data[i]])
                         if i < trns_chunk.length else
                         tuple(list(self.palette[i]) + [255]))
                new_palette.append(value)
            self.palette = new_palette
        elif self.type_of_pixel == GRAYSCALE:
            gray_value = int(binascii.hexlify(trns_chunk.data), 16)
            self.fully_transparent_color = tuple([gray_value] * 3)
        else:
            red, green, blue = map(lambda x: int(binascii.hexlify(x), 16), (trns_chunk.data[0:2],
                                                                            trns_chunk.data[2:4],
                                                                            trns_chunk.data[4:6]))
            self.fully_transparent_color = (red, green, blue)

    @chunk_wrapper(False)
    def __read_zTXt(self):
        text_chunks = []
        for chunk in self.chunks:
            if chunk.name == b'zTXt':
                text_chunks.append(chunk)
        if self.text_info is None:
            self.text_info = ''

        for chunk in text_chunks:
            null_index = chunk.data.index(0)
            keyword = chunk.data[0:null_index].decode()
            compression_method = chunk.data[null_index+1]
            if compression_method != 0:
                raise ValueError('Unrecognized compression method')

            input_stream = BitInputStream(io.BytesIO(chunk.data[null_index+2:]))
            input_stream.read_byte(), input_stream.read_byte()  # skip zlib header (always 2 bytes in PNG)
            deflate = Deflate()
            output_stream = deflate.decompress(input_stream)
            output_stream.seek(0)

            text = output_stream.read().decode()

            self.text_info += '{}: {}\n'.format(keyword, text)

    @chunk_wrapper(False)
    def __read_iTXt(self):
        text_chunks = []
        for chunk in self.chunks:
            if chunk.name == b'iTXt':
                text_chunks.append(chunk)
        if self.text_info is None:
            self.text_info = ''

        for chunk in text_chunks:
            null_index_1 = chunk.data.index(0)
            keyword = chunk.data[0:null_index_1].decode(encoding='utf-8', errors='ignore')
            is_compressed, compression_method = chunk.data[null_index_1+1] == 1, chunk.data[null_index_1+2]
            if compression_method != 0:
                raise ValueError('Unrecognized compression method')

            null_index_2 = chunk.data[null_index_1+3:].index(0) + null_index_1 + 3
            language_tag = chunk.data[null_index_1+3:null_index_2].decode(encoding='utf-8', errors='ignore')

            null_index_3 = chunk.data[null_index_2+1:].index(0) + null_index_2 + 1
            translated_keyword = chunk.data[null_index_2+1:null_index_3].decode(encoding='utf-8', errors='ignore')

            raw_text = chunk.data[null_index_3+1:]
            text = ''
            if is_compressed:
                input_stream = BitInputStream(io.BytesIO(raw_text))
                input_stream.read_byte(), input_stream.read_byte()  # skip zlib header (always 2 bytes in PNG)
                deflate = Deflate()
                output_stream = deflate.decompress(input_stream)
                output_stream.seek(0)
                text = output_stream.read().decode(encoding='utf-8', errors='ignore')
            else:
                text = raw_text.decode(encoding='utf-8', errors='ignore')

            self.text_info += '{} (language: {}, translated: {}): {}\n'.format(keyword,
                                                                               language_tag,
                                                                               translated_keyword,
                                                                               text)

    def __find_first_chunk(self, chunk_name):
        for chunk in self.chunks:
            if chunk.name == chunk_name.encode():
                return chunk

    def __decode_idat_stream(self):
        data = b''
        for chunk in self.chunks:  # all data from IDAT chunks concatenated form a zlib packed data
            if chunk.name == b'IDAT':
                data = data + chunk.data

        input_stream = BitInputStream(io.BytesIO(data))

        input_stream.read_byte(), input_stream.read_byte()  # skip zlib header (always 2 bytes in PNG)

        deflate = Deflate()

        output_stream = deflate.decompress(input_stream)
        output_stream.seek(0)

        return output_stream.read()

    def __unfilter_image(self):
        def extract_from_pixel_map(i_, j_):
            if i_ < 0 or j_ < 0:
                return 0
            return self._pixel_map[i_][j_]

        filter_type, passed, current_row = None, 0, 0

        def reverse_sub(index):
            return self._temp_output_stream[index] + extract_from_pixel_map(current_row, index - self._gap)

        def reverse_up(index):
            return self._temp_output_stream[index] + extract_from_pixel_map(current_row - 1, index)

        def reverse_average(index):
            return self._temp_output_stream[index] + (extract_from_pixel_map(current_row, index - self._gap) +
                                                      extract_from_pixel_map(current_row - 1, index)) // 2

        def paeth_preducator(left, above, upper_left):
            pa, pb, pc = map(abs, (above - upper_left, left - upper_left, left - upper_left + above - upper_left))

            if pa <= pb and pa <= pc:
                return left
            elif pb <= pc:
                return above
            else:
                return upper_left

        def reverse_paeth(index):
            return self._temp_output_stream[index] + paeth_preducator(
                                                        extract_from_pixel_map(current_row, index - self._gap),
                                                        extract_from_pixel_map(current_row - 1, index),
                                                        extract_from_pixel_map(current_row - 1, index - self._gap))
        print(len(self._temp_output_stream))
        for i in range(0, len(self._temp_output_stream)):
            if filter_type is None:
                filter_type = self._temp_output_stream[i]
                continue
            byte = self._temp_output_stream[i]

            if filter_type == 0:
                self._pixel_map[current_row].append(byte)
            elif filter_type == 1:
                self._pixel_map[current_row].append(reverse_sub(i))
            elif filter_type == 2:
                self._pixel_map[current_row].append(reverse_up(i))
            elif filter_type == 3:
                self._pixel_map[current_row].append(reverse_average(i))
            elif filter_type == 4:
                self._pixel_map[current_row].append(reverse_paeth(i))
            passed += 1

            if passed == self.width:
                filter_type, passed = None, 0
                current_row += 1
                continue

        return None


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

    def __read_next_chunk(self):
        b_length = self.file.read(4)
        length = int(binascii.hexlify(b_length), 16)
        name = self.read(4)
        data = self.read(length)
        crc = self.read(4)
        chunk = Chunk(name, length, data, crc)
        if not self.__check_crc(chunk):
            raise ValueError('File seems to be corrupted')
        return chunk

    def __check_crc(self, chunk):
        data = chunk.name + chunk.data
        return binascii.crc32(data) == int(binascii.hexlify(chunk.crc), 16)

    def __is_png(self):
        if self.file:
            info = self.file.read(8)
            self.file.seek(0)
            return all(x == y for x, y in zip(info, (137, 80, 78, 71, 13, 10, 26, 10)))
        return False

    def __read_all_chunks(self):
        chunk = self.__read_next_chunk()
        while chunk.name != b'IEND':
            self.chunks.append(chunk)
            chunk = self.__read_next_chunk()
        self.chunks.append(chunk)

    def get_picture(self):
        if not self.file:
            raise ReferenceError('Nothing is opened')

        self.file.seek(0)
        if not self.__is_png():
            raise TypeError('File seems to be corrupted')
        self.file.read(8)  # PNG signature
        self.__read_all_chunks()

        return Picture(self.name, self.chunks)


def get_pic(picture):  # todo: delete this
    image = Image.new("RGB", (picture.width, picture.height), (0, 0, 0))
    pixels = image.load()

    colors = []
    i = 0
    while True:
        try:
            colors.append((picture._temp_output_stream[i], picture._temp_output_stream[i+1], picture._temp_output_stream[i+2]))
            i += 3
        except Exception:
            break
    for i in range(image.size[0]):
        for j in range(image.size[1]):
            pixels[i, j] = colors[j * image.size[0] + i]

    image.show()


def main():
    reader = Reader()
    picture = reader.open('pics/h.png').get_picture()
    # get_pic(picture)

if __name__ == '__main__':
    main()
