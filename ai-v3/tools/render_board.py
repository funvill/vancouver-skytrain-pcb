"""Render the top and bottom of the PCB as PNG images via KiCad's built-in
3D renderer (kicad-cli pcb render - KiCad 9+).

Usage:
    python render_board.py ../hardware/vancouver-skytrain-pcb.kicad_pcb ../test-results
    python render_board.py ../hardware/vancouver-skytrain-pcb.kicad_pcb ../test-results --kicad-cli "C:/Program Files/KiCad/9.0/bin/kicad-cli.exe"
"""
import argparse
import os
import subprocess
import sys

import glob


def newest_kicad_cli():
    """The newest installed KiCad's kicad-cli - a board saved by KiCad 10
    can't be loaded by the 9.0 CLI."""
    found = sorted(glob.glob(r"C:\Program Files\KiCad\*\bin\kicad-cli.exe"),
                   key=lambda p: [int(x) for x in p.split("\\")[3].split(".") if x.isdigit()])
    return found[-1] if found else r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"


DEFAULT_KICAD_CLI = newest_kicad_cli()


def render(kicad_cli, pcb, out_png, side, size=1400, quality="high"):
    cmd = [kicad_cli, "pcb", "render", pcb, "-o", out_png, "--side", side,
           "--width", str(size), "--height", str(size),
           "--quality", quality, "--background", "opaque"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"kicad-cli failed for side={side}")
    print(f"wrote {out_png}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcb")
    ap.add_argument("outdir")
    ap.add_argument("--kicad-cli", default=DEFAULT_KICAD_CLI)
    ap.add_argument("--size", type=int, default=1400)
    ap.add_argument("--quality", default="high",
                    choices=["basic", "high", "user"])
    args = ap.parse_args()
    if not os.path.exists(args.kicad_cli):
        raise SystemExit(f"kicad-cli not found at {args.kicad_cli} - pass "
                         f"--kicad-cli with the correct path")
    os.makedirs(args.outdir, exist_ok=True)
    render(args.kicad_cli, args.pcb, os.path.join(args.outdir, "board-top.png"),
           "top", args.size, args.quality)
    render(args.kicad_cli, args.pcb, os.path.join(args.outdir, "board-bottom.png"),
           "bottom", args.size, args.quality)


if __name__ == "__main__":
    main()
