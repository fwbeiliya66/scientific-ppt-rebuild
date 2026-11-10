#!/usr/bin/env python3
"""SYNTHETIC DEMO: generate a controlled public fixture. No network or OCR."""

import csv
import hashlib
import importlib.util
import io
import math
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
import pymupdf


HERE = Path(__file__).resolve().parent
TEAL = "#087F83"
GRAPHITE = "#20363E"
MUTED = "#5B7076"
RULE = "#D8E4E3"
PALE = "#EDF6F5"
ORANGE = "#AD592C"


def signals(x):
    return math.exp(-0.08 * x), 0.7 * math.exp(-0.04 * x)


def draft_signals(x):
    return 0.95 * math.exp(-0.02 * x), 0.4 * math.exp(-0.10 * x)


def make_data():
    rows = [(x, *signals(x)) for x in range(41)]
    with (HERE / "data.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["x", "y_A", "y_B", "data_kind"])
        writer.writerows((x, f"{a:.12f}", f"{b:.12f}", "SYNTHETIC DEMO")
                         for x, a, b in rows)
    return rows


def make_figure(draft=False):
    # Pillow's bundled font avoids dependency on machine-specific font files.
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    values = draft_signals if draft else signals

    def text(x, y, value, size=28, color=GRAPHITE, anchor="la"):
        draw.text((x, y), value, font=ImageFont.load_default(size=size),
                  fill=color, anchor=anchor)

    def point(x, y):
        return 180 + x / 40 * 1290, 800 - y / 1.05 * 570

    draw.rectangle((1, 1, 1598, 998), outline=RULE, width=2)
    text(65, 45, "INTENTIONALLY INCORRECT DEMO" if draft else "SYNTHETIC DEMO",
         25, ORANGE if draft else TEAL)
    text(1535, 45, "SYNTHETIC / UNVERIFIED DRAFT" if draft else "FORMULAS / NO OBSERVATIONS",
         23, MUTED, "ra")
    text(65, 102, "Deliberately wrong draft curves" if draft else "Two deterministic decay curves", 40)
    for y in range(6):
        value = y / 5
        _, py = point(0, value)
        draw.line((180, py, 1470, py), fill=RULE, width=2)
        text(153, py, f"{value:.1f}", 28, MUTED, "rm")
    for x in range(0, 41, 10):
        px, _ = point(x, 0)
        draw.line((px, 800, px, 811), fill=MUTED, width=2)
        text(px, 829, str(x), 28, MUTED, "ma")
    draw.line((180, 230, 180, 800, 1470, 800), fill=MUTED, width=3)
    # Dense deterministic samples draw smooth formula curves; CSV uses unit steps.
    draw.line([point(x / 10, values(x / 10)[0]) for x in range(401)],
              fill=TEAL, width=8, joint="curve")
    for i in range(0, 160, 4):
        xs = [i / 4, (i + 1) / 4, (i + 2) / 4]
        draw.line([point(x, values(x)[1]) for x in xs],
                  fill=GRAPHITE, width=7, joint="curve")
    draw.line((1020, 173, 1092, 173), fill=TEAL, width=8)
    text(1110, 173, "Curve A", 28, GRAPHITE, "lm")
    for x in (1272, 1300):
        draw.line((x, 173, x + 18, 173), fill=GRAPHITE, width=7)
    text(1340, 173, "Curve B", 28, GRAPHITE, "lm")
    text(825, 891, "x (arbitrary units)", 30, MUTED, "ma")
    label = Image.new("RGBA", (640, 55))
    ImageDraw.Draw(label).text((320, 27), "Synthetic signal (a.u.)",
                              font=ImageFont.load_default(size=30),
                              fill=MUTED, anchor="mm")
    label = label.rotate(90, expand=True)
    image.paste(label, (48, 195), label)
    text(180, 952, "WRONG: A = 0.95 exp(-0.02x)  |  B = 0.4 exp(-0.10x)" if draft else
         "A = exp(-0.08x)  |  B = 0.7 exp(-0.04x)", 25, MUTED)
    image.save(HERE / ("draft-figure.png" if draft else "source-figure.png"), optimize=False)


def make_paper():
    paper = pymupdf.open()
    page = paper.new_page(width=612, height=792)
    paper.set_metadata({
        "title": "SYNTHETIC DEMO - A synthetic two-curve fixture",
        "author": "Synthetic demo",
        "creator": "Scientific PPT Rebuild demo generator",
        "subject": "Formula-generated fixture; not a publication or scientific evidence",
    })

    def rgb(color):
        return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def text(x, y, value, size=11, font="Helvetica", color=GRAPHITE):
        fontname = {"Helvetica": "helv", "Helvetica-Bold": "hebo", "Courier": "cour"}[font]
        page.insert_text((x, 792 - y), value, fontsize=size,
                         fontname=fontname, color=rgb(color))

    def rule(y):
        page.draw_line((48, 792 - y), (564, 792 - y), color=rgb(RULE), width=1)

    text(48, 744, "SYNTHETIC DEMO / CONTROLLED PUBLIC FIXTURE", 9,
         "Helvetica-Bold", TEAL)
    text(48, 710, "A synthetic two-curve fixture", 26, "Helvetica-Bold")
    text(48, 688, "Formula-generated values for an editable-slide demonstration.", 11, color=MUTED)
    rule(670)
    text(48, 646, "ABSTRACT", 9, "Helvetica-Bold", TEAL)
    text(48, 628, "This one-page document supplies a clearly labeled synthetic figure and its")
    text(48, 612, "definitions. It is a controlled source artifact for inspecting image preservation")
    text(48, 596, "and editable slide structure. It reports no study, experiment, or observations.")
    text(48, 570, "1. Defined signals", 14, "Helvetica-Bold")
    text(48, 546, "y_A(x) = exp(-0.08 x)", 14, "Courier")
    text(48, 525, "y_B(x) = 0.7 exp(-0.04 x)", 14, "Courier")
    text(48, 503, "CSV samples: integer x from 0 to 40. No randomness or measurements.", 10, color=MUTED)
    page.insert_image(pymupdf.Rect(48, 309.5, 564, 632),
                      filename=str(HERE / "source-figure.png"))
    text(48, 141, "Figure 1. Deterministic decay curves defined above. Curve A is a solid teal line;", 9.5)
    text(48, 126, "Curve B is a dashed graphite line. Arbitrary units; this is not measured data.", 9.5)
    text(48, 99, "SYNTHETIC DEMO / Not a publication, study, or scientific evidence.", 9,
         "Helvetica-Bold", ORANGE)
    rule(83)
    text(48, 66, "Controlled public fixture | No authors, affiliations, DOI, or citations", 8.5, color=MUTED)
    text(545, 66, "1 / 1", 8.5, color=MUTED)
    paper.save(HERE / "synthetic-paper.pdf", deflate=True, no_new_id=True)
    paper.close()


def make_slide(draft=False):
    builder_path = (HERE.parents[1] / "skills" / "scientific-ppt-rebuild" /
                    "runtime" / "build_pptx_from_manifest.py")
    spec = importlib.util.spec_from_file_location("fixture_builder", builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    boxes, shapes = [], []

    def text(name, value, x, y, w, h, size, color=GRAPHITE, bold=False, **options):
        boxes.append(dict(id=name, text=value, left=x, top=y, width=w, height=h,
                          font="Arial", font_size=size, color=color, bold=bold,
                          fit_text=False, **options))

    def shape(name, x, y, w, h, fill="none", stroke="none", kind="rect", **options):
        shapes.append(dict(id=name, type=kind, left=x, top=y, width=w, height=h,
                           fill=fill, stroke=stroke, **options))

    text("synthetic-label", "SYNTHETIC DEMO", .62, .35, 3.5, .20, 10, TEAL, True,
         group_id="slide-header")
    text("fixture-label", "CONTROLLED FIXTURE / 01", 9.1, .35, 3.61, .20, 10, MUTED,
         align="right", group_id="slide-header")
    text("slide-title", "Two curves. Editable structure.", .62, .83, 12.1, .55, 30,
         bold=True, group_id="slide-header")
    text("slide-subtitle", "Deterministic mathematics for testing slide reconstruction.",
         .62, 1.46, 12.1, .3, 14, MUTED, group_id="slide-header")
    shape("header-rule", .62, 1.91, 12.09, .012, RULE, group_id="slide-header")
    text("formula-heading", "01 / FORMULAS", 8.15, 2.17, 4.56, .22, 10, TEAL, True)
    for name, index, formula, y in [
        ("equation-A", "A", "(x) = exp(-0.08x)", 2.56),
        ("equation-B", "B", "(x) = 0.7 exp(-0.04x)", 3.08),
    ]:
        text(name, "", 8.15, y, 4.56, .39, 17.5,
             runs=[{"text": "y"}, {"text": index, "baseline": -25000, "font_size": 13},
                   {"text": formula}])
    text("sampling-description", "CSV: x = 0 to 40, at unit steps.\nValues are generated, never observed.",
         8.15, 3.66, 4.56, .66, 13, MUTED)
    text("flow-heading", "02 / EDITABLE FLOW", 8.15, 4.46, 4.56, .22, 10, TEAL, True)
    for index, label in enumerate(["Define", "Sample", "Plot"]):
        x = 8.15 + index * 1.59
        shape(f"flow-step-{index + 1}", x, 4.85, 1.2, .55, PALE, RULE, stroke_width=.75)
        text(f"flow-label-{index + 1}", label, x, 4.85, 1.2, .55, 11.5, TEAL,
             bold=True, align="center", valign="middle")
        if index < 2:
            shape(f"flow-arrow-{index + 1}", x + 1.31, 5.125, .17, 0,
                  stroke=TEAL, kind="line", stroke_width=1.2, tail_end="triangle")
    shape("figure-preservation-callout", 8.15, 5.77, 4.56, .87, "#FCF3EC")
    text("callout-heading", "SOURCE FIGURE PRESERVED", 8.36, 5.94, 4.13, .19,
         9.5, ORANGE, True)
    text("callout-body", "One independent, movable PNG.", 8.36, 6.21, 4.13, .25, 12)
    text("figure-caption", "Figure 1. Formula-generated curves; arbitrary units.",
         .62, 6.62, 7.10, .25, 10, MUTED)
    shape("footer-rule", .62, 6.99, 12.09, .012, RULE)
    text("evidence-boundary", "SYNTHETIC DEMO / Formula-generated values; no measured study.",
         .62, 7.12, 11.5, .18, 9, MUTED)
    text("page-number", "01", 12.1, 7.12, .61, .18, 9, MUTED, align="right")
    manifest = {
        "slide": {"width": 13.333, "height": 7.5, "background": "#FFFFFF"},
        "fit_text": False,
        "text_boxes": boxes,
        "shapes": shapes,
        "images": [{"id": "source-figure", "path": "source-figure.png",
                    "left": .62, "top": 2.10, "width": 7.10, "height": 4.4375,
                    "alt": "SYNTHETIC DEMO: formula-generated decay curves A and B; no observations."}],
        "notes": ("SYNTHETIC DEMO. y_A(x) = exp(-0.08x); y_B(x) = 0.7 exp(-0.04x). "
                  "No measured data, authors, institutions, publication, or DOI. "
                  "Known object positions define this controlled fixture. This is not a blind OCR "
                  "reconstruction or an automatic-reconstruction benchmark. Formulas are native "
                  "editable text runs, not Office Math objects. The source PNG is embedded unchanged."),
    }
    if draft:
        draft_text = {
            "synthetic-label": "UNVERIFIED DRAFT / SYNTHETIC DEMO",
            "fixture-label": "INTENTIONALLY INCORRECT / 01",
            "slide-subtitle": "Controlled illustration: wrong draft figure and unsupported formulas.",
            "sampling-description": "Draft values disagree with the source.\nVerify against synthetic-paper.pdf.",
            "callout-heading": "UNVERIFIED FIGURE / DO NOT USE",
            "callout-body": "Replace from source paper Figure 1.",
            "figure-caption": "Draft panel. Intentionally incorrect synthetic curves.",
            "evidence-boundary": "SYNTHETIC DEMO / Deliberate errors; not actual GPT output.",
        }
        wrong_formulas = {"equation-A": "(x) = 0.95 exp(-0.02x)",
                          "equation-B": "(x) = 0.4 exp(-0.10x)"}
        for item in boxes:
            if item["id"] in draft_text:
                item["text"] = draft_text[item["id"]]
            if item["id"] in wrong_formulas:
                item["runs"][-1]["text"] = wrong_formulas[item["id"]]
            if item["id"] == "synthetic-label":
                item["color"] = ORANGE
        manifest["images"][0].update({
            "id": "draft-figure", "path": "draft-figure.png",
            "alt": "INTENTIONALLY INCORRECT DEMO: unverified synthetic draft curves; replace from source Figure 1.",
        })
        manifest["notes"] = (
            "SYNTHETIC DEMO / UNVERIFIED DRAFT. The wrong curves and native formulas are deliberate: "
            "y_A(x) = 0.95 exp(-0.02x); y_B(x) = 0.4 exp(-0.10x). "
            "This is a controlled illustration, not actual GPT output; no model call occurred. "
            "Reference synthetic-paper.pdf, page 1, Figure 1 and Section 1 for the correct source. "
            "Replace this panel with source-figure.png and correct the editable formula text. "
            "No measured data, real authors, institutions, publication, or DOI are involved."
        )
    output = HERE / ("draft-demo.pptx" if draft else "editable-demo.pptx")
    builder.write_pptx(manifest, output, HERE / "generate.py")
    # Normalize package metadata and ZIP timestamps for repeatable public output.
    with zipfile.ZipFile(io.BytesIO(output.read_bytes())) as package:
        parts = {name: package.read(name) for name in package.namelist()}
    parts["docProps/core.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:title>SYNTHETIC DEMO - Two formula-generated decay curves</dc:title>'
        '<dc:creator>Synthetic demo</dc:creator>'
        '<dc:description>Controlled fixture; not scientific evidence.</dc:description>'
        '</cp:coreProperties>'
    ).encode("utf-8")
    if draft:
        parts["docProps/core.xml"] = parts["docProps/core.xml"].replace(
            b"Two formula-generated decay curves", b"UNVERIFIED DRAFT with intentional errors"
        ).replace(b"Controlled fixture; not scientific evidence.",
                  b"Controlled illustration; not actual GPT output or scientific evidence.")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name, content in sorted(parts.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, content)


def make_mapping():
    source_hash = hashlib.sha256((HERE / "source-figure.png").read_bytes()).hexdigest()
    common = {
        "demo_kind": "SYNTHETIC DEMO / controlled known-source illustration",
        "draft_deck_path": "draft-demo.pptx", "draft_slide": 1,
        "source_pdf_path": "synthetic-paper.pdf", "source_page": 1,
        "source_figure": "Figure 1", "source_figure_path": "source-figure.png",
        "source_figure_sha256": source_hash, "repaired_deck_path": "editable-demo.pptx",
        "repaired_slide": 1,
    }
    repairs = [
        {"draft_object": "left plot panel", "draft_asset_path": "draft-figure.png",
         "draft_value": "A=0.95exp(-0.02x); B=0.4exp(-0.10x); intentionally wrong curves",
         "evidence_kind": "figure + caption + axes + definitions",
         "source_evidence": "Page 1 Figure 1 caption: deterministic decay curves; solid teal A and dashed graphite B. "
                            "Axes: x (arbitrary units), 0 to 40; Synthetic signal (a.u.). "
                            "Section 1 defines A=exp(-0.08x), B=0.7exp(-0.04x).",
         "repair_action": "replace entire draft panel with unchanged original source PNG",
         "repaired_object": "left plot panel", "repaired_value": "source-figure.png; original source figure bytes"},
        {"draft_object": "equation-A", "draft_asset_path": "",
         "draft_value": "y_A(x) = 0.95 exp(-0.02x)", "evidence_kind": "source formula",
         "source_evidence": "Page 1 Section 1: y_A(x) = exp(-0.08 x).",
         "repair_action": "correct native formula text using source definition",
         "repaired_object": "equation-A", "repaired_value": "y_A(x) = exp(-0.08x)"},
        {"draft_object": "equation-B", "draft_asset_path": "",
         "draft_value": "y_B(x) = 0.4 exp(-0.10x)", "evidence_kind": "source formula",
         "source_evidence": "Page 1 Section 1: y_B(x) = 0.7 exp(-0.04 x).",
         "repair_action": "correct native formula text using source definition",
         "repaired_object": "equation-B", "repaired_value": "y_B(x) = 0.7 exp(-0.04x)"},
    ]
    rows = [{**common, **repair} for repair in repairs]
    with (HERE / "figure-mapping.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def check_fixture(rows):
    assert len(rows) == 41 and rows[0] == (0, 1.0, 0.7)
    assert all(a > 0 and b > 0 for _, a, b in rows)
    assert all(rows[i][1] > rows[i + 1][1] and rows[i][2] > rows[i + 1][2]
               for i in range(40))
    with (HERE / "data.csv").open(encoding="utf-8", newline="") as stream:
        stored = list(csv.DictReader(stream))
    assert len(stored) == len(rows)
    for item, (x, a, b) in zip(stored, rows):
        assert int(item["x"]) == x and item["data_kind"] == "SYNTHETIC DEMO"
        assert abs(float(item["y_A"]) - a) <= 5.1e-13
        assert abs(float(item["y_B"]) - b) <= 5.1e-13
    deck = Presentation(HERE / "editable-demo.pptx")
    assert len(deck.slides) == 1
    groups = [s for s in deck.slides[0].shapes if s.shape_type == 6]
    assert len(groups) == 1 and groups[0].name == "slide-header"
    assert {s.name for s in groups[0].shapes} == {
        "synthetic-label", "fixture-label", "slide-title", "slide-subtitle", "header-rule",
    }

    def leaves(shapes):
        for shape in shapes:
            if shape.shape_type == 6:
                yield from leaves(shape.shapes)
            else:
                yield shape

    objects = list(leaves(deck.slides[0].shapes))
    assert {s.name for s in objects} >= {
        "slide-title", "equation-A", "equation-B", "sampling-description",
        "flow-step-1", "flow-step-2", "flow-step-3", "figure-preservation-callout",
    }
    assert sum(s.shape_type == 13 for s in objects) == 1
    with zipfile.ZipFile(HERE / "editable-demo.pptx") as package:
        media = [name for name in package.namelist() if name.startswith("ppt/media/")]
        assert len(media) == 1
        assert package.read(media[0]) == (HERE / "source-figure.png").read_bytes()
        assert b"SYNTHETIC DEMO" in package.read("ppt/slides/slide1.xml")
        assert b"srcRect" not in package.read("ppt/slides/slide1.xml")
    correct_text = {shape.name: shape.text for shape in objects if shape.has_text_frame}
    assert correct_text["equation-A"] == "yA(x) = exp(-0.08x)"
    assert correct_text["equation-B"] == "yB(x) = 0.7 exp(-0.04x)"
    draft = Presentation(HERE / "draft-demo.pptx")
    assert len(draft.slides) == 1
    draft_groups = [s for s in draft.slides[0].shapes if s.shape_type == 6]
    assert len(draft_groups) == 1 and draft_groups[0].name == "slide-header"
    assert {s.name for s in draft_groups[0].shapes} == {s.name for s in groups[0].shapes}
    draft_objects = list(leaves(draft.slides[0].shapes))
    assert sum(s.shape_type == 13 for s in draft_objects) == 1
    draft_text = {shape.name: shape.text for shape in draft_objects if shape.has_text_frame}
    assert draft_text["equation-A"] == "yA(x) = 0.95 exp(-0.02x)"
    assert draft_text["equation-B"] == "yB(x) = 0.4 exp(-0.10x)"
    assert "UNVERIFIED DRAFT" in draft_text["synthetic-label"]
    assert "not actual GPT output" in draft_text["evidence-boundary"]
    with zipfile.ZipFile(HERE / "draft-demo.pptx") as package:
        media = [name for name in package.namelist() if name.startswith("ppt/media/")]
        assert len(media) == 1
        assert package.read(media[0]) == (HERE / "draft-figure.png").read_bytes()
        assert b"srcRect" not in package.read("ppt/slides/slide1.xml")
    assert (HERE / "draft-figure.png").read_bytes() != (HERE / "source-figure.png").read_bytes()
    with (HERE / "figure-mapping.csv").open(encoding="utf-8", newline="") as stream:
        mapping = list(csv.DictReader(stream))
    assert {item["draft_object"] for item in mapping} == {"left plot panel", "equation-A", "equation-B"}
    source_hash = hashlib.sha256((HERE / "source-figure.png").read_bytes()).hexdigest()
    with pymupdf.open(HERE / "synthetic-paper.pdf") as paper:
        assert len(paper) == 1
        page = paper[0]
        source_text = "".join(page.get_text().split())
        assert "Figure1." in source_text
        assert "y_A(x)=exp(-0.08x)" in source_text
        assert "y_B(x)=0.7exp(-0.04x)" in source_text
        source_images = page.get_images()
        assert len(source_images) == 1
        original = Image.open(HERE / "source-figure.png").convert("RGB")
        pdf_image = Image.open(io.BytesIO(paper.extract_image(source_images[0][0])["image"])).convert("RGB")
        assert pdf_image.size == original.size and pdf_image.tobytes() == original.tobytes()
    for item in mapping:
        assert item["source_figure_sha256"] == source_hash
        assert item["source_page"] == "1" and item["source_figure"] == "Figure 1"
        for key, value in item.items():
            if key.endswith("_path") and value:
                assert not Path(value).is_absolute() and ".." not in Path(value).parts
                assert (HERE / value).is_file()
    print("PASS: labeled wrong draft, source-supported repair, original PNG bytes, relative mapping audit.")


if __name__ == "__main__":
    sample_rows = make_data()
    make_figure()
    make_paper()
    make_slide()
    make_figure(draft=True)
    make_slide(draft=True)
    make_mapping()
    check_fixture(sample_rows)
