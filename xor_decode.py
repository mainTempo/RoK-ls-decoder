M = 0x7FFFFFFF
A = 16807
Q = 0x1F31D

HACK_SIG = bytes([0x1B, 0x2F, 0x16, 0x02, 0x32, 0x63, 0x62, 0x67])


def lcg_step(state: int):
    v0 = A * state - M * (state // Q)
    if v0 <= 0:
        v0 += M
    return v0, (v0 % M) + 1


def compute_seed(filename: str, flag: int) -> int:
    n = len(filename)
    if n <= 3:
        return flag
    seed = 0
    count = 0
    i = n - 1
    while i >= 0:
        if count > 10:
            break
        c = filename[i]
        if not (c == '.' or 'A' <= c <= 'Z' or 'a' <= c <= 'z' or '0' <= c <= '9'):
            break
        seed += ord(c)
        count += 1
        i -= 1
    return seed


def xor_v1(data: bytearray, size: int) -> bytearray:
    if size < 2:
        return data
    key = data[0] ^ 0x78
    if size - 16 > 1:
        count = ((size - 18) >> 4) + 1
        pos = 1
        for _ in range(count):
            for i in range(16):
                if pos + i < len(data):
                    data[pos + i] ^= key
            pos += 16
    return data


def xor_v2(data: bytearray, flag: int, filename: str) -> bytearray:
    seed = compute_seed(filename, flag)
    state, key = lcg_step(seed)

    if len(data) >= 5:
        if data[0] == 0x1B and bytes(data[1:5]) == b'LuaQ':
            data[0] = 0x01
        elif data[0] == 0x01 and all(
            (data[1 + k] ^ key) & 0xFF == b'LuaQ'[k] for k in range(4)
        ):
            data[0] = 0x1B

    v16 = 1
    v17 = flag // 10
    if v17 < 123:
        v17 = 123
    v18 = flag - 16
    v15 = key
    state_cur = state

    if v18 > 1:
        pos = 1
        while True:
            if v16 % v17 == 100:
                state_cur, v15 = lcg_step(state_cur)
            for i in range(16):
                if pos + i < len(data):
                    data[pos + i] ^= v15 & 0xFF
            pos += 16
            v16 += 16
            if not (v16 < v18):
                break
    return data


def decrypt_ls(data: bytes, filename: str) -> bytes:
    flag = len(data)
    data = bytearray(data)
    if flag < 2:
        return bytes(data)
    if flag <= 8 or bytes(data[:8]) == HACK_SIG:
        return bytes(xor_v1(data, flag))
    return bytes(xor_v2(data, flag, filename))
