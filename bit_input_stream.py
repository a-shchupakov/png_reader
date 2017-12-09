import io


class BitInputStream:
    def __init__(self, input_stream):
        if not isinstance(input_stream, io.IOBase):
            raise TypeError
        self._input = input_stream
        self._current_byte = 0
        self._bits_remaining = 0

    def get_bit_position(self):
        return (8 - self._bits_remaining) % 8

    def read_byte(self):
        self._current_byte = 0
        self._bits_remaining = 0
        read = self._input.read(1)
        if read:
            return read[0]
        raise IOError

    def read(self):
        if self._bits_remaining == 0:
            new_byte = self._input.read(1)
            if new_byte:
                self._current_byte = new_byte[0]
                self._bits_remaining = 8
            else:
                raise IOError
        self._bits_remaining -= 1
        return (self._current_byte >> (7 - self._bits_remaining)) & 1

    def read_bits(self, number):
        """
        Reads the given number of bits from the bit input stream as a single integer, packed in little endian.
        :param number: number of bits to read
        :return: int-representation of read data
        """
        result = 0
        for i in range(0, number):
            result |= self.read() << i
        return result

    def close(self):
        self._input.close()
        self._current_byte = b''
        self._bits_remaining = 0


def main():
    input_stream = BitInputStream(io.BytesIO(b"\x63\xF8"))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print()
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    print(input_stream.read_bits(1))
    input_stream.close()


def assertEquals(a, b):
    print(a == b)


def test():
    input_stream = BitInputStream(io.BytesIO(b"\xB7\xC5\xBD\xDA\x5B\xD0\x3A\xD5\x19\x3A\x41\xA6"))
    assertEquals(0, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(1, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(2, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(3, input_stream.get_bit_position())
    assertEquals(0, input_stream.read())
    assertEquals(4, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(5, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(6, input_stream.get_bit_position())
    assertEquals(0, input_stream.read())
    assertEquals(7, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())

    assertEquals(0, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(1, input_stream.get_bit_position())
    assertEquals(0, input_stream.read())
    assertEquals(2, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(0, input_stream.read())
    assertEquals(0, input_stream.read())
    assertEquals(5, input_stream.get_bit_position())

    assertEquals(0xBD, input_stream.read_byte())

    assertEquals(0, input_stream.get_bit_position())
    assertEquals(0, input_stream.read())
    assertEquals(1, input_stream.read())
    assertEquals(0, input_stream.read())
    assertEquals(1, input_stream.read())
    assertEquals(1, input_stream.read())
    assertEquals(0, input_stream.read())
    assertEquals(6, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(7, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())

    assertEquals(0x5B, input_stream.read_byte())

    assertEquals(0, input_stream.get_bit_position())
    assertEquals(0, input_stream.read())
    assertEquals(1, input_stream.get_bit_position())

    assertEquals(0x3A, input_stream.read_byte())

    assertEquals(0, input_stream.get_bit_position())
    assertEquals(1, input_stream.read())
    assertEquals(0, input_stream.read())
    assertEquals(2, input_stream.get_bit_position())

    assertEquals(0x19, input_stream.read_byte())

    assertEquals(0, input_stream.get_bit_position())
    assertEquals(0, input_stream.read())
    assertEquals(1, input_stream.read())
    assertEquals(0, input_stream.read())
    assertEquals(1, input_stream.read())
    assertEquals(1, input_stream.read())
    assertEquals(1, input_stream.read())
    assertEquals(0, input_stream.read())
    assertEquals(7, input_stream.get_bit_position())

    assertEquals(0x41, input_stream.read_byte())
    assertEquals(0xA6, input_stream.read_byte())
    assertEquals(0, input_stream.get_bit_position())


if __name__ == '__main__':
    main()
