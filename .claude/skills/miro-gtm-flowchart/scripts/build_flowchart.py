#!/usr/bin/env python3
"""Turn a GTM system spec (JSON) into a Miro Canvas Composer SVG, plus an optional PNG preview.

Usage:
  python3 build_flowchart.py spec.json -o flowchart.svg [--preview preview.png] [--x 0 --y 0]

The SVG goes to the Miro MCP tool canvas_create_from_svg. The preview is a rough local render
(boxes, diamonds, chips, straight-line edges) for catching overlaps before anything touches the board.
See ../SKILL.md for the spec format.
"""
import argparse, json, math, re, sys

# ---------- style (Miro "Bright Paper" palette) ----------
KIND = {  # fill, stroke, text colour, shape, default w, default h, font size
    'start':    ('#6631d7', '#6631d7', '#ffffff', 'round_rectangle', 260, 140, 21),
    'step':     ('#dedaff', '#8f7fee', '#1a1a1a', 'rectangle',       260, 140, 21),
    'decision': ('#fff6b6', '#ffdc4a', '#1a1a1a', 'rhombus',         230, 180, 22),
    'branch':   ('#c6dcff', '#659df2', '#1a1a1a', 'rectangle',       260, 100, 21),
    'exit':     ('#ffffff', '#b0b0b0', '#595959', 'rectangle',       220, 70,  19),
}
LEGEND = [('start', 'Start or review'), ('step', 'Step'), ('decision', 'Decision'), ('branch', 'Branch or outcome'), ('exit', 'Exit or fallback')]
INK, BODY, LANE, LINE, LOOP = '#1a1a1a', '#595959', '#f7f7f7', '#313131', '#6631d7'
TOOLS = {  # key: (display name, public logo url). Swap the urls for your own if these ever stop loading.
    'claude':      ('Claude', 'https://lh3.googleusercontent.com/d/1H3p2Jb7qCm_Lekja6MD70TNcEkOn43Hz'),
    'claude_code': ('Claude Code', 'https://lh3.googleusercontent.com/d/1H3p2Jb7qCm_Lekja6MD70TNcEkOn43Hz'),
    'github':      ('GitHub', 'https://lh3.googleusercontent.com/d/18gZYM4j-KI8qsNUrHk1z9QZxUvHNRvnu'),
    'clay':        ('Clay', 'https://lh3.googleusercontent.com/d/17p9VTOfRU57ZcgMJoK6waiXiwp8fFMIM'),
    'hubspot':     ('HubSpot', 'https://lh3.googleusercontent.com/d/1SEB69b4BJiKnQqRjOFNUidiDFcDeCwrE'),
    'n8n':         ('n8n', 'https://lh3.googleusercontent.com/d/15VWDwfJhdHviy-VnCqZkZO4DEFflmHEk'),
    'plusvibe':    ('PlusVibe', 'https://lh3.googleusercontent.com/d/1Iij8_D6KxJSdNYrCVqbrbIaqB3fF-KTO'),
}
COL_GAP, STACK_GAP, ROW_GAP, HEADER, PAD, X0 = 90, 30, 40, 100, 50, 100
CHIP_FS, CHIP_CHAR = 16, 10.2          # Noto Sans bold 16: about 10 px a character (measured on Miro)

def esc(s): return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def label_of(nid, nd):
    pre = nid + ' ' if re.fullmatch(r'\d+[A-Z]', nid) else ''
    return pre + nd['title']

def sub_lines(nd):
    s = nd.get('sub', '')
    if isinstance(s, list): return ['• ' + x for x in s]
    return [s] if s else []

def est_lines(text, width, fs, decision=False):
    usable = (width * 0.62 - 20) if decision else (width - 30)
    cpl = max(int(usable / (fs * 0.56)), 4)
    return sum(max(1, math.ceil(len(t) / cpl)) for t in text)

def size(nid, nd):
    fill, stroke, tc, shape, w, h, fs = KIND[nd['kind']]
    w = nd.get('w', w)
    if nd['kind'] == 'decision':
        n = est_lines([label_of(nid, nd)], w, fs, True)
        if n > 2: print(f'warning: decision "{nid}" needs {n} lines; shorten it (3 words or fewer) or the text will overflow the diamond', file=sys.stderr)
        return w, nd.get('h', max(h, 90 + n * fs * 1.5))
    n = est_lines([label_of(nid, nd)] + sub_lines(nd), w, fs)
    return w, nd.get('h', max(h, int(n * fs * 1.5 + 44)))

def build(spec, ox=0, oy=0):
    nodes, rows = spec['nodes'], spec['rows']
    for nid, nd in nodes.items():
        if nd.get('kind') not in KIND: sys.exit(f'node {nid}: kind must be one of {list(KIND)}')
    below = {nd['below']: nid for nid, nd in nodes.items() if nd.get('below')}
    box = {}  # nid -> [x, y, w, h]
    for nid, nd in nodes.items(): box[nid] = [0, 0, *size(nid, nd)]
    # column widths and row widths
    layout = []
    for r in rows:
        cols = [c if isinstance(c, list) else [c] for c in r['columns']]
        widths = [max(max(box[n][2] for n in c), max((box[below[n]][2] for n in c if n in below), default=0)) for c in cols]
        layout.append((r, cols, widths, sum(widths) + COL_GAP * (len(cols) - 1)))
    right = X0 + max(L[3] for L in layout)
    prev_end = X0   # x where the previous row finished, so a right-to-left row starts directly under it
    y = oy + 200; lanes = []
    for ri, (r, cols, widths, total) in enumerate(layout):
        rtl = r.get('direction', 'ltr' if ri % 2 == 0 else 'rtl') == 'rtl'
        tops, bots = [], []
        for c in cols:
            hs = [box[n][3] for n in c]; H = sum(hs) + STACK_GAP * (len(c) - 1)
            extra = max((50 + box[below[n]][3] for n in c if n in below), default=0)
            tops.append(H / 2); bots.append(H / 2 + extra)
        mt, mb = max(tops), max(bots)
        cy = y + HEADER + mt
        x = X0 if not rtl else max(prev_end, X0 + total)
        for c, w in zip(cols, widths):
            if rtl: x -= w
            hs = [box[n][3] for n in c]; H = sum(hs) + STACK_GAP * (len(c) - 1); yy = cy - H / 2
            if len(c) == 1 and nodes[c[0]].get('align') == 'bottom': yy = cy + mb - H   # e.g. the loop's source, so the loop runs under everything
            for n in c:
                b = box[n]; b[0] = x + (w - b[2]) / 2; b[1] = yy; yy += b[3] + STACK_GAP
                if n in below:
                    e = box[below[n]]; e[0] = x + (w - e[2]) / 2; e[1] = b[1] + b[3] + 50
            x = x + w + COL_GAP if not rtl else x - COL_GAP
        prev_end = x - COL_GAP if not rtl else x + COL_GAP
        lane_h = HEADER + mt + mb + PAD + (90 if ri == len(layout) - 1 and spec.get('loop') else 0)
        lanes.append((y, lane_h, r['title'], ri)); y += lane_h + ROW_GAP
    for b in box.values(): b[0] += ox
    right += ox
    row_of = {n: ri for ri, (r, cols, _, _) in enumerate(layout) for c in cols for n in c}
    for n, nd in nodes.items():
        if nd.get('below'): row_of[n] = row_of[nd['below']]
    return box, lanes, right, row_of, layout

def edge_sides(a, b, box, row_of, layout):
    A, B = box[a], box[b]
    if row_of[a] == row_of[b]:
        if B[1] >= A[1] + A[3] - 1 and B[0] < A[0] + A[2] and B[0] + B[2] > A[0]: return 'bottom', 'top'
        return ('right', 'left') if B[0] > A[0] else ('left', 'right')
    # crossing into a later row: the top node of a column under the source drops straight down,
    # the others in that stack are reached round the outside edge of the row
    stack = next((c for c in layout[row_of[b]][1] if b in c), [b])
    overlap = B[0] < A[0] + A[2] and B[0] + B[2] > A[0]
    if overlap and stack[0] == b: return 'bottom', 'top'
    if overlap:
        row_nodes = [n for c in layout[row_of[b]][1] for n in c]
        outer = 'right' if B[0] + B[2] >= max(box[n][0] + box[n][2] for n in row_nodes) - 1 else 'left'
        return outer, outer
    # no overlap: run sideways inside the source row, then drop into the target's top (keeps clear of the centred headers)
    return ('left' if B[0] + B[2] / 2 < A[0] else 'right'), 'top'

def chip(nd, b):
    keys = nd.get('tools', [])
    if not keys: return [], None
    names = [TOOLS[k][0] if k in TOOLS else k for k in keys]
    text = nd.get('tool_label', ' + '.join(names))
    logos = [TOOLS[k][1] for k in keys if k in TOOLS]
    n = len(logos); tw = round(len(text) * CHIP_CHAR)
    lw = n * 22 + max(n - 1, 0) * 4 + (8 if n else 0)
    w = tw + lw + 28; x = b[0] + b[2] - w - 6; y = b[1] - 18; cy = y + 18
    out = [f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="36" rx="62" fill="#ffffff" stroke="{INK}" stroke-width="2" />']
    for j, u in enumerate(logos): out.append(f'<image href="{u}" x="{x + 14 + j * 26:.0f}" y="{cy - 11:.0f}" width="22" height="22" />')
    out.append(f'<text x="{x + 14 + lw:.0f}" y="{cy + 5:.0f}" data-width="{tw + 40}" font-family="noto_sans" font-size="{CHIP_FS}" font-weight="bold" fill="{INK}">{esc(text)}</text>')
    return ['<g data-group="">'] + out + ['</g>'], (x, y, w, 36)

def svg(spec, ox=0, oy=0):
    box, lanes, right, row_of, layout = build(spec, ox, oy)
    nodes = spec['nodes']; out, chips, edges = [], [], []
    out.append(f'<text x="{ox}" y="{oy + 80}" font-family="noto_sans" font-size="67" font-weight="bold" fill="{INK}">{esc(spec["title"])}</text>')
    if spec.get('subtitle'):
        out.append(f'<textArea x="{ox}" y="{oy + 110}" width="{right - ox}" font-family="noto_sans" font-size="24" fill="{BODY}">{esc(spec["subtitle"])}</textArea>')
    for ly, lh, title, ri in lanes:
        out.append(f'<rect x="{ox + 40}" y="{ly}" width="{right - ox}" height="{lh}" rx="12" fill="{LANE}" stroke="none" />')
        # centred header: row-to-row links run down the lane ends and the loop runs down the far left, so the middle stays clear
        out.append(f'<text x="{(ox + 40 + right + 40) / 2:.0f}" y="{ly + 58}" text-anchor="middle" font-family="noto_sans" font-size="33" font-weight="bold" fill="{INK}">{ri + 1}  {esc(title)}</text>')
    for nid, nd in nodes.items():
        fill, stroke, tc, shape, _, _, fs = KIND[nd['kind']]
        x, y, w, h = box[nid]
        body = '<b>' + label_of(nid, nd) + '</b>' + ''.join('<br>' + s for s in sub_lines(nd))
        align = ' data-text-align="left"' if isinstance(nd.get('sub'), list) else ''
        rx = ' rx="12"' if shape == 'rectangle' else ''
        out.append(f'<rect id="{nid}" x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h:.0f}"{rx} data-shape="{shape}" fill="{fill}" stroke="{stroke}" '
                   f'stroke-width="2" data-text-color="{tc}" data-font-family="noto_sans" data-font-size="{fs}"{align} data-content="{esc(body)}" />')
        c, _ = chip(nd, box[nid]); chips += c
    for e in spec.get('edges', []):
        a, b = e[0], e[1]; lab = e[2] if len(e) > 2 else ''
        ss, es = edge_sides(a, b, box, row_of, layout)
        if ss == es and lab:
            print(f'note: dropped label "{lab}" on {a}->{b}; it would sit on an overlapping line. Say it inside {b} instead.', file=sys.stderr); lab = ''
        edges.append(f'<line x1="0" y1="0" x2="1" y2="1" stroke="{LINE}" stroke-width="2" data-arrow="end" data-shape="elbowed" data-start="{a}" data-end="{b}" '
                     f'data-start-side="{ss}" data-end-side="{es}"' + (f' data-content="{esc(lab)}"' if lab else '') + ' />')
    lp = spec.get('loop')
    if lp:
        a, b = lp['from'], lp['to']; A = box[a]
        edges.append(f'<line x1="0" y1="0" x2="1" y2="1" stroke="{LOOP}" stroke-width="4" data-arrow="end" data-shape="elbowed" data-start="{a}" data-end="{b}" data-start-side="bottom" data-end-side="left" />')
        if lp.get('label'):
            lw = round(len(lp['label']) * 9.6) + 40; ly = A[1] + A[3] + 27
            out.append(f'<rect x="{X0 + ox + 120:.0f}" y="{ly - 18:.0f}" width="{lw}" height="36" rx="62" fill="{LOOP}" stroke="{LOOP}" stroke-width="2" data-text-color="#ffffff" '
                       f'data-font-family="noto_sans" data-font-size="17" data-font-weight="bold" data-content="{esc(lp["label"])}" />')
    if spec.get('legend', True):
        lx, ly = right + 140, lanes[0][0]
        out.append(f'<text x="{lx}" y="{ly + 30}" font-family="noto_sans" font-size="24" font-weight="bold" fill="{INK}">Key</text>')
        for i, (k, t) in enumerate(LEGEND):
            fill, stroke, _, shape, *_ = KIND[k]; yy = ly + 50 + i * 52
            out.append(f'<rect x="{lx}" y="{yy}" width="60" height="36" data-shape="{shape}" fill="{fill}" stroke="{stroke}" stroke-width="2" />')
            out.append(f'<text x="{lx + 80}" y="{yy + 26}" font-family="noto_sans" font-size="20" fill="{BODY}">{t}</text>')
    doc = '<svg xmlns="http://www.w3.org/2000/svg">\n' + '\n'.join(out + chips + edges) + '\n</svg>'
    return doc, box, lanes, right

def check(spec, box):
    """Warn about overlapping boxes (nodes and chips) before anything is sent to Miro."""
    items = [(n, b) for n, b in box.items()]
    for n, nd in spec['nodes'].items():
        _, cb = chip(nd, box[n])
        if cb: items.append((n + ' chip', cb))
    bad = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (a, A), (b, B) = items[i], items[j]
            if a.split()[0] == b.split()[0]: continue
            if A[0] < B[0] + B[2] and B[0] < A[0] + A[2] and A[1] < B[1] + B[3] and B[1] < A[1] + A[3]:
                print(f'overlap: {a} and {b}', file=sys.stderr); bad += 1
    ids = set(spec['nodes'])
    for e in spec.get('edges', []):
        for n in e[:2]:
            if n not in ids: print(f'edge refers to unknown node {n}', file=sys.stderr); bad += 1
    return bad

def preview(spec, box, lanes, right, path):
    from PIL import Image, ImageDraw
    s = 0.4; W, H = int((right + 600) * s), int((lanes[-1][0] + lanes[-1][1] + 60) * s)
    im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
    for ly, lh, t, ri in lanes:
        d.rounded_rectangle([40 * s, ly * s, right * s + 40 * s, (ly + lh) * s], 6, fill=LANE)
        d.text((((40 + right + 40) / 2) * s - 60, (ly + 30) * s), f'{ri + 1} {t}', fill=INK)
    for e in spec.get('edges', []):
        A, B = box[e[0]], box[e[1]]
        d.line([(A[0] + A[2] / 2) * s, (A[1] + A[3] / 2) * s, (B[0] + B[2] / 2) * s, (B[1] + B[3] / 2) * s], fill='#b0b0b0', width=1)
    for n, nd in spec['nodes'].items():
        x, y, w, h = [v * s for v in box[n]]; fill, stroke, tc, shape, *_ = KIND[nd['kind']]
        if shape == 'rhombus': d.polygon([(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)], fill=fill, outline=stroke)
        else: d.rounded_rectangle([x, y, x + w, y + h], 5, fill=fill, outline=stroke)
        d.text((x + 6, y + 6), label_of(n, nd)[:22], fill=tc)
        _, cb = chip(nd, box[n])
        if cb: cx, cy, cw, ch = [v * s for v in cb]; d.rounded_rectangle([cx, cy, cx + cw, cy + ch], 6, fill='white', outline=INK)
    im.save(path)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('spec'); ap.add_argument('-o', '--out', default='flowchart.svg')
    ap.add_argument('--preview'); ap.add_argument('--x', type=int, default=0); ap.add_argument('--y', type=int, default=0)
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    doc, box, lanes, right = svg(spec, a.x, a.y)
    open(a.out, 'w').write(doc)
    bad = check(spec, box)
    if a.preview: preview(spec, box, lanes, right, a.preview)
    print(f'wrote {a.out}: {len(spec["nodes"])} nodes, {len(spec.get("edges", []))} edges, {len(doc)} chars' + (f', {bad} problems' if bad else ', no overlaps'))
