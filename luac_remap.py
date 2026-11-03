import struct
from pathlib import Path


STD_OPNAMES = [
    "MOVE", "LOADK", "LOADBOOL", "LOADNIL", "GETUPVAL", "GETGLOBAL", "GETTABLE",
    "SETGLOBAL", "SETUPVAL", "SETTABLE", "NEWTABLE", "SELF", "ADD", "SUB", "MUL",
    "DIV", "MOD", "POW", "UNM", "NOT", "LEN", "CONCAT", "JMP", "EQ", "LT", "LE",
    "TEST", "TESTSET", "CALL", "TAILCALL", "RETURN", "FORLOOP", "FORPREP",
    "TFORLOOP", "SETLIST", "CLOSE", "CLOSURE", "VARARG",
]
STD_NAME2OP = {n: i for i, n in enumerate(STD_OPNAMES)}

GAME2STD_NAME = {
    7: "CLOSURE", 8: "CLOSE", 9: "SETLIST", 10: "TFORLOOP", 11: "FORPREP",
    12: "FORLOOP", 13: "RETURN", 14: "NEWTABLE", 15: "SELF", 16: "ADD",
    17: "SUB", 18: "MUL", 19: "DIV", 20: "MOD", 21: "POW", 22: "UNM",
    23: "NOT", 24: "SETTABLE", 25: "SETUPVAL", 26: "SETGLOBAL", 27: "GETTABLE",
    28: "GETGLOBAL", 29: "GETUPVAL", 30: "LOADNIL", 31: "LOADBOOL", 32: "LOADK",
    33: "MOVE", 34: "LEN", 35: "CONCAT", 36: "JMP", 37: "EQ", 38: "LT",
    39: "LE", 40: "TEST", 41: "TESTSET", 42: "CALL", 43: "TAILCALL",
    44: "VARARG",
}
GAME2STD = {g: STD_NAME2OP[n] for g, n in GAME2STD_NAME.items()}

LUA_SIG = b"\x1bLua"
HEADER = bytes([0x1B, 0x4C, 0x75, 0x61, 0x51, 0x00, 0x01, 0x04, 0x04, 0x04, 0x08, 0x00])
MAXARG_sBx = 131071

OP_MASK, A_MASK, B_MASK, C_MASK = 0x3F, 0xFF, 0x1FF, 0x1FF
A_SHIFT, C_SHIFT, B_SHIFT = 6, 14, 23
BIT_RK = 0x100


def decode(i):
    return (i & OP_MASK, (i >> A_SHIFT) & A_MASK, (i >> C_SHIFT) & C_MASK, (i >> B_SHIFT) & B_MASK)


def encode(op, a, c, b):
    return (op & OP_MASK) | ((a & A_MASK) << A_SHIFT) | ((c & C_MASK) << C_SHIFT) | ((b & B_MASK) << B_SHIFT)



class Proto:
    __slots__ = ("source", "linedefined", "lastlinedefined", "nups",
                 "numparams", "is_vararg", "maxstacksize", "code",
                 "constants", "protos", "lineinfo", "locvars", "upvalues")

    def __init__(self):
        self.source = None
        self.linedefined = 0
        self.lastlinedefined = 0
        self.nups = 0
        self.numparams = 0
        self.is_vararg = 0
        self.maxstacksize = 0
        self.code = []        
        self.constants = []   
        self.protos = []      
        self.lineinfo = []    
        self.locvars = []     
        self.upvalues = []    

    def opcode_stats(self):
        stats = {}
        for i in self.code:
            stats[i & OP_MASK] = stats.get(i & OP_MASK, 0) + 1
        for p in self.protos:
            for k, v in p.opcode_stats().items():
                stats[k] = stats.get(k, 0) + v
        return stats

    def iter_protos(self):
        yield self
        for p in self.protos:
            yield from p.iter_protos()


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def bytes(self, n):
        if self.p + n > len(self.d):
            raise ValueError(
                f"unexpected end of data at 0x{self.p:x} "
                f"(need {n}, have {len(self.d) - self.p})")
        r = self.d[self.p:self.p + n]
        self.p += n
        return r

    def byte(self):
        return self.bytes(1)[0]

    def int(self):
        return struct.unpack_from("<i", self.bytes(4))[0]

    def uint(self):
        return struct.unpack_from("<I", self.bytes(4))[0]

    def number(self):
        return struct.unpack_from("<d", self.bytes(8))[0]

    def string(self):
        size = self.uint()
        if size == 0:
            return None
        return self.bytes(size)[:-1]


class Writer:
    def __init__(self):
        self.buf = bytearray()

    def bytes(self, b):
        self.buf += b

    def byte(self, v):
        self.buf.append(v & 0xFF)

    def int(self, v):
        self.buf += struct.pack("<i", v)

    def uint(self, v):
        self.buf += struct.pack("<I", v)

    def number(self, v):
        self.buf += struct.pack("<d", v)

    def string(self, s):
        if s is None:
            self.uint(0)
        else:
            if isinstance(s, str):
                s = s.encode("utf-8", "surrogateescape")
            self.uint(len(s) + 1)
            self.buf += s + b"\x00"



CODE_KEY = bytes.fromhex(
    "1f5c48540d224f5f0a3b111c252f6039"
    "0d1d1b301f2b613b47164e560e234e60"
    "115c574429355745")


def lsx_block(b: bytes) -> bytes:
    if len(b) >= 0x20:
        return b
    out = bytearray(b)
    for i, v in enumerate(out):
        if v == 0:
            continue
        nv = v ^ CODE_KEY[i]
        if nv == 0:
            continue
        out[i] = nv
    return bytes(out)


class LSReader(Reader):
    def __init__(self, data):
        super().__init__(data)
        self.crypt = False

    def block(self, n):
        raw = self.bytes(n)
        return lsx_block(raw) if self.crypt else raw

    def int(self):
        return struct.unpack_from("<i", self.block(4))[0]

    def uint(self):
        return struct.unpack_from("<I", self.block(4))[0]

    def number(self):
        return struct.unpack_from("<d", self.block(8))[0]

    def byte(self):
        return self.block(1)[0]

    def string(self):
        size = self.uint()
        if size == 0:
            return None
        return self.block(size)[:-1]


def load_function(r: LSReader) -> Proto:
    p = Proto()
    p.source = r.string()
    p.linedefined = r.int()
    p.lastlinedefined = r.int()
    p.nups = r.byte()
    p.numparams = r.byte()
    p.is_vararg = r.byte()
    p.maxstacksize = r.byte()

    r.crypt = True

    n = r.int()
    if n < 0 or n > 5_000_000:
        raise ValueError(f"подозрительный ncode={n} at 0x{r.p:x}")
    if n:
        p.code = list(struct.unpack_from(f"<{n}I", r.block(4 * n)))

    n = r.int()
    if n < 0 or n > 1_000_000:
        raise ValueError(f"подозрительный nconst={n} at 0x{r.p:x}")
    for _ in range(n):
        t = r.byte()
        if t == 0:
            p.constants.append((0, None))
        elif t == 1:
            p.constants.append((1, bool(r.byte())))
        elif t == 3:
            p.constants.append((3, r.number()))
        elif t == 4:
            p.constants.append((4, r.string()))
        else:
            raise ValueError(f"bad constant type {t} at 0x{r.p:x}")

    n = r.int()
    if n < 0 or n > 65536:
        raise ValueError(f"подозрительный nproto={n} at 0x{r.p:x}")
    for _ in range(n):
        p.protos.append(load_function(r))

    n = r.int()
    if n != len(p.code):
        raise ValueError(f"nline {n} != ncode {len(p.code)} at 0x{r.p:x}")
    if n:
        p.lineinfo = list(struct.unpack_from(f"<{n}i", r.block(4 * n)))

    n = r.int()
    if n < 0 or n > 65536:
        raise ValueError(f"подозрительный nloc={n} at 0x{r.p:x}")
    for _ in range(n):
        name = r.string()
        start = r.int()
        end = r.int()
        p.locvars.append((name, start, end))

    n = r.int()
    if n != p.nups:
        raise ValueError(f"nupvalues {n} != nups {p.nups} at 0x{r.p:x}")
    p.upvalues = [r.string() for _ in range(n)]

    r.crypt = False
    return p


def load_chunk(data: bytes, ls_mode=True) -> Proto:
    if len(data) < 12:
        raise ValueError("файл слишком мал")
    if data[:4] != LUA_SIG:
        raise ValueError("не Lua-байткод (плохая сигнатура)")
    if data[:12] != HEADER:
        raise ValueError("неожиданный заголовок: " + data[:12].hex(" "))
    r = LSReader(data)
    r.crypt = False
    r.p = 12
    main = load_function(r)
    if r.p != len(data):
        raise ValueError(f"{len(data) - r.p} непрочитанных байт после main chunk ""(парсер рассинхронился)")
    return main



def dump_function(w: Writer, p: Proto, strip=False):
    w.string(None if strip else p.source)
    w.int(p.linedefined)
    w.int(p.lastlinedefined)
    w.byte(p.nups)
    w.byte(p.numparams)
    w.byte(p.is_vararg)
    w.byte(p.maxstacksize)

    w.int(len(p.code))
    for i in p.code:
        w.uint(i)

    w.int(len(p.constants))
    for t, v in p.constants:
        w.byte(t)
        if t == 0:
            pass
        elif t == 1:
            w.byte(1 if v else 0)
        elif t == 3:
            w.number(v)
        elif t == 4:
            w.string(v)
        else:
            raise ValueError(f"bad constant type {t}")

    w.int(len(p.protos))
    for sp in p.protos:
        dump_function(w, sp, strip)

    w.int(0 if strip else len(p.lineinfo))
    if not strip:
        for l in p.lineinfo:
            w.int(l)

    w.int(0 if strip else len(p.locvars))
    if not strip:
        for name, s, e in p.locvars:
            w.string(name)
            w.int(s)
            w.int(e)

    w.int(0 if strip else len(p.upvalues))
    if not strip:
        for n in p.upvalues:
            w.string(n)


def dump_chunk(p: Proto, strip=False) -> bytes:
    w = Writer()
    w.bytes(HEADER)
    dump_function(w, p, strip)
    return bytes(w.buf)


WARNINGS = []


def _decode_insn(i, ctx):
    op = i & OP_MASK
    a = (i >> A_SHIFT) & A_MASK
    c = (i >> C_SHIFT) & C_MASK
    b = (i >> B_SHIFT) & B_MASK

    if op not in GAME2STD:
        raise ValueError(f"{ctx}: неизвестный опкод {op} (0x{i:08x})")
    sop = GAME2STD[op]

    if sop == STD_NAME2OP["LOADNIL"]:
        return [(encode(sop, a, 0, b), None)]

    if sop == STD_NAME2OP["CONCAT"]:
        return [(encode(sop, a, c, b), None)]

    return [(encode(sop, a, c, b), None)]


def remap_proto(p: Proto, name="main"):
    old_n = len(p.code)
    decoded = []
    skip_raw = 0
    for pc, i in enumerate(p.code):
        if skip_raw:
            decoded.append((pc, [i]))
            skip_raw -= 1
            continue
        outs = _decode_insn(i, ctx=f"{name} pc={pc}")
        decoded.append((pc, outs))
        gop = i & OP_MASK
        if gop == 9 and ((i >> C_SHIFT) & C_MASK) == 0:
            skip_raw = 1

    map_old_new = [0] * (old_n + 1)
    new_code = []
    new_line = []
    for old_pc, outs in decoded:
        map_old_new[old_pc] = len(new_code)
        line = p.lineinfo[old_pc] if old_pc < len(p.lineinfo) else 0
        for o, _ in outs:
            new_code.append(o)
            new_line.append(line)
    map_old_new[old_n] = len(new_code)

    for old_pc, outs in decoded:
        for j, (o, _) in enumerate(outs):
            op = o & OP_MASK
            if op in (STD_NAME2OP["JMP"], STD_NAME2OP["FORLOOP"], STD_NAME2OP["FORPREP"]):
                i_old = p.code[old_pc]
                sBx = (i_old >> 14) - MAXARG_sBx
                target_old = old_pc + 1 + sBx
                new_pc = map_old_new[old_pc] + j
                target_new = map_old_new[min(target_old, old_n)]
                new_sBx = target_new - (new_pc + 1)
                bx = new_sBx + MAXARG_sBx
                if not (0 <= bx <= 0x3FFFF):
                    raise ValueError(f"{name} pc={old_pc}: jump target out of range")
                new_code[new_pc] = (new_code[new_pc] & ~0xFFFFC000 & 0xFFFFFFFF) | (bx << 14)

    p.code = new_code
    p.lineinfo = new_line

    def m(v):
        return map_old_new[min(v, old_n)]

    p.locvars = [(nm, m(s), m(e)) for nm, s, e in p.locvars]

    for j, sp in enumerate(p.protos):
        remap_proto(sp, f"{name}.{j}")


def convert(data: bytes, strip=False):
    WARNINGS.clear()
    proto = load_chunk(data)
    remap_proto(proto)
    return dump_chunk(proto, strip), proto


def disassemble(p: Proto, out=None, name="main", depth=0):
    out = [] if out is None else out
    ind = "  " * depth
    src = p.source.decode("utf-8", "replace") if p.source else "?"
    out.append(f"{ind}; proto '{name}' src={src} "
               f"lines {p.linedefined}-{p.lastlinedefined} "
               f"params={p.numparams} vararg={p.is_vararg} nups={p.nups} "
               f"stack={p.maxstacksize} instrs={len(p.code)}")
    for idx, i in enumerate(p.code):
        op, a, c, b = decode(i)
        oname = STD_OPNAMES[op] if op < len(STD_OPNAMES) else f"OP{op}"
        line = p.lineinfo[idx] if idx < len(p.lineinfo) else "?"
        extra = ""
        if op in (STD_NAME2OP["LOADK"], STD_NAME2OP["GETGLOBAL"],
                  STD_NAME2OP["SETGLOBAL"]):
            if b < len(p.constants):
                t, v = p.constants[b]
                extra = "  ; " + repr(v)[:80]
        elif op == STD_NAME2OP["CLOSURE"]:
            extra = f"  ; proto #{b}"
        elif op in (STD_NAME2OP["JMP"], STD_NAME2OP["FORPREP"],
                    STD_NAME2OP["FORLOOP"]):
            extra = f"  ; to {idx + 1 + (b - MAXARG_sBx)}"
        elif op == STD_NAME2OP["TFORLOOP"]:
            if idx + 1 < len(p.code):
                nxt = p.code[idx + 1]
                sbx = (nxt >> 14) - MAXARG_sBx - 1
                extra = f"  ; to {idx + 2 + sbx}"
        out.append(f"{ind}  [{idx:4d}] line {line:>5} {oname:<9} "
                   f"A={a:<3} B={b:<3} C={c:<3}{extra}")
    for j, sp in enumerate(p.protos):
        disassemble(sp, out, f"{name}.{j}", depth + 1)
    return out


def main():
    import sys
    args = sys.argv[1:]
    if not args:
        print("usage: python luac_remap.py <file.ls|file.luac> [--stats] [--disasm] [--out FILE] [--strip]")
        return
    src = Path(args[0])
    data = src.read_bytes()
    out, proto = convert(data, strip="--strip" in args)
    print(f"OK: {src.name}: {len(proto.code)} инструкций в main chunk")
    if "--stats" in args:
        inv = {}
        for g, s in GAME2STD.items():
            inv.setdefault(s, []).append(GAME2STD_NAME[g])
        for s, cnt in sorted(proto.opcode_stats().items(), key=lambda kv: -kv[1]):
            print(f"  std {s:>2} ({'/'.join(inv.get(s, []))}): {cnt}")
    if "--disasm" in args:
        lines = disassemble(proto)
        print("\n".join(lines[:400]))
        if len(lines) > 400:
            print(f"... (+{len(lines) - 400} строк, см. --out)")
    if "--out" in args:
        dst = args[args.index("--out") + 1]
        Path(dst).write_bytes(out)
        print(f"written: {dst}")
    for w in WARNINGS[:20]:
        print("WARN:", w)


if __name__ == "__main__":
    main()


