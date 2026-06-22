from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _render(dot_text: str, out_base: Path) -> Path:
    dot_path = out_base.with_suffix(".dot")
    dot_path.parent.mkdir(parents=True, exist_ok=True)
    dot_path.write_text(dot_text, encoding="utf-8")
    dot = shutil.which("dot")
    if dot:
        for fmt in ("svg", "png"):
            try:
                subprocess.run(
                    [dot, f"-T{fmt}", str(dot_path), "-o", str(out_base.with_suffix("." + fmt))],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            except Exception as exc:
                print(f"  graphviz {fmt} render failed: {exc}")
        print(f"  wrote {dot_path.name} (+ svg/png if graphviz present)")
    else:
        print(f"  wrote {dot_path.name} (install graphviz `dot` to render SVG/PNG)")
    return dot_path


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\l")


def curriculum_tree(out_dir: Path) -> None:
    print("curriculum tree ...")
    rows = [
        'digraph curriculum {',
        '  rankdir=TB; node [shape=box, style="rounded,filled", fontname="Helvetica"];',
        '  root [label="Two-dimensional curriculum", fillcolor="#1f2937", fontcolor=white];',
        '  axisL [label="Axis 1: language similarity\\l(high-resource source -> Python)\\l", fillcolor="#dbeafe"];',
        '  axisC [label="Axis 2: AST complexity tier\\l(easy -> hard, gated on val plateau)\\l", fillcolor="#dcfce7"];',
        '  root -> axisL; root -> axisC;',
        '  p1 [label="Phase 1: transfer warm-start\\lhigh-resource code/NL -> Python\\l", fillcolor="#eff6ff"];',
        '  p2 [label="Phase 2: COBOL adaptation\\l(curriculum over tiers)\\l", fillcolor="#f0fdf4"];',
        '  axisL -> p1; axisC -> p2;',
        '  t1 [label="Tier: SIMPLE\\l~62 progs, 94-97% auto\\l", fillcolor="#f0fdf4"];',
        '  t2 [label="Tier: MEDIUM\\l~220 progs, 78-85%\\l", fillcolor="#fef9c3"];',
        '  t3 [label="Tier: HIGH\\l~177 progs, 52-65%, review\\l", fillcolor="#fee2e2"];',
        '  p2 -> t1 -> t2 -> t3 [label="release on plateau"];',
        '  gold [label="gold: execution-verified pairs\\l(GnuCOBOL stdout match)\\l", fillcolor="#bbf7d0"];',
        '  silver [label="silver: LLM targets (unverified)\\learly tiers only\\l", fillcolor="#fde68a"];',
        '  t1 -> gold; t1 -> silver;',
        '}',
    ]
    _render("\n".join(rows), out_dir / "curriculum_tree")


def ast_pipeline(out_dir: Path) -> None:
    print("AST -> neural pipeline ...")
    from src.pipeline.stage1_parser import CobolParser, ComplexityScorer
    from src.pipeline.stage1_parser.normaliser import normalise_cobol

    sample = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-TOTAL PIC 9(4) VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           ADD 1 TO WS-TOTAL.\n"
        "           DISPLAY WS-TOTAL.\n"
        "           STOP RUN.\n"
    )
    parse = CobolParser().parse(normalise_cobol(sample).cobol)
    ast = parse.ast
    tier = ComplexityScorer().score(ast).tier if ast else "n/a"

    rows = [
        'digraph pipeline {',
        '  rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica"];',
        '  cob [label="COBOL source\\l(fixed-format)\\l", fillcolor="#e5e7eb"];',
        '  norm [label="normalise + lex\\l(strip cols 1-6/73-80)\\l", fillcolor="#e5e7eb"];',
        f'  ast [label="Stage-1 AST\\lroot={_esc(getattr(ast, "node_type", "Program"))}, tier={_esc(str(getattr(tier, "value", tier)))}\\l", fillcolor="#dbeafe"];',
    ]
    children = list(getattr(ast, "children", []) or [])[:5]
    for i, ch in enumerate(children):
        lbl = _esc(getattr(ch, "node_type", "Node"))
        rows.append(f'  n{i} [label="{lbl}", shape=box, fillcolor="#eff6ff"];')
        rows.append(f'  ast -> n{i};')
    rows += [
        '  prompt [label="PromptBuilder\\llinearised AST + tier token\\l", fillcolor="#fef9c3"];',
        '  enc [label="CodeT5+ encoder\\l(transformer stack)\\l", fillcolor="#dcfce7"];',
        '  dec [label="CodeT5+ decoder\\ltier-aware beam search\\l", fillcolor="#dcfce7"];',
        '  py [label="Python 3\\l(idiomatic translation)\\l", fillcolor="#bbf7d0"];',
        '  cob -> norm -> ast; ast -> prompt -> enc -> dec -> py;',
        '}',
    ]
    _render("\n".join(rows), out_dir / "ast_neural_pipeline")


def _module_tree_dot(model, max_depth: int) -> str:
    rows = [
        'digraph modules {',
        '  rankdir=TB; node [shape=box, style="rounded,filled", fontname="Courier", fillcolor="#eef2ff"];',
    ]
    counter = {"i": 0}
    ids = {}

    def nid(path):
        if path not in ids:
            ids[path] = f"m{counter['i']}"
            counter["i"] += 1
        return ids[path]

    def params(mod):
        return sum(p.numel() for p in mod.parameters())

    def walk(module, path, depth):
        for name, child in module.named_children():
            cpath = f"{path}/{name}"
            label = f"{name}: {type(child).__name__}\\l{params(child):,} params\\l"
            rows.append(f'  {nid(cpath)} [label="{_esc(label)}"];')
            rows.append(f'  {nid(path)} -> {nid(cpath)};')
            if depth + 1 < max_depth:
                walk(child, cpath, depth + 1)

    root_label = f"{type(model).__name__}\\l{params(model):,} params\\l"
    rows.append(f'  {nid("root")} [label="{_esc(root_label)}", fillcolor="#1f2937", fontcolor=white];')
    walk(model, "root", 0)
    rows.append("}")
    return "\n".join(rows)


def model_module_tree(out_dir: Path, backbone: str, checkpoint: str | None, max_depth: int) -> None:
    print(f"model module tree ({backbone}) ...")
    try:
        from transformers import AutoModelForSeq2SeqLM
    except ImportError:
        print("  transformers/torch not installed; run on the Mac venv. Skipped.")
        return
    src = checkpoint or backbone
    model = AutoModelForSeq2SeqLM.from_pretrained(src)
    _render(_module_tree_dot(model, max_depth), out_dir / "model_module_tree")
    txt = out_dir / "model_module_tree.txt"
    lines = []
    for name, mod in model.named_modules():
        depth = name.count(".")
        if name and depth < max_depth:
            n = sum(p.numel() for p in mod.parameters())
            lines.append("  " * depth + f"{name.split('.')[-1]} [{type(mod).__name__}] {n:,}")
    txt.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {txt.name}")


def forward_graph(out_dir: Path, backbone: str, checkpoint: str | None) -> None:
    print(f"forward computation graph ({backbone}) ...")
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError:
        print("  transformers/torch not installed; run on the Mac venv. Skipped.")
        return
    src = checkpoint or backbone
    tok = AutoTokenizer.from_pretrained(src)
    model = AutoModelForSeq2SeqLM.from_pretrained(src)
    enc = tok("MOVE 1 TO X", return_tensors="pt")
    dec = tok("x = 1", return_tensors="pt")
    try:
        from torchview import draw_graph

        g = draw_graph(
            model,
            input_data={"input_ids": enc["input_ids"], "decoder_input_ids": dec["input_ids"]},
            graph_name="codet5p_forward",
            depth=3,
            expand_nested=True,
            save_graph=False,
        )
        g.visual_graph.render(str(out_dir / "forward_graph"), format="svg", cleanup=True)
        print("  wrote forward_graph.svg (torchview)")
    except ImportError:
        print("  torchview not installed: `pip install torchview`. Skipped forward graph.")
    except Exception as exc:
        print(f"  forward graph failed: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", default="all", choices=["all", "model", "forward", "curriculum", "ast"])
    ap.add_argument("--out-dir", default="docs/figures")
    ap.add_argument("--backbone", default="Salesforce/codet5p-220m")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--max-depth", type=int, default=3)
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if a.which in ("all", "curriculum"):
        curriculum_tree(out)
    if a.which in ("all", "ast"):
        ast_pipeline(out)
    if a.which in ("all", "model"):
        model_module_tree(out, a.backbone, a.checkpoint, a.max_depth)
    if a.which in ("all", "forward"):
        forward_graph(out, a.backbone, a.checkpoint)
    print(f"figures in {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
