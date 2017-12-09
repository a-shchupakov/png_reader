import io
import zlib

def main():
    b'73494dcb492c4955001100'
    data = b'\x73\x49\x4D\xCB\x49\x2C\x49\x55\x00'
    decode = zlib.decompress(data, wbits=-15)


if __name__ == '__main__':
    main()
