"""Look and feel: neutral dark base, muted blue accent, warm-to-cool match scale."""

from typing import List, Tuple

BG = "#09090B"
SURFACE = "#161618"
SURFACE_2 = "#1F1F22"
BORDER = "#2A2A2E"
TEXT = "#F5F5F7"
TEXT_DIM = "#8E8E93"
ACCENT = "#7C9CC4"  # soft steel blue, deliberately not a system blue

# Match strength: strong matches run warm (coral -> amber -> gold), weak ones cool.
_STOPS: List[Tuple[float, Tuple[int, int, int]]] = [
    (35, (0x4F, 0x78, 0xB0)),   # cool blue
    (60, (0x84, 0xA3, 0xBE)),   # pale steel
    (75, (0xE0, 0xB2, 0x5E)),   # gold
    (90, (0xEE, 0x8A, 0x47)),   # amber
    (100, (0xEC, 0x5B, 0x45)),  # coral red
]


def score_color(score: float) -> str:
    """Hex color for a 0-100 match score."""
    score = max(_STOPS[0][0], min(_STOPS[-1][0], score))
    for (lo, c1), (hi, c2) in zip(_STOPS, _STOPS[1:]):
        if lo <= score <= hi:
            f = (score - lo) / (hi - lo)
            r, g, b = (round(a + (b_ - a) * f) for a, b_ in zip(c1, c2))
            return f"#{r:02X}{g:02X}{b:02X}"
    return "#%02X%02X%02X" % _STOPS[-1][1]



_CSS = """
<style>
:root { --bg:@BG; --glass:rgba(255,255,255,.05); --glass2:rgba(255,255,255,.08);
        --line:rgba(255,255,255,.10); --text:@TEXT; --dim:@DIM; --accent:@ACCENT; }
html, body, [class*="stApp"] {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Inter, sans-serif;
  color-scheme: dark; }
.stApp { background:
  radial-gradient(900px 520px at 8% -8%, rgba(238,138,71,.13), transparent 62%),
  radial-gradient(900px 560px at 100% 4%, rgba(124,156,196,.15), transparent 60%),
  radial-gradient(800px 500px at 50% 110%, rgba(236,91,69,.07), transparent 60%),
  var(--bg); background-attachment: fixed; }
[data-testid="stToolbar"], [data-testid="stDecoration"], footer { display:none !important; }
header[data-testid="stHeader"] { display: none !important; }  /* it would sit on top of our bar and eat clicks */
.block-container { max-width: 1180px; padding-top: 5.6rem; padding-bottom: 6.5rem; }
h1, h2, h3 { letter-spacing: -0.025em; font-weight: 700; }
h1 { font-size: 2.3rem !important; }

/* top bar: a floating glass pill */
.vm-brand { font-size: 1.15rem; font-weight: 750; letter-spacing: -0.02em; color: var(--text); padding-left:.4rem; }
.st-key-topbar { position: fixed; top: 14px; left: 50%; transform: translateX(-50%);
  width: min(1180px, calc(100vw - 2rem)); z-index: 1000; padding: .45rem 1rem;
  background: rgba(24,24,28,.62); backdrop-filter: blur(28px) saturate(160%);
  -webkit-backdrop-filter: blur(28px) saturate(160%);
  border: 1px solid var(--line); border-radius: 999px;
  box-shadow: 0 18px 50px -24px rgba(0,0,0,.9); }
[data-testid="stSegmentedControl"] { justify-content: flex-end; }
[data-testid="stSegmentedControl"] button { border-radius: 999px !important; }

/* agent question on home */
.vm-ask { background: var(--glass); border:1px solid var(--line); border-radius: 22px;
          padding: 1rem 1.3rem; margin: .2rem 0 .8rem; font-size: 1.05rem;
          backdrop-filter: blur(20px); }
.vm-ask span { display:block; color: var(--dim); font-size:.8rem; margin-top:.3rem; }

/* chips */
.vm-chips { display:flex; flex-wrap:wrap; gap:.45rem; }
.vm-chip { background: var(--glass2); border:1px solid var(--line); color: var(--text);
           padding: .28rem .8rem; border-radius: 999px; font-size: .8rem;
           backdrop-filter: blur(14px); }
.vm-chip b { color: var(--dim); font-weight: 500; margin-right:.35rem; }

/* glass cards */
[class*="st-key-card_"], .st-key-stats {
    background: var(--glass); border:1px solid var(--line); border-radius: 30px;
    padding: 14px 14px 10px; backdrop-filter: blur(24px) saturate(140%);
    -webkit-backdrop-filter: blur(24px) saturate(140%);
    box-shadow: 0 24px 60px -34px rgba(0,0,0,.9);
    transition: border-color .25s, transform .25s, background .25s, opacity .4s, filter .4s; }
[class*="st-key-card_"]:hover { border-color: rgba(255,255,255,.2); background: var(--glass2);
    transform: translateY(-3px); }
.vm-art { position:relative; aspect-ratio:1/1; border-radius:22px; overflow:hidden;
          background: linear-gradient(135deg,#26262b,#18181b);
          box-shadow: 0 16px 38px -16px var(--c, #000); }
.vm-art img { width:100%; height:100%; object-fit:cover; display:block; }
.vm-art .vm-note { position:absolute; inset:0; display:flex; align-items:center;
                   justify-content:center; font-size:3rem; opacity:.25; }
.vm-badge { position:absolute; top:12px; left:12px; color:#111; font-weight:700;
            font-size:.72rem; padding:.22rem .65rem; border-radius:999px;
            backdrop-filter: blur(8px); }
.vm-title { font-weight:650; font-size:1.02rem; margin-top:.8rem; line-height:1.25;
            white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.vm-artist { color: var(--dim); font-size:.86rem; white-space:nowrap; overflow:hidden;
             text-overflow:ellipsis; margin-bottom:.5rem; }
.vm-tags { display:flex; gap:.35rem; margin-bottom:.45rem; }
.vm-tags span { font-size:.68rem; color: var(--dim); border:1px solid var(--line);
                padding:.1rem .6rem; border-radius:999px; }
.vm-link a { color: var(--dim) !important; font-size:.72rem; text-decoration:none; }
.vm-link a:hover { color: var(--accent) !important; }
[class*="st-key-card_"] audio { width:100%; height:34px; margin:.25rem 0 .45rem; }

/* hero banner: the cover, blurred, as its own backdrop */
.st-key-hero { position:relative; overflow:hidden; border-radius: 38px; padding: 30px 34px;
  border:1px solid var(--line); background: #131316; isolation:isolate;
  box-shadow: 0 30px 80px -40px rgba(0,0,0,.95); margin-bottom: .6rem; }
.st-key-hero::before { content:""; position:absolute; inset:-40px; z-index:-2;
  background: var(--hero-img, linear-gradient(135deg,#2a2a30,#17171a)) center/cover;
  filter: blur(46px) saturate(1.5) brightness(.62); transform: scale(1.15); }
.st-key-hero::after { content:""; position:absolute; inset:0; z-index:-1;
  background: linear-gradient(100deg, rgba(8,8,10,.55) 0%, rgba(8,8,10,.15) 70%); }
.vm-eyebrow { font-size:.74rem; letter-spacing:.14em; text-transform:uppercase; color: rgba(255,255,255,.7); }
.vm-hero-title { font-size:2.5rem; font-weight:760; letter-spacing:-0.03em; line-height:1.08; margin:.25rem 0 .1rem; }
.vm-hero-artist { color: rgba(255,255,255,.72); font-size:1.05rem; margin-bottom:.8rem; }
.vm-hero-art { aspect-ratio:1/1; border-radius:28px; overflow:hidden;
  box-shadow: 0 30px 70px -20px rgba(0,0,0,.85); }
.vm-hero-art img { width:100%; height:100%; object-fit:cover; display:block; }
.st-key-hero audio { width:100%; height:36px; }

/* playlist tiles: filled with album art */
[class*="st-key-tile_"] { position:relative; overflow:hidden; isolation:isolate;
  border-radius: 30px; padding: 20px 20px 16px; min-height: 210px; border:1px solid var(--line);
  display:flex; flex-direction:column; justify-content:flex-end; background:#18181b;
  box-shadow: 0 24px 60px -36px rgba(0,0,0,.95); transition: transform .25s, border-color .25s; }
[class*="st-key-tile_"]:hover { transform: translateY(-3px); border-color: rgba(255,255,255,.22); }
[class*="st-key-tile_"]::before { content:""; position:absolute; inset:0; z-index:-2;
  background: var(--cover, linear-gradient(135deg,#2a2a30,#17171a)) center/cover;
  filter: saturate(1.2) brightness(.62); transition: transform .5s; }
[class*="st-key-tile_"]:hover::before { transform: scale(1.06); }
[class*="st-key-tile_"]::after { content:""; position:absolute; inset:0; z-index:-1;
  background: linear-gradient(180deg, rgba(0,0,0,0) 20%, rgba(0,0,0,.72) 100%); }
.vm-tile-name { font-size:1.25rem; font-weight:720; letter-spacing:-0.02em; }
.vm-tile-tag { color: rgba(255,255,255,.72); font-size:.86rem; margin:.15rem 0 .7rem; }

/* stats */
.st-key-stats { padding: 22px 26px; margin-bottom: .4rem; }
.vm-stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 1.6rem; align-items:start; }
.vm-stat-h { font-size:.72rem; letter-spacing:.13em; text-transform:uppercase; color: var(--dim); margin-bottom:.8rem; }
.vm-ring { --p:50; --c:#EE8A47; width:132px; height:132px; border-radius:50%;
  background: conic-gradient(var(--c) calc(var(--p) * 1%), rgba(255,255,255,.09) 0);
  display:flex; align-items:center; justify-content:center; margin: 0 auto .6rem; }
.vm-ring div { width:100px; height:100px; border-radius:50%; background:#141417;
  display:flex; flex-direction:column; align-items:center; justify-content:center; }
.vm-ring b { font-size:1.7rem; letter-spacing:-0.03em; }
.vm-ring span { font-size:.68rem; color: var(--dim); }
.vm-nums { display:flex; justify-content:center; gap:1.4rem; text-align:center; margin-top:.5rem; }
.vm-nums b { display:block; font-size:1.3rem; letter-spacing:-0.02em; }
.vm-nums span { font-size:.68rem; color: var(--dim); }
.vm-bar { margin-bottom:.7rem; }
.vm-bar-top { display:flex; justify-content:space-between; font-size:.86rem; margin-bottom:.28rem; }
.vm-bar-top span { color: var(--dim); }
.vm-bar-track { height:9px; border-radius:999px; background: rgba(255,255,255,.08); overflow:hidden; }
.vm-bar-fill { height:100%; border-radius:999px; }
.vm-empty { color: var(--dim); font-size:.95rem; padding:.6rem 0; }

/* no screen fade while Streamlit reruns: it makes every click feel heavy */
[data-stale="true"], [data-stale="true"] * { opacity: 1 !important; transition: none !important; }

/* thumbs: color change + one hop. Disliked cards grey out. */
@keyframes vm-hop { 0%{transform:translateY(0)} 30%{transform:translateY(-9px) scale(1.25)}
  55%{transform:translateY(0) scale(.94)} 75%{transform:translateY(-3px)} 100%{transform:translateY(0) scale(1)} }
@keyframes vm-drop { 0%{transform:translateY(0)} 30%{transform:translateY(8px) scale(1.2)}
  60%{transform:translateY(0) scale(.94)} 100%{transform:translateY(0) scale(1)} }
[class*="st-key-up_"] button[kind="primary"] [data-testid="stIconMaterial"] {
  display:inline-block; animation: vm-hop .6s ease-out; }
[class*="st-key-down_"] button[kind="primary"] [data-testid="stIconMaterial"] {
  display:inline-block; animation: vm-drop .6s ease-out; }
[class*="st-key-down_"] button[kind="primary"] { background:#55555c !important; color:#fff !important; }
[class*="st-key-card_"]:has(.vm-dim), .st-key-hero:has(.vm-dim) {
  opacity:.4; filter: grayscale(1); }

/* buttons: soft pills */
.stButton > button, [data-testid="stPopover"] > div > button {
  background: var(--glass2); color: var(--text); border:1px solid var(--line);
  border-radius: 999px; font-weight:500; transition: all .18s; backdrop-filter: blur(14px); }
.stButton > button:hover, [data-testid="stPopover"] > div > button:hover {
  border-color: rgba(255,255,255,.35); color:#fff; background: rgba(255,255,255,.13); }
.stButton > button:active { transform: scale(.96); }
.stButton > button[kind="primary"] { background: var(--accent); color:#0b0b0d; border-color: transparent; }
.stButton > button[kind="primary"]:hover { background:#93b0d4; color:#0b0b0d; }

/* chat */
[data-testid="stChatMessage"] { background: transparent; padding:.4rem 0; }
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] {
  background: var(--glass2) !important; color: var(--dim) !important; border:1px solid var(--line); }
[data-testid="stChatInput"] { border-radius: 999px; background: rgba(24,24,28,.7);
  backdrop-filter: blur(24px); border:1px solid var(--line); }
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] > div > div {
  border-radius: 999px; background: transparent; border-color: transparent; box-shadow:none; }
[data-testid="stChatInput"] textarea { padding-left: 1.1rem; }
</style>
"""

CSS = _CSS.replace("@BG", BG).replace("@TEXT", TEXT).replace("@DIM", TEXT_DIM).replace("@ACCENT", ACCENT)
