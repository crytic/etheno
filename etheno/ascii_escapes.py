from typing import Iterable, Union

CONTROL_CODES = {
    b'0'   : b'\0',
    b'a'   : b'\x07',	# alert
    b'b'   : b'\x08',	# backspace
    b'f'   : b'\x0C',	# form feed
    b'n'   : b'\x0A',	# newline (line feed)
    b'r'   : b'\x0D',	# carriage return
    b't'   : b'\x09',	# horizontal tab
    b'v'   : b'\x0B',	# vertical tab
    b'"'   : b'\x22',	# double quote
    b'&'   : b'',		# empty string
    b'\''  : b'\x27',	# single quote
    b'\\'  : b'\x5C',	# backslash
    b'NUL' : b'\0', 	# null character
    b'SOH' : b'\x01', 	# start of heading
    b'STX' : b'\x02', 	# start of text
    b'ETX' : b'\x03', 	# end of text
    b'EOT' : b'\x04', 	# end of transmission
    b'ENQ' : b'\x05', 	# enquiry
    b'ACK' : b'\x06', 	# acknowledge
    b'BEL' : b'\x07', 	# bell
    b'BS'  : b'\x08', 	# backspace
    b'HT'  : b'\x09', 	# horizontal tab
    b'LF'  : b'\x0A', 	# line feed (newline)
    b'VT'  : b'\x0B', 	# vertical tab
    b'FF'  : b'\x0C', 	# form feed
    b'CR'  : b'\x0D', 	# carriage return
    b'SO'  : b'\x0E', 	# shift out
    b'SI'  : b'\x0F', 	# shift in
    b'DLE' : b'\x10', 	# data link escape
    b'DC1' : b'\x11', 	# device control 1
    b'DC2' : b'\x12', 	# device control 2
    b'DC3' : b'\x13', 	# device control 3
    b'DC4' : b'\x14', 	# device control 4
    b'NAK' : b'\x15', 	# negative acknowledge
    b'SYN' : b'\x16', 	# synchronous idle
    b'ETB' : b'\x17', 	# end of transmission block
    b'CAN' : b'\x18', 	# cancel
    b'EM'  : b'\x19', 	# end of medium
    b'SUB' : b'\x1A', 	# substitute
    b'ESC' : b'\x1B', 	# escape
    b'FS'  : b'\x1C', 	# file separator
    b'GS'  : b'\x1D', 	# group separator
    b'RS'  : b'\x1E', 	# record separator
    b'US'  : b'\x1F', 	# unit separator
    b'SP'  : b'\x20', 	# space
    b'DEL' : b'\x7F', 	# delete
    b'^@'  : b'\0',
    b'^['  : b'\x1B',	# escape
    b'^\\' : b'\x1C',	# file separator
    b'^]'  : b'\x1D',	# group separator
    b'^^'  : b'\x1E',	# record separator
    b'^_'  : b'\x1F',	# unit separator
}

for i in range(26):
    CONTROL_CODES[bytes([ord('^'), ord('A') + i])] = bytes([i + 1])


def decode(text: Union[str, bytes, Iterable[int]]) -> bytes:
    escaped = None
    ret = b''
    for c in text:
        if isinstance(c, str):
            c = ord(c)
        c = bytes([c])
        if escaped is not None:

            escaped += c
            if escaped in CONTROL_CODES:
                ret += CONTROL_CODES[escaped]
                escaped = None
            elif len(escaped) >= 3:
                if len(escaped) == 3:
                    # see if it is an integer in the range [0, 255]
                    try:
                        value = int(escaped)
                        if 0 <= value <= 255:
                            ret += bytes([value])
                            escaped = None
                            continue
                    except ValueError:
                        pass
                raise ValueError(f"Unknown escape sequence: {escaped!r}")
        elif c == b'\\':
            escaped = b''
        else:
            ret += c
    return ret
