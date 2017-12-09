import binascii

#      Extra               Extra               Extra
# Code Bits Length(s) Code Bits Lengths   Code Bits Length(s)
# ---- ---- ------     ---- ---- -------   ---- ---- -------
#  257   0     3       267   1   15,16     277   4   67-82
#  258   0     4       268   1   17,18     278   4   83-98
#  259   0     5       269   2   19-22     279   4   99-114
#  260   0     6       270   2   23-26     280   4  115-130
#  261   0     7       271   2   27-30     281   5  131-162
#  262   0     8       272   2   31-34     282   5  163-194
#  263   0     9       273   3   35-42     283   5  195-226
#  264   0    10       274   3   43-50     284   5  227-257
#  265   1  11,12      275   3   51-58     285   0    258
#  266   1  13,14      276   3   59-66

#      Extra           Extra               Extra
# Code Bits Dist  Code Bits   Dist     Code Bits Distance
# ---- ---- ----  ---- ----  ------    ---- ---- --------
#   0   0    1     10   4     33-48    20    9   1025-1536
#   1   0    2     11   4     49-64    21    9   1537-2048
#   2   0    3     12   5     65-96    22   10   2049-3072
#   3   0    4     13   5     97-128   23   10   3073-4096
#   4   1   5,6    14   6    129-192   24   11   4097-6144
#   5   1   7,8    15   6    193-256   25   11   6145-8192
#   6   2   9-12   16   7    257-384   26   12  8193-12288
#   7   2  13-16   17   7    385-512   27   12 12289-16384
#   8   3  17-24   18   8    513-768   28   13 16385-24576
#   9   3  25-32   19   8   769-1024   29   13 24577-32768

ONE_BIT = 1
TWO_BITS = 2
FIVE_BITS = 5
SEVEN_BITS = 7
EIGHT_BITS = 8
NINE_BITS = 9
SIXTEEN_BITS = 16


class Deflate:
    _static_border_table = {7: [('0000000', '0010111', 256, 'pair')],
                            8: [('00110000', '10111111', 0, 'literal'),
                                ('11000000', '11000111', 280, 'pair')],
                            9: [('110010000', '111111111', 144, 'literal')]}

    _length_table = {257: (0, 3), 258: (0, 4), 259: (0, 5), 260: (0, 6), 261: (0, 7), 262: (0, 8), 263: (0, 9),
                     264: (0, 10), 265: (1, 11), 266: (1, 13), 267: (1, 15), 268: (1, 17), 269: (2, 19),
                     270: (2, 23), 271: (2, 27), 272: (2, 31), 273: (3, 35), 274: (3, 43), 275: (3, 51),
                     276: (3, 59), 277: (4, 67), 278: (4, 83), 279: (4, 99), 280: (4, 115), 281: (5, 131),
                     282: (5, 163), 293: (5, 195), 284: (5, 227), 285: (0, 258)}

    _distance_table = {0: (0, 1), 1: (0, 2), 2: (0, 3), 3: (0, 4), 4: (1, 5), 5: (1, 7), 6: (2, 9), 7: (2, 13),
                       8: (3, 17), 9: (3, 25), 10: (4, 33), 11: (4, 49), 12: (5, 65), 13: (5, 97), 14: (6, 129),
                       15: (6, 193), 16: (7, 257), 17: (7, 385), 18: (8, 513), 19: (8, 769), 20: (9, 1025),
                       21: (9, 1537), 22: (10, 2049), 23: (10, 3073), 24: (11, 4097), 25: (11, 6145),
                       26: (12, 8193), 27: (12, 12289), 28: (13, 16385), 29: (13, 24577)}

    @staticmethod
    def _decode_uncompressed_data(unit):
        print('Uncompressed')
        length = int(unit.read_bits(SIXTEEN_BITS), 2)
        n_length = unit.read_bits(SIXTEEN_BITS)
        result = b''
        for _ in range(0, length):
            pass
        return result

    @staticmethod
    def _decode_static_huffman(unit):
        print('Static huffman')

        def get_next_value():
            """
            :return: Возвращает int - код символа
            """
            nonlocal is_pair
            value = unit.read_bits(SEVEN_BITS)
            modified, v_type = Deflate._modify_value_using_table(value, SEVEN_BITS)
            i = 0
            while not modified:
                value += unit.read_bits(ONE_BIT)
                modified, v_type = Deflate._modify_value_using_table(value, SEVEN_BITS + ONE_BIT + i)
                i += 1

            is_pair = (v_type == 'pair')
            return modified

        result = b''
        is_pair = False
        while True:
            next_value = get_next_value()
            if next_value == 256:  # Означает конец блока данных
                break
            if not is_pair:
                result += binascii.unhexlify(hex(next_value)[2:])
            else:
                extra_len_bits, length = Deflate._length_table[next_value]
                extra_len_value = unit.read_bits(extra_len_bits)[::-1]  # ревёрсим, т.к. хранится в прямом порядке
                length += int(extra_len_value, 2) if len(extra_len_value) else 0

                shift = int(unit.read_bits(FIVE_BITS)[::-1], 2)  # ревёрсим, т.к. хранится в прямом порядке
                extra_distance_bits, distance = Deflate._distance_table[shift]
                extra_distance_value = unit.read_bits(extra_distance_bits)[::-1]
                distance += int(extra_distance_value, 2) if len(extra_distance_value) else 0

                to_add = (result[-distance:])[:length]
                result += to_add
                is_pair = False

        return result

    @staticmethod
    def _modify_value_using_table(value, bits_read):
        for border in Deflate._static_border_table[bits_read]:
            left_border, right_border, int_value = map(lambda x: int(x, 2), (border[0], border[1], value))
            shift, v_type = border[2], border[3]
            if left_border <= int_value <= right_border:
                new_value = int_value - left_border + shift
                return new_value, v_type
        return None, None

    @staticmethod
    def _decode_dynamic_huffman(unit):
        print('Dynamic huffman')
        return b''

    @staticmethod
    def _reserved_function(unit):
        print('Reserved')
        return b''

    _uncompress_methods = {'00': _decode_uncompressed_data,
                           '01': _decode_static_huffman,
                           '10': _decode_dynamic_huffman,
                           '11': _reserved_function}

    @staticmethod
    def decode(data):
        result = b''
        unit = StringExt(_get_bits(data))
        while True:
            b_final, b_type = unit.read_bits(ONE_BIT), unit.read_bits(TWO_BITS)[::-1]
            result += Deflate._uncompress(unit, b_type)
            if b_final:
                break
        return result

    @staticmethod
    def _uncompress(unit, b_type):
        return Deflate._uncompress_methods[b_type].__func__(unit)


class StringExt:
    def __init__(self, string):
        self.string = string
        self.read = 0

    def read_bits(self, n):
        result = self.string[self.read:self.read+n]
        self.read += n
        return result


def _get_bits(hex_string):
    bytes_ = []
    for i in range(0, len(hex_string), 2):
        bytes_.append(hex_string[i:i+2])
    binary_iterable = map(lambda x: bin(int(x, SIXTEEN_BITS))[2:].zfill(EIGHT_BITS), bytes_)
    binary_string = ''
    for y in binary_iterable:
        binary_string += y[::-1]
    return binary_string


def main():
    data = b'73494dcb492c4955001100'
    result = Deflate.decode(data)
    print(result)

if __name__ == '__main__':
    main()
