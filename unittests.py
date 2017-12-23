import unittest
import io
from reader import Picture, Reader
from deflate import Deflate
from bit_input_stream import BitInputStream


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.reader = Reader()
        self.picture = self.reader.open('pics/400x400.png').get_picture()

    def test_opens_picture(self):
        self.assertTrue(isinstance(self.picture, Picture))


class DeflateTests(unittest.TestCase):
    def setUp(self):
        self.deflate = Deflate()

    def test_decompress_data(self):
        data = b'\x73\x49\x4D\xCB\x49\x2C\x49\x55\x00\x11\x00'
        input_stream = BitInputStream(io.BytesIO(data))

        deflate = Deflate(no_adler=True)
        output_stream = deflate.decompress(input_stream)

        output_stream.seek(0)
        result = output_stream.read()
        self.assertEqual(result, b"Deflate late")


class BitInputStreamTests(unittest.TestCase):
    def setUp(self):
        self.input_stream = BitInputStream(io.BytesIO(b"\xB7\xC5\xBD\xDA\x5B\xD0\x3A\xD5\x19\x3A\x41\xA6"))

    def test_read_data(self):
        self.assertEquals(0, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(1, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(2, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(3, self.input_stream.get_bit_position())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(4, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(5, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(6, self.input_stream.get_bit_position())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(7, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())

        self.assertEquals(0, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(1, self.input_stream.get_bit_position())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(2, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(5, self.input_stream.get_bit_position())

        self.assertEquals(0xBD, self.input_stream.read_byte())

        self.assertEquals(0, self.input_stream.get_bit_position())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(6, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(7, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())

        self.assertEquals(0x5B, self.input_stream.read_byte())

        self.assertEquals(0, self.input_stream.get_bit_position())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(1, self.input_stream.get_bit_position())

        self.assertEquals(0x3A, self.input_stream.read_byte())

        self.assertEquals(0, self.input_stream.get_bit_position())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(2, self.input_stream.get_bit_position())

        self.assertEquals(0x19, self.input_stream.read_byte())

        self.assertEquals(0, self.input_stream.get_bit_position())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(1, self.input_stream.read())
        self.assertEquals(0, self.input_stream.read())
        self.assertEquals(7, self.input_stream.get_bit_position())

        self.assertEquals(0x41, self.input_stream.read_byte())
        self.assertEquals(0xA6, self.input_stream.read_byte())
        self.assertEquals(0, self.input_stream.get_bit_position())


if __name__ == '__main__':
    unittest.main()
