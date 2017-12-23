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
