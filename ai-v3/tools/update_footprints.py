"""Replace board footprints with their current library copies (the fix for
DRC 'lib_footprint_mismatch'), keeping everything that belongs to the
board: position, rotation, side, reference/value and every custom field,
the schematic path, pad nets, attributes and lock.

KiCad has no CLI for "Update footprints from library", so this uses
KiCad's own Python. Run with KiCad's interpreter, with the board closed
in the editor (or reload it afterwards):

    "C:/Program Files/KiCad/10.0/bin/python.exe" update_footprints.py \
        ../hardware/vancouver-skytrain-pcb.kicad_pcb Capacitor_SMD:C_0402_1005Metric [more lib:name ...]

The global footprint libraries are looked up under KiCad's share dir.
"""
import os
import sys

import pcbnew

SHARE = os.path.join(os.path.dirname(os.path.dirname(pcbnew.__file__)), "..", "..",
                     "share", "kicad", "footprints")
SHARE = os.path.normpath(SHARE)
if not os.path.isdir(SHARE):
    # python.exe lives in bin/; footprints in share/kicad/footprints
    SHARE = os.path.normpath(os.path.join(os.path.dirname(sys.executable), "..",
                                          "share", "kicad", "footprints"))


def replace(board, old, lib, name):
    new = pcbnew.FootprintLoad(os.path.join(SHARE, lib + ".pretty"), name)
    if new is None:
        raise SystemExit(f"{lib}:{name} not found under {SHARE}")
    new.SetFPID(old.GetFPID())
    # side first (Flip mirrors positions), then placement
    if old.IsFlipped():
        new.Flip(new.GetPosition(), False)
    new.SetPosition(old.GetPosition())
    new.SetOrientation(old.GetOrientation())
    new.SetPath(old.GetPath())
    new.SetAttributes(old.GetAttributes())
    new.SetLocked(old.IsLocked())
    # reference / value keep their board text placement and visibility
    for src, dst in ((old.Reference(), new.Reference()), (old.Value(), new.Value())):
        dst.SetText(src.GetText())
        dst.SetPosition(src.GetPosition())
        dst.SetTextAngle(src.GetTextAngle())
        dst.SetLayer(src.GetLayer())
        dst.SetVisible(src.IsVisible())
        dst.SetTextSize(src.GetTextSize())
        dst.SetTextThickness(src.GetTextThickness())
    # every other field (LCSC, MFG, Datasheet, Description ...)
    for field in old.GetFields():
        n = field.GetName()
        if n in ("Reference", "Value"):
            continue
        new.SetField(n, field.GetText())        # creates the user field if new
        f = new.GetField(n)
        if f is None:
            continue
        f.SetVisible(field.IsVisible())
        f.SetLayer(field.GetLayer())
        f.SetPosition(field.GetPosition())
        f.SetTextAngle(field.GetTextAngle())
        f.SetTextSize(field.GetTextSize())
    # pad nets by pad number - assigned after the footprint is on the
    # board, since net codes are resolved against the board's netlist
    old_nets = {p.GetNumber(): p.GetNetCode() for p in old.Pads()}
    board.Remove(old)
    board.Add(new)
    for p in new.Pads():
        code = old_nets.get(p.GetNumber())
        if code is not None:
            p.SetNetCode(code)
    nets = {p.GetNumber(): p.GetNetname() for p in new.Pads()}
    print(f"  {new.GetReference()}: pads -> {nets}")
    return new


def main():
    pcb = sys.argv[1]
    targets = set(sys.argv[2:])
    board = pcbnew.LoadBoard(pcb)
    done = []
    for fp in list(board.GetFootprints()):
        fpid = fp.GetFPID()
        key = f"{fpid.GetLibNickname()}:{fpid.GetLibItemName()}"
        if key in targets:
            replace(board, fp, str(fpid.GetLibNickname()), str(fpid.GetLibItemName()))
            done.append(fp.GetReference())
    pcbnew.SaveBoard(pcb, board)
    print(f"updated {len(done)} footprint(s) from library: {', '.join(sorted(done))}")


if __name__ == "__main__":
    main()
