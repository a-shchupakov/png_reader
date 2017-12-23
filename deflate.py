import io
from zlib import adler32
import code_tree
from bit_input_stream import BitInputStream

ONE_BIT = 1
TWO_BITS = 2
THREE_BITS = 3
FOUR_BITS = 4
FIVE_BITS = 5
SEVEN_BITS = 7
EIGHT_BITS = 8
SIXTEEN_BITS = 16


class Buffer:
    def __init__(self, size):
        self.data = [0] * size
        self.index = 0

    def append(self, value):
        self.data[self.index] = value
        self.index = (self.index + 1) % len(self.data)

    def copy(self, length, distance, output_stream):
        read_index = (self.index - distance + len(self.data)) % len(self.data)
        for _ in range(0, length):
            byte = self.data[read_index]
            read_index = (read_index + 1) % len(self.data)
            output_stream.write(bytes([byte]))
            self.append(byte)


class Deflate:
    def __init__(self, no_adler=False):
        self.fixed_literal_length_table = None
        self.fixed_distance_table = None
        self.dynamic_literal_length_table = None
        self.dynamic_distance_table = None
        self.input = None
        self.output = io.BytesIO()
        self.buffer = Buffer(2 ** 15)
        self.no_adler = no_adler
        self.__build_static_tables()

    def decompress(self, input_stream):
        self.input = input_stream
        while True:
            b_final = self.input.read() == 1
            b_type = self.input.read_bits(2)

            if b_type == 0:
                self.__decompress_uncompressed_data()
            elif b_type == 1:
                self.__decompress_huffman_data(self.fixed_literal_length_table, self.fixed_distance_table)
            elif b_type == 2:
                self.__build_dynamic_tables()
                self.__decompress_huffman_data(self.dynamic_literal_length_table, self.dynamic_distance_table)
            else:
                raise ValueError('Invalid compression type')

            if b_final:
                if self.no_adler:
                    break
                self.__check_adler32()
                break

        return self.output

    def __check_adler32(self):
        self.output.seek(0)

        expected_adler32 = int.from_bytes(self.input._input.read(), byteorder='big')
        actual_adler32 = adler32(self.output.read())

        if expected_adler32 != actual_adler32:
            raise ValueError('Adler32 checksum failed. File might be corrupted')

    def __build_static_tables(self):
        code_table = [8] * 144 + [9] * (256 - 144) + [7] * (280 - 256) + [8] * (288 - 280)
        self.fixed_literal_length_table = code_tree.CodeTree(code_table)

        dist_table = [5] * 32
        self.fixed_distance_table = code_tree.CodeTree(dist_table)

    def __build_dynamic_tables(self):
        hlit = self.input.read_bits(FIVE_BITS) + 257
        hdist = self.input.read_bits(FIVE_BITS) + 1

        hclen = self.input.read_bits(FOUR_BITS) + 4
        length_code_lengths = [0] * 19
        length_code_lengths[16] = self.input.read_bits(THREE_BITS)
        length_code_lengths[17] = self.input.read_bits(THREE_BITS)
        length_code_lengths[18] = self.input.read_bits(THREE_BITS)
        length_code_lengths[0] = self.input.read_bits(THREE_BITS)
        for i in range(0, hclen - 4):
            if i % 2 == 0:
                length_code_lengths[8 + i // 2] = self.input.read_bits(THREE_BITS)
            else:
                length_code_lengths[7 - i // 2] = self.input.read_bits(THREE_BITS)

        code_length_table = code_tree.CodeTree(length_code_lengths)

        code_lengths = [0] * (hlit + hdist)
        temp_value = -1
        temp_length = 0
        index = 0
        while index < len(code_lengths):
            if temp_length > 0:
                if temp_value == -1:
                    raise ValueError('Impossible state')
                code_lengths[index] = temp_value
                temp_length -= 1 
                index += 1
            else:
                symbol = self.__decode_literal(code_length_table)
                if 0 <= symbol <= 15:
                    code_lengths[index], temp_value = symbol, symbol
                    index += 1
                elif symbol == 16:
                    if temp_value == -1:
                        raise ValueError('Impossible state')
                    temp_length = self.input.read_bits(TWO_BITS) + 3
                elif symbol == 17:
                    temp_value, temp_length = 0, self.input.read_bits(THREE_BITS) + 3
                elif symbol == 18:
                    temp_value, temp_length = 0, self.input.read_bits(SEVEN_BITS) + 11

        if temp_length > 0:
            raise ValueError('Run exceeds number of codes')

        literal_length_table_length = code_lengths[:hlit]
        self.dynamic_literal_length_table = code_tree.CodeTree(literal_length_table_length)

        distance_table_length = code_lengths[hlit:]
        if len(distance_table_length) == 1 and distance_table_length[0] == 0:
            self.dynamic_distance_table = None
        else:
            one_temp_count, second_temp_count = 0, 0
            for x in distance_table_length:
                if x == 1:
                    one_temp_count += 1
                elif x > 0:
                    second_temp_count += 1

            if one_temp_count == 1 and second_temp_count == 0:
                if len(distance_table_length) < 32:
                    distance_table_length += [0] * (32 - len(distance_table_length))
                distance_table_length[31] = 1

            self.dynamic_distance_table = code_tree.CodeTree(distance_table_length)

    def __decompress_uncompressed_data(self):
        while self.input.get_bit_position() != 0:
            self.input.read()

        len = self.input.read_bits(SIXTEEN_BITS)
        nlen = self.input.read_bits(SIXTEEN_BITS)

        if (len ^ 0xFFFF) != nlen:
            raise ValueError('Invalid length in uncompressed block')

        for i in range(0, len):
            byte = self.input.read_byte()
            self.output.write(bytes([byte]))
            self.buffer.append(byte)

    def __decompress_huffman_data(self, length_table, distance_table):
        while True:
            symbol = self.__decode_literal(length_table)
            if symbol == 256:  # end of block
                break

            if symbol < 256:  # symbol is literal
                self.output.write(bytes([symbol]))
                self.buffer.append(symbol)
            else:  # symbol is length-distance pair
                length = self.__decode_length(symbol)
                if length < 3 or length > 258:
                    raise ValueError('Invalid run length')
                if not distance_table:
                    raise ValueError('Length symbol encountered with empty distance code')
                distance_byte = self.__decode_literal(distance_table)
                distance = self.__decode_distance(distance_byte)
                if distance < 1 or distance > 2 ** 15:
                    raise ValueError('Invalid distance')

                self.buffer.copy(length, distance, self.output)

    def __decode_literal(self, tree):
        current_node = tree.root
        while True:
            byte = self.input.read()
            next_node = None
            if byte == 0:
                next_node = current_node.left_child
            elif byte == 1:
                next_node = current_node.right_child
            else:
                raise ValueError

            if isinstance(next_node, code_tree.Leaf):
                return next_node.symbol

            current_node = next_node

    def __decode_length(self, symbol):
        if symbol < 257 or symbol > 287:
            raise ValueError('Invalid length value')
        elif symbol <= 264:
            return symbol - 254
        elif symbol <= 284:
            extra_bits = (symbol - 261) // 4
            return (((symbol - 265) % 4 + 4) << extra_bits) + 3 + self.input.read_bits(extra_bits)
        elif symbol == 285:
            return 258
        else:
            raise ValueError('Invalid length value')

    def __decode_distance(self, symbol):
        if symbol < 0 or symbol > 31:
            raise ValueError('Invalid distance symbol')
        if symbol <= 3:
            return symbol + 1
        elif symbol <= 29:
            extra_bits = symbol // 2 - 1
            return ((symbol % 2 + 2) << extra_bits) + 1 + self.input.read_bits(extra_bits)
        else:
            raise ValueError('Reserved distance symbol')
