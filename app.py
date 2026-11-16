"""VibeMatch: Streamlit UI.   Run:  streamlit run app.py"""

import datetime
import html
import random
import re
import uuid

import streamlit as st

from src import chat_store, llm
from src.agent import MusicAgent
from src.branding import APP_NAME
from src.explain import explain_recommendations
from src.playlists import PLAYLISTS, diverse_top
from src.preview import lookup_many
from src.recommender import load_songs
from src.stats import compute_stats
from src.ui_theme import CSS, score_color

st.set_page_config(page_title=APP_NAME, page_icon="🎧", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def get_songs():
    return load_songs("data/catalog.csv")


@st.cache_data(show_spinner=False)
def playlist_picks(playlist_id: str):
    pl = next(p for p in PLAYLISTS if p["id"] == playlist_id)
    picks, _ = diverse_top(pl["profile"], get_songs(), k=8)
    return picks


# ------------------------------------------------------------------ state
GREETING = "Hi! I'll ask a few quick questions to find your music."


def fresh_chat():
    """Reset to a brand-new conversation (the old one is saved first)."""
    agent = MusicAgent()
    st.session_state.update(
        agent=agent, chat_id=uuid.uuid4().hex[:8], stage="onboarding", recs=None,
        needs_refresh=False, recs_stale=False, mode="home", open_playlist=None, dirty=False,
        messages=[{"role": "assistant", "content": GREETING},
                  {"role": "assistant", "content": agent.next_question()}])


def init_state():
    if "agent" not in st.session_state:
        fresh_chat()
    s = st.session_state
    # A chat left waiting on optional questions (older behavior) is already good to go.
    if (s.stage == "onboarding" and s.agent.ready()
            and any(m["role"] == "user" for m in s.messages)):
        s.stage = "chatting"
        s.needs_refresh = True


def has_activity() -> bool:
    s = st.session_state
    return any(m["role"] == "user" for m in s.messages) or bool(s.agent.liked)


def save_current():
    """Persist the current chat, but only once there is something worth keeping."""
    s = st.session_state
    if has_activity():
        chat_store.save_chat(s.chat_id, s.messages, s.stage, s.agent.export_state())
    s.dirty = False


def new_chat():
    save_current()
    fresh_chat()


def open_chat(chat: dict):
    save_current()
    s = st.session_state
    s.update(agent=MusicAgent.from_state(chat["agent"]), chat_id=chat["id"],
             stage=chat["stage"], messages=chat["messages"], recs=None,
             needs_refresh=chat["stage"] == "chatting", recs_stale=False, mode="rec",
             open_playlist=None, dirty=False)
    init_state()  # promotes a chat that was stuck on optional questions


def say(role: str, content: str):
    st.session_state.messages.append({"role": role, "content": content})
    st.session_state.dirty = True


def profile_text(profile: dict) -> str:
    bits = [profile["mood"]]
    if profile["genre"] != "any":
        bits.append(profile["genre"])
    bits.append(f"energy {profile['energy']:.2f}")
    bits.append("acoustic" if profile["likes_acoustic"] else "produced sound")
    if profile.get("min_popularity"):
        bits.append("familiar picks")
    if profile.get("max_popularity"):
        bits.append("hidden gems")
    return " · ".join(bits)


def profile_chips(profile: dict) -> str:
    chips = [("mood", profile["mood"]),
             ("genre", profile["genre"] if profile["genre"] != "any" else "open"),
             ("energy", f"{profile['energy']:.2f}"),
             ("sound", "acoustic" if profile["likes_acoustic"] else "produced")]
    if profile.get("min_popularity"):
        chips.append(("picks", "familiar"))
    if profile.get("max_popularity"):
        chips.append(("picks", "hidden gems"))
    return '<div class="vm-chips">' + "".join(
        f'<span class="vm-chip"><b>{k}</b>{html.escape(str(v))}</span>' for k, v in chips
    ) + "</div>"


def refresh_recs():
    profile = st.session_state.agent.build_profile()
    picks, result = diverse_top(profile, get_songs(), k=6)
    st.session_state.recs = dict(
        profile=profile, picks=picks, result=result,
        media=lookup_many([p[0] for p in picks]),
        expl=explain_recommendations(profile, picks),
    )


def handle_message(text: str):
    """Any message from any screen: process it, then morph into the recommender."""
    agent = st.session_state.agent
    say("user", text)
    st.session_state.mode = "rec"
    st.session_state.open_playlist = None
    if st.session_state.stage == "onboarding":
        agent.submit_answer(text)
        # Recommend as soon as we know the mood or activity; don't interrogate.
        question = None if agent.ready() else agent.next_question()
        if question:
            say("assistant", question)
            return
        st.session_state.stage = "chatting"
        profile = agent.build_profile()
        narrow = "" if "genre" in agent.known else "Want to narrow it down? Name a genre or how much energy. "
        say("assistant", f"Got it: **{profile_text(profile)}**. Here's what I found. {narrow}"
            "You can also say *more upbeat*, *calmer*, *less acoustic*, *more familiar*, "
            "*hidden gems*, or ask for something new like *gym music*, and thumb songs up or down.")
    else:
        profile = agent.apply_feedback(text)
        say("assistant", f"Updated: **{profile_text(profile)}**.")
    agent.log_request()  # feeds the "Your taste" stats
    st.session_state.needs_refresh = True


# --------------------------------------------------------------- callbacks
def go_home():
    st.session_state.mode = "home"
    st.session_state.open_playlist = None


def go_recommender():
    st.session_state.mode = "rec"


def open_playlist(playlist_id: str):
    st.session_state.mode = "home"
    st.session_state.open_playlist = playlist_id


def on_like(song):
    """Thumbs up: update taste now, but leave the grid alone until 'Update picks'."""
    st.session_state.agent.like_song(song)
    say("assistant", f"Liked **{song['title']}**. I'll use that when you update your picks.")
    st.session_state.recs_stale = st.session_state.stage == "chatting"
    save_current()


def on_dislike(song):
    st.session_state.agent.dislike_song(song)
    say("assistant", f"Okay, I'll skip **{song['title']}** and steer away from it.")
    st.session_state.recs_stale = st.session_state.stage == "chatting"
    save_current()


def update_picks():
    st.session_state.needs_refresh = True
    st.session_state.recs_stale = False


# ---------------------------------------------------------------- widgets
COVER_OK = re.compile(r"^https://[A-Za-z0-9._~%/-]+$")


def safe_cover(media):
    """A cover URL that is safe to drop into HTML/CSS, or None."""
    url = media.cover_url if media else None
    return url if url and COVER_OK.match(url) else None


def card_html(song, score, media, disliked=False) -> str:
    color = score_color(score)
    cover = media.cover_url if media and media.cover_url and media.cover_url.startswith("https://") else None
    art = (f'<img src="{html.escape(cover)}" alt="" loading="lazy">' if cover
           else '<div class="vm-note">♪</div>')
    spotify = (f'<div class="vm-link"><a href="https://open.spotify.com/track/'
               f'{html.escape(str(song["track_id"]))}" target="_blank">Open in Spotify ↗</a></div>'
               if song.get("track_id") else "")
    return (
        ('<span class="vm-dim"></span>' if disliked else "") +
        f'<div class="vm-art" style="--c:{color}">{art}'
        f'<span class="vm-badge" style="background:{color}">{score:.0f}% match</span></div>'
        f'<div class="vm-title" title="{html.escape(song["title"])}">{html.escape(song["title"])}</div>'
        f'<div class="vm-artist">{html.escape(song["artist"])}</div>'
        f'<div class="vm-tags"><span>{html.escape(song["genre"])}</span>'
        f'<span>{html.escape(song["mood"])}</span></div>{spotify}')


def song_card(song, score, media, ctx, why=None, reasons=""):
    agent = st.session_state.agent
    liked = any(x["id"] == song["id"] for x in agent.liked)
    disliked = song["id"] in agent.disliked_ids
    with st.container(key=f"card_{ctx}_{song['id']}"):
        st.markdown(card_html(song, score, media, disliked), unsafe_allow_html=True)
        if media and media.preview_url:
            st.audio(media.preview_url)
        else:
            st.caption("No preview available")
        c1, c2, c3 = st.columns(3)
        c1.button(" ", icon=":material/thumb_up:", key=f"up_{ctx}_{song['id']}",
                  on_click=on_like, args=(song,), help="More like this",
                  type="primary" if liked else "secondary", use_container_width=True)
        c2.button(" ", icon=":material/thumb_down:", key=f"down_{ctx}_{song['id']}",
                  on_click=on_dislike, args=(song,), help="Less like this",
                  type="primary" if disliked else "secondary", use_container_width=True)
        if why:
            with c3.popover(" ", icon=":material/info:", help="Why this song?",
                            use_container_width=True):
                st.write(why.text)
                st.caption(f"{'Written by Gemini' if why.source == 'gemini' else 'Built from song data'}"
                           f" · {reasons}")


def grid(items, cols, ctx, with_why=False):
    """items: list of (song, score, media, why, reasons)."""
    for start in range(0, len(items), cols):
        row = st.columns(cols)
        for col, (song, score, media, why, reasons) in zip(row, items[start:start + cols]):
            with col:
                song_card(song, score, media, ctx, why if with_why else None, reasons)


@st.dialog("Chats", width="large")
def chats_dialog():
    s = st.session_state
    save_current()  # so the current chat shows up with its latest messages
    if st.button("New chat", icon=":material/add:", key="dlg_new"):
        new_chat()
        st.rerun()
    saved = chat_store.load_all()
    current = next((c for c in saved if c["id"] == s.chat_id), None)
    rows = [(s.chat_id, chat_store.make_title(s.messages),
             current["updated"] if current else "", len(s.messages), True)]
    rows += [(c["id"], c["title"], c["updated"], len(c["messages"]), False)
             for c in saved if c["id"] != s.chat_id]
    for chat_id, title, updated, count, is_current in rows:
        info, open_col, del_col = st.columns([6, 1.3, 0.8], vertical_alignment="center")
        label = "Current chat" if is_current and title == "New chat" else title
        info.markdown(f"**{html.escape(label)}**" + ("  ·  *current*" if is_current else ""))
        info.caption(f"{chat_store.when(updated)}  ·  {count} messages".strip(" ·"))
        if open_col.button("Back to chat" if is_current else "Open", key=f"dlg_open_{chat_id}"):
            if is_current:
                go_recommender()
            else:
                open_chat(chat_store.get_chat(chat_id))
            st.rerun()
        if not is_current and del_col.button("", icon=":material/delete:", key=f"dlg_del_{chat_id}",
                                             help="Delete this chat"):
            chat_store.delete_chat(chat_id)
            st.rerun()


def top_bar():
    s = st.session_state
    with st.container(key="topbar"):
        logo, home, chats, liked, _gap, view = st.columns(
            [1.5, 0.9, 1.0, 0.8, 2.6, 3.4], vertical_alignment="center")
        logo.markdown(f'<div class="vm-brand">{html.escape(APP_NAME)}</div>', unsafe_allow_html=True)
        home.button("Home", icon=":material/home:", key="nav_home", on_click=go_home,
                    type="primary" if s.mode == "home" and not s.open_playlist else "secondary")
        if chats.button("Chats", icon=":material/forum:", key="nav_chats"):
            chats_dialog()
        if s.agent.liked:
            with liked.popover(f"♥ {len(s.agent.liked)}", help="Songs you liked"):
                for song in s.agent.liked:
                    st.caption(f"{song['title']} · {song['artist']}")
        if s.mode == "rec":
            with view:
                st.segmented_control("View", ["Split", "Recommendations", "Chat"], default="Split",
                                     key="view", label_visibility="collapsed")


# ------------------------------------------------------------------ pages
def hero_block(song, score, media, heading, blurb, action_label, action):
    cover = safe_cover(media)
    if cover:
        st.markdown(f"<style>.st-key-hero{{--hero-img:url('{cover}');}}</style>",
                    unsafe_allow_html=True)
    agent = st.session_state.agent
    liked = any(x["id"] == song["id"] for x in agent.liked)
    disliked = song["id"] in agent.disliked_ids
    with st.container(key="hero"):
        left, right = st.columns([2.6, 1], vertical_alignment="center")
        with left:
            st.markdown(
                ('<span class="vm-dim"></span>' if disliked else "") +
                f'<div class="vm-eyebrow">{html.escape(heading)}</div>'
                f'<div class="vm-hero-title">{html.escape(song["title"])}</div>'
                f'<div class="vm-hero-artist">{html.escape(song["artist"])}</div>',
                unsafe_allow_html=True)
            st.markdown(blurb)
            if media and media.preview_url:
                st.audio(media.preview_url)
            b1, b2, b3, _ = st.columns([0.7, 0.7, 2.4, 2])
            b1.button(" ", icon=":material/thumb_up:", key=f"up_hero_{song['id']}",
                      on_click=on_like, args=(song,), help="More like this",
                      type="primary" if liked else "secondary", use_container_width=True)
            b2.button(" ", icon=":material/thumb_down:", key=f"down_hero_{song['id']}",
                      on_click=on_dislike, args=(song,), help="Less like this",
                      type="primary" if disliked else "secondary", use_container_width=True)
            b3.button(action_label, on_click=action[0], args=action[1], key="hero_action")
        with right:
            art = (f'<img src="{html.escape(cover)}" alt="">' if cover
                   else '<div class="vm-note" style="height:100%">♪</div>')
            st.markdown(f'<div class="vm-hero-art">{art}</div>', unsafe_allow_html=True)


def bars_html(items, empty: str) -> str:
    if not items:
        return f'<div class="vm-empty">{empty}</div>'
    top = max(i["count"] for i in items)
    return "".join(
        f'<div class="vm-bar"><div class="vm-bar-top"><b>{html.escape(i["name"])}</b>'
        f'<span>{i["count"]}×</span></div><div class="vm-bar-track">'
        f'<div class="vm-bar-fill" style="width:{i["count"] / top * 100:.0f}%;'
        f'background:{score_color(100 - n * 17)}"></div></div></div>'
        for n, i in enumerate(items))


def stats_panel():
    stats = compute_stats(chat_store.load_all())
    with st.container(key="stats"):
        if not stats["has_data"]:
            st.markdown(
                '<div class="vm-empty">Chat with me and your favorite moods, genres and '
                'energy will show up here.</div>',
                unsafe_allow_html=True)
            return
        energy = stats["avg_energy"]
        sound = ("Leans acoustic" if stats["acoustic_share"] >= 0.5 else "Leans produced")
        liked_g = stats["top_liked_genres"]
        liked_line = (f'<div class="vm-empty" style="margin-top:.4rem">Most liked genre: '
                      f'<b style="color:var(--text)">{html.escape(liked_g[0]["name"])}</b></div>'
                      if liked_g else "")
        st.markdown(f"""
<div class="vm-stats">
  <div><div class="vm-stat-h">Your energy</div>
    <div class="vm-ring" style="--p:{energy * 100:.0f};--c:{score_color(40 + 60 * energy)}">
      <div><b>{energy * 100:.0f}%</b><span>avg energy</span></div></div>
    <div class="vm-empty" style="text-align:center;font-size:.8rem;padding:0">{sound}</div>
    <div class="vm-nums"><div><b>{stats["chats"]}</b><span>chats</span></div>
      <div><b>{stats["requests"]}</b><span>requests</span></div>
      <div><b>{stats["liked_total"]}</b><span>liked</span></div></div></div>
  <div><div class="vm-stat-h">Top moods</div>
    {bars_html(stats["top_moods"], "No moods yet.")}</div>
  <div><div class="vm-stat-h">Top genres</div>
    {bars_html(stats["top_genres"], "No genre picked yet, you're open to anything.")}{liked_line}</div>
</div>""", unsafe_allow_html=True)


def page_home():
    s = st.session_state
    hour = datetime.datetime.now().hour
    st.title("Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening")
    if s.stage == "onboarding":
        st.markdown(f'<div class="vm-ask">{html.escape(s.messages[-1]["content"])}'
                    '<span>Type your answer below to get started.</span></div>',
                    unsafe_allow_html=True)

    recs = s.recs
    if recs and recs["picks"]:
        song, score, _ = recs["picks"][0]
        hero_block(song, score, recs["media"][0], "Your top pick", recs["expl"][0].text,
                   "See all recommendations", (go_recommender, ()))
    else:
        pl = random.Random(datetime.date.today().toordinal()).choice(PLAYLISTS)
        song, score, _ = playlist_picks(pl["id"])[0]
        hero_block(song, score, lookup_many([song])[0], "Top pick today",
                   f"From **{pl['name']}**: {pl['tagline']}.", "Open playlist",
                   (open_playlist, (pl["id"],)))

    st.subheader("Your taste")
    stats_panel()

    st.subheader("Playlists")
    st.caption(f"Built from {len(get_songs()):,} songs, matched on mood and energy.")
    # Cover = first of a playlist's top 3 songs that Deezer knows; else a tinted gradient.
    candidates = [(p["id"], song) for p in PLAYLISTS for song, _, _ in playlist_picks(p["id"])[:3]]
    found = {}
    for (pid, _), media in zip(candidates, lookup_many([song for _, song in candidates])):
        if pid not in found and safe_cover(media):
            found[pid] = safe_cover(media)
    st.markdown("<style>" + "".join(
        f".st-key-tile_{p['id']}{{--cover:"
        + (f"url('{found[p['id']]}')" if p["id"] in found
           else f"linear-gradient(145deg,{p['tile']},#0e0e11)") + ";}"
        for p in PLAYLISTS) + "</style>", unsafe_allow_html=True)
    for start in range(0, len(PLAYLISTS), 3):
        for col, pl in zip(st.columns(3), PLAYLISTS[start:start + 3]):
            with col, st.container(key=f"tile_{pl['id']}"):
                st.markdown(f'<div class="vm-tile-name">{pl["name"]}</div>'
                            f'<div class="vm-tile-tag">{pl["tagline"]}</div>', unsafe_allow_html=True)
                st.button("Open", key=f"open_{pl['id']}", on_click=open_playlist, args=(pl["id"],))


def page_playlist(playlist_id: str):
    pl = next(p for p in PLAYLISTS if p["id"] == playlist_id)
    st.title(pl["name"])
    st.caption(pl["tagline"])
    picks = playlist_picks(playlist_id)
    media = lookup_many([p[0] for p in picks])
    grid([(sg, sc, m, None, r) for (sg, sc, r), m in zip(picks, media)], 4, f"pl_{playlist_id}")


def page_recommender(view: str):
    s = st.session_state
    recs = s.recs
    if view in ("Split", "Recommendations"):
        st.title("Recommended for you")
        if recs:
            chips_col, update_col = st.columns([5, 1.5], vertical_alignment="center")
            chips_col.markdown(profile_chips(recs["profile"]), unsafe_allow_html=True)
            if s.recs_stale:
                update_col.button("Update picks", icon=":material/refresh:", key="refresh_picks",
                                  on_click=update_picks, type="primary", use_container_width=True)
            res = recs["result"]
            if res.relaxed:
                st.caption(f"Not enough exact matches, so I widened the search ({res.tier}).")
            if res.popularity_relaxed:
                st.caption("Not enough songs at that familiarity level, so I ignored it.")
            st.write("")
            grid([(sg, sc, m, w, r) for (sg, sc, r), m, w in
                  zip(recs["picks"], recs["media"], recs["expl"])], 3, "rec", with_why=True)
        else:
            st.info("Answer a few questions below and your recommendations will show up here.")
    if view in ("Split", "Chat"):
        st.subheader("Chat")
        with st.container(height=300 if view == "Split" else 560, border=False):
            for msg in s.messages:
                avatar = ":material/graphic_eq:" if msg["role"] == "assistant" else ":material/person:"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])


# ------------------------------------------------------------------- main
init_state()

# The chat bar is always at the bottom, on every screen.
prompt = st.chat_input("Tell me what you're in the mood for…")
if prompt:
    handle_message(prompt)

if st.session_state.needs_refresh and st.session_state.stage == "chatting":
    with st.spinner("Finding songs…"):
        refresh_recs()
    st.session_state.needs_refresh = False
    st.session_state.recs_stale = False

if st.session_state.dirty:
    save_current()  # before rendering, so the stats panel sees this turn

top_bar()
# Only one preview plays at a time: starting any <audio> pauses all the others.
st.html("<script>if(!window.__vmSolo){window.__vmSolo=true;document.addEventListener("
        "'play',e=>{if(e.target.tagName!=='AUDIO')return;document.querySelectorAll('audio')"
        ".forEach(a=>{if(a!==e.target)a.pause()})},true);"
        # a song you just disliked goes quiet too
        "setInterval(()=>document.querySelectorAll('audio').forEach(a=>{if(!a.paused&&a.closest("
        "'[class*=\"st-key-card_\"],.st-key-hero')?.querySelector('.vm-dim'))a.pause()}),400)}</script>",
        unsafe_allow_javascript=True)
view = st.session_state.get("view") or "Split"
if prompt and view == "Recommendations":
    st.toast(st.session_state.messages[-1]["content"])  # the chat pane is hidden in this view
if llm.last_error in ("quota exceeded", "quota cooldown"):
    st.caption("Gemini's free quota is used up for now, so I'm using built-in fallbacks.")

if st.session_state.mode == "rec":
    page_recommender(view)
elif st.session_state.open_playlist:
    page_playlist(st.session_state.open_playlist)
else:
    page_home()

# Streamlit scrolls chat-style apps to the bottom on every run. Jump back to the
# top whenever the screen or conversation changes, so the new results are what you see.
scroll_key = (st.session_state.mode, st.session_state.open_playlist,
              st.session_state.chat_id, len(st.session_state.messages))
if st.session_state.get("_scroll_key") != scroll_key:
    st.session_state["_scroll_key"] = scroll_key
    st.session_state["_scroll_n"] = st.session_state.get("_scroll_n", 0) + 1
    scroll_js = (  # the nonce makes each script unique, so Streamlit re-runs it
        "<script>/*NONCE*/(()=>{const el=document.querySelector("
        "'[data-testid=\"stAppScrollToBottomContainer\"]')||document.querySelector("
        "'[data-testid=\"stMain\"]');if(!el)return;let stop=false;"
        # Keep the page at the top while it finishes loading (images and audio make it
        # grow, and Streamlit keeps re-pinning it to the bottom). Any real user input stops this.
        "['wheel','touchstart','keydown','mousedown'].forEach(e=>window.addEventListener("
        "e,()=>{stop=true},{once:true,capture:true}));const t0=Date.now();"
        "const tick=()=>{if(stop||Date.now()-t0>4500)return;el.scrollTop=0;"
        "requestAnimationFrame(tick)};tick();})();</script>"
    ).replace("NONCE", str(st.session_state["_scroll_n"]))
    st.html(scroll_js, unsafe_allow_javascript=True)
