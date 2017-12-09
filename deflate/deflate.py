import io
from code_tree import CodeTree, Leaf
from bit_input_stream import BitInputStream as IO_Stream

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
    def __init__(self, input_stream):
        self.fixed_literal_length_table = None
        self.fixed_distance_table = None
        self.dynamic_literal_length_table = None
        self.dynamic_distance_table = None
        self.input = input_stream
        self.output = io.BytesIO()
        self.buffer = Buffer(2 ** 15)
        self.__build_static_tables()

    def decompress(self):
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
                raise RuntimeError('Invalid compression type')

            if b_final:
                break

        return self.output

    def __build_static_tables(self):
        code_table = [8] * 144 + [9] * (256 - 144) + [7] * (280 - 256) + [8] * (288 - 280)
        self.fixed_literal_length_table = CodeTree(code_table)

        dist_table = [5] * 32
        self.fixed_distance_table = CodeTree(dist_table)

    def __build_dynamic_tables(self):
        hlit = self.input.read_bits(FIVE_BITS) + 257
        hdist = self.input.read_bits(FIVE_BITS) + 1

        hclen = self.input.read_bits(FOUR_BITS) + 4
        temp_code_lengths = [0] * 19
        temp_code_lengths[16] = self.input.read_bits(THREE_BITS)
        temp_code_lengths[17] = self.input.read_bits(THREE_BITS)
        temp_code_lengths[18] = self.input.read_bits(THREE_BITS)
        temp_code_lengths[0] = self.input.read_bits(THREE_BITS)
        for i in range(0, hclen - 4):
            if i % 2 == 0:
                temp_code_lengths[8 + i / 2] = self.input.read_bits(THREE_BITS)
            else:
                temp_code_lengths[7 - i / 2] = self.input.read_bits(THREE_BITS)

        code_length_table = CodeTree(temp_code_lengths)

        code_lengths = [0] * (hlit + hdist)
        temp_value = -1
        temp_length = 0
        index = 0
        while index < len(code_lengths):
            if temp_length > 0:
                code_lengths[index] = temp_value
                temp_value -= 1
                index += 1
            else:
                symbol = self.__decode_literal(code_length_table)
                if 0 <= symbol <= 15:
                    code_lengths[index], temp_value = symbol, symbol
                    index += 1
                elif symbol == 16:
                    temp_length = self.input.read_bits(TWO_BITS) + 3
                elif symbol == 17:
                    temp_value, temp_length = 0, self.input.read_bits(THREE_BITS) + 3
                elif symbol == 18:
                    temp_value, temp_length = 0, self.input.read_bits(SEVEN_BITS) + 11

        literal_length_table_length = code_lengths[:hlit]
        self.dynamic_literal_length_table = CodeTree(literal_length_table_length)

        distance_table_length = code_lengths[hlit:]
        if len(distance_table_length) == 1 and distance_table_length[0] == 0:
            self.dynamic_distance_table = None
        else:
            one_temp_count, second_temp_count = 0
            for x in distance_table_length:
                if x == 1:
                    one_temp_count += 1
                elif x > 0:
                    second_temp_count += 1

            if one_temp_count == 1 and second_temp_count == 0:
                distance_table_length = distance_table_length[:32]
                distance_table_length[31] = 1

            self.dynamic_distance_table = CodeTree(distance_table_length)

    def __decompress_uncompressed_data(self):
        while self.input.get_bit_position() != 0:
            self.input.read()

        len = self.input.read_bits(SIXTEEN_BITS)
        nlen = self.input.read_bits(SIXTEEN_BITS)

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

                distance_byte = self.__decode_literal(distance_table)
                distance = self.__decode_distance(distance_byte)

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

            if isinstance(next_node, Leaf):
                return next_node.symbol

            current_node = next_node

    def __decode_length(self, symbol):
        if symbol < 257 or symbol > 287:
            raise RuntimeError('Invalid length value')
        elif symbol <= 264:
            return symbol - 254
        elif symbol <= 284:
            extra_bits = (symbol - 261) // 4
            return (((symbol - 265) % 4 + 4) << extra_bits) + 3 + self.input.read_bits(extra_bits)
        elif symbol == 285:
            return 258
        else:
            raise RuntimeError('Invalid length value')

    def __decode_distance(self, symbol):
        if symbol < 0 or symbol > 31:
            raise RuntimeError
        if symbol <= 3:
            return symbol + 1
        elif symbol <= 29:
            extra_bits = symbol // 2 - 1
            return ((symbol % 2 + 2) << extra_bits) + 1 + self.input.read_bits(extra_bits)
        else:
            raise RuntimeError


def main():
    data = b'\x73\x49\x4D\xCB\x49\x2C\x49\x55\x00\x11\x00'
    stream = io.BytesIO(data)
    bit_input_stream = IO_Stream(stream)

    deflate = Deflate(bit_input_stream)
    output_stream = deflate.decompress()

    output_stream.seek(0)
    print(output_stream.read())



if __name__ == '__main__':
    main()


