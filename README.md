**English** | [Русский](README.ru.md)
# RoK-ls-decoder

Decrypt and decompile Lua scripts from Rise of Kingdoms (`ls.dat`).
The logic is taken from `EngineDll.dll`.

`ls.dat` is a zip archive of encrypted `.ls` files (modified Lua 5.1 bytecode).  
This tool decrypts them, remaps the custom opcodes back to standard Lua 5.1, and runs unluac.

## Requirements

- Python 3.10+
- Java 11+

## Usage

```bash
python ls2lua.py "path/to/Rise Of Kingdoms Game"
python ls2lua.py "path/to/ls.dat" -o ./out
```

Options:

| Flag | Description |
|------|-------------|
| `-o PATH` | Output directory |
| `--workers N` | Parallel workers |
| `--keep-luac` | Keep intermediate `.luac` |
| `--skip-decompile` | Stop after remap |

Result goes to `rok_sources/`.

## Pipeline

```
ls.dat (zip)
  -> encrypted .ls
  -> xordecode (MainLsCypher)
  -> decrypted bytecode (\x1bLua...)
  -> luac_remap (opcode remap + LOADNIL/CONCAT/SETTABLE fixups)
  -> standard Lua 5.1 .luac
  -> unluac / BatchDecompile
  -> .lua
```

## Opcode map (game -> standard)

```
7:CLOSURE  8:CLOSE  9:SETLIST  10:TFORLOOP  11:FORPREP
12:FORLOOP 13:RETURN 14:NEWTABLE 15:SELF    16:ADD
17:SUB     18:MUL   19:DIV     20:MOD      21:POW
22:UNM     23:NOT   24:SETTABLE 25:SETUPVAL 26:SETGLOBAL
27:GETTABLE 28:GETGLOBAL 29:GETUPVAL 30:LOADNIL 31:LOADBOOL
32:LOADK   33:MOVE  34:LEN     35:CONCAT   36:JMP
37:EQ      38:LT    39:LE      40:TEST     41:TESTSET
42:CALL    43:TAILCALL 44:VARARG
```

Operand encoding differences that are corrected during remap:

- `LOADNIL` - game B is last register, standard B is count-1
- `CONCAT` - different A/B/C layout
- `SETTABLE` - different A/B/C layout

## Files

```
ls2lua.py   # entry point
xordecode.py     # MainLsCypher (sub_18007E7B0, base 0x180001000) port
luac_remap.py    # bytecode rewriter
unluac_bin/      # unluac + BatchDecompile
```

## Notes

Decryption keystream is derived from the filename (LCG / Park-Miller).  
Header toggle `0x1B` <-> `0x01` is handled automatically.

The retrieved files contain the complete game logic for *Rise of Kingdoms*; you can write a C++ injector to inject your own Lua code into the game. There is also a feature (`ScoutHandler.lua`) that decouples the maximum number of scouts from the Scout Camp level; this allows you to deploy the maximum of 3 scouts regardless of your Scout Camp's level. There may well be other features, too.
The game utilizes the `NEP2.dll` anti-cheat library; however, a standard DLL injection did not trigger any adverse effects, such as game crashes. It is possible that the injection is logged on the server side - you will need to reverse it yourself to confirm.
