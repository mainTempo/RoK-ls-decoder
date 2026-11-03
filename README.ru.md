[English](README.md) | **Русский**
# RoK-ls-decoder

Расшифровка и декомпиляция Lua-скриптов из Rise of Kingdoms (`ls.dat`).
Логика взята из `Engine.dll`.

`ls.dat` - zip-архив с зашифрованными `.ls` файлами (модифицированный байткод Lua 5.1).  
Инструмент расшифровывает их, возвращает опкоды к стандартному Lua 5.1 и прогоняет через unluac.

## Требования

- Python 3.10+
- Java 11+
- `unluac_bin/` (class-файлы + `BatchDecompile`)

## Использование

```bash
python ls2lua.py "path/to/Rise Of Kingdoms Game"
python ls2lua.py "path/to/ls.dat" -o ./out
```

Опции:

| Флаг | Описание |
|------|----------|
| `-o PATH` | Папка для результата |
| `--workers N` | Количество потоков |
| `--keep-luac` | Оставить промежуточные `.luac` |
| `--skip-decompile` | Остановиться после ремапа |

Результат появляется в `rok_sources/`.

## Пайплайн

```
ls.dat (zip)
  -> encrypted .ls
  -> xordecode (MainLsCypher)
  -> расшифрованный байткод (\x1bLua...)
  -> luac_remap (ремап опкодов + фиксы LOADNIL/CONCAT/SETTABLE)
  -> стандартный Lua 5.1 .luac
  -> unluac / BatchDecompile
  -> .lua
```

## Карта опкодов (игра -> стандарт)

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

Отличия кодировки операндов, которые правятся при ремапе:

- `LOADNIL` - в игре B = последний регистр, в стандарте B = count-1
- `CONCAT` - другая раскладка A/B/C
- `SETTABLE` - другая раскладка A/B/C

## Файлы

```
ls2lua.py   # точка входа
xordecode.py     # порт MainLsCypher
luac_remap.py    # переписчик байткода
unluac_bin/      # unluac + BatchDecompile
```

## Примечания

Ключ шифрования считается из имени файла (LCG / Park-Miller).  
Переключение заголовка `0x1B` <-> `0x01` обрабатывается автоматически.

Полученные файлы являются полной логикой игры *Rise of Kingdoms*, вы можете написать инжектор своего луа кода в игру на С++. Также есть фича (`ScoutHandler.lua`) что на клиенте не связано максимальное кол-во разведчиков исходя из уровня лагеря разведчиков и то, сколько разведчиков вы отправили, соответственно можно использовать максимальные 3 разведчика несмотря на уровень лагеря. Возможно имеются еще какие то фичи.
Игра имеет библиотеку античита `NEP2.dll`, но после обычного длл инжекта никаких побочных эффектов от игры по типу краша и тд не было, есть шанс что инжект логируется на сервер, реверсите ее сами.