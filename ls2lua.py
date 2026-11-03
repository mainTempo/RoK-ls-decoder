from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import xor_decode
import luac_remap as L


def find_ls_dat(game_path: Path) -> Path:
    game_path = game_path.resolve()

    if game_path.is_file() and game_path.name.lower() == "ls.dat":
        return game_path

    candidates = [
        game_path / "MASS_Data" / "StreamingAssets" / "ls.dat",
        game_path / "StreamingAssets" / "ls.dat",
        game_path / "ls.dat",
    ]
    for c in candidates:
        if c.is_file():
            return c

    for p in game_path.rglob("ls.dat"):
        if p.is_file():
            return p

    raise FileNotFoundError(f"ls.dat not found in {game_path}")


def extract_zip(ls_dat: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ls_files = []

    with zipfile.ZipFile(ls_dat, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            target = out_dir / name
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            if name.lower().endswith(".ls"):
                ls_files.append(target)

    return sorted(ls_files)


def decrypt_one(ls_path: Path, dec_dir: Path) -> tuple[str, bool, str]:
    try:
        raw = ls_path.read_bytes()
        decrypted = xor_decode.decrypt_ls(raw, ls_path.name)
        out = dec_dir / ls_path.name
        out.write_bytes(decrypted)
        ok = decrypted[:4] == b"\x1bLua"
        return ls_path.name, ok, "ok" if ok else "bad signature"
    except Exception as e:
        return ls_path.name, False, str(e)


def remap_one(args) -> tuple[str, bool, str]:
    ls_path_str, luac_dir_str = args
    ls_path = Path(ls_path_str)
    luac_dir = Path(luac_dir_str)

    try:
        raw = ls_path.read_bytes()
        if raw[:4] != b"\x1bLua":
            return ls_path.name, False, "not bytecode"
        remapped, _ = L.convert(raw)
        (luac_dir / (ls_path.stem + ".luac")).write_bytes(remapped)
        return ls_path.name, True, f"{len(remapped)} bytes"
    except Exception as e:
        return ls_path.name, False, str(e)


def find_unluac(base: Path) -> str | None:
    candidates = [
        base / "unluac_bin",
        Path(__file__).parent / "unluac_bin",
    ]
    for c in candidates:
        if (c / "unluac" / "Main.class").exists() or (c / "unluac").is_dir():
            return str(c.resolve())
    for jar in [base / "unluac.jar", Path("unluac.jar")]:
        if jar.exists():
            return str(jar.resolve())
    return None


def main():
    parser = argparse.ArgumentParser(description="Extract and decompile Lua sources from ROK ls.dat")
    parser.add_argument("game_path", help="Path to game folder or ls.dat")
    parser.add_argument("-o", "--output", default=None, help="Output directory")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    parser.add_argument("--keep-luac", action="store_true")
    parser.add_argument("--skip-decompile", action="store_true")
    args = parser.parse_args()

    game_path = Path(args.game_path)
    if not game_path.exists():
        print(f"[!] path not found: {game_path}")
        sys.exit(1)

    out_root = Path(args.output) if args.output else Path.cwd() / "rok_sources"
    out_root = out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"[*] looking for ls.dat...")
    try:
        ls_dat = find_ls_dat(game_path)
    except FileNotFoundError as e:
        print(f"[!] {e}")
        sys.exit(1)
    print(f"[+] {ls_dat}")

    work = out_root / "_work"
    encrypted_dir = work / "encrypted"
    decrypted_dir = work / "decrypted"
    for d in (encrypted_dir, decrypted_dir, out_root):
        d.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    print(f"[*] extracting zip...")
    ls_files = extract_zip(ls_dat, encrypted_dir)
    print(f"[+] {len(ls_files)} .ls files")

    if not ls_files:
        print("[!] no .ls files inside ls.dat")
        sys.exit(1)

    print(f"[*] decrypting ({args.workers} workers)...")
    ok_dec = fail_dec = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(decrypt_one, p, decrypted_dir): p for p in ls_files}
        for fut in as_completed(futs):
            name, success, msg = fut.result()
            if success:
                ok_dec += 1
            else:
                fail_dec += 1
                if fail_dec <= 5:
                    print(f"    FAIL decrypt {name}: {msg}")
    print(f"[+] decrypt: OK={ok_dec} FAIL={fail_dec}")

    decrypted_files = sorted(decrypted_dir.glob("*.ls"))
    if not decrypted_files:
        print("[!] no valid files after decrypt")
        sys.exit(1)

    luac_dir = work / "luac"
    luac_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] remapping opcodes ({args.workers} workers)...")
    ok_remap = fail_remap = 0
    jobs = [(str(p), str(luac_dir)) for p in decrypted_files]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(remap_one, j): j for j in jobs}
        done = 0
        for fut in as_completed(futs):
            name, success, msg = fut.result()
            done += 1
            if success:
                ok_remap += 1
            else:
                fail_remap += 1
                if fail_remap <= 5:
                    print(f"    FAIL remap {name}: {msg}")
            if done % 1000 == 0:
                print(f"    {done}/{len(jobs)}")
    print(f"[+] remap: OK={ok_remap} FAIL={fail_remap}")

    if args.skip_decompile:
        for f in luac_dir.glob("*.luac"):
            shutil.copy2(f, out_root / f.name)
        print(f"[+] done (remap only) -> {out_root}")
        return

    unluac_cp = find_unluac(Path(__file__).parent)
    if not unluac_cp:
        print("[!] unluac_bin not found")
        print("    put unluac_bin/ next to this script or use --skip-decompile")
        sys.exit(1)

    print(f"[*] decompiling (BatchDecompile)...")
    cmd = [
        "java", "-cp", unluac_cp,
        "BatchDecompile",
        str(luac_dir),
        str(out_root),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if res.stdout:
            print(res.stdout.strip())
        if res.returncode != 0 and res.stderr:
            print(res.stderr.strip()[:500])
    except subprocess.TimeoutExpired:
        print("[!] BatchDecompile timeout")
    except FileNotFoundError:
        print("[!] java not found in PATH")
        sys.exit(1)

    lua_count = len(list(out_root.glob("*.lua")))

    if not args.keep_luac:
        try:
            shutil.rmtree(work)
        except Exception:
            pass
    else:
        keep_dir = out_root / "luac"
        if keep_dir.exists():
            shutil.rmtree(keep_dir)
        shutil.move(str(luac_dir), str(keep_dir))
        try:
            shutil.rmtree(work)
        except Exception:
            pass

    elapsed = time.time() - t0
    print()
    print(f"done in {elapsed:.1f}s")
    print(f"  lua files : {lua_count}")
    print(f"  output    : {out_root}")


if __name__ == "__main__":
    main()
