import streamlit as st
import random
from collections import deque
import pandas as pd
from itertools import combinations
import json
import os
from supabase_client import get_supabase

supabase = get_supabase()

# ======================================================
# PAGE CONFIG
# ======================================================
st.set_page_config(page_title="Pickleball Auto Stack LPC Official", page_icon="🎾", layout="wide")

st.markdown("""
<style>
footer {visibility:hidden;}
a[href*="github.com/streamlit"]{display:none!important;}

.court-card{
    padding:14px;
    border-radius:12px;
    background:#f4f6fa;
    margin-bottom:12px;
}
.waiting-box{
    background:#fff3cd;
    padding:10px;
    border-radius:10px;
}
</style>
""", unsafe_allow_html=True)

# =========================
# HEADER PHOTO
# =========================
col1, col2, col3 = st.columns([1,2,1])
with col2:
    st.image("lpcphoto.jpg", width=300)

st.title("🎾 Pickleball Auto Stack LPC Official")
st.caption("LET'S PLAY!")

# ======================================================
# HELPERS
# ======================================================
def icon(skill):
    return {"BEGINNER":"🟢","NOVICE":"🟡","INTERMEDIATE":"🔴"}[skill]

def superscript_number(n):
    sup_map = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    return str(n).translate(sup_map)

def fmt(p):
    name, skill, dupr = p
    games = st.session_state.players.get(name, {}).get("games", 0)
    return f"{icon(skill)} {superscript_number(games)} {name}"

def safe_group(players):
    skills = {p[1] for p in players}
    return not ("BEGINNER" in skills and "INTERMEDIATE" in skills)

def make_teams(players):
    random.shuffle(players)
    return [players[:2], players[2:]]

# ======================================================
# SESSION INIT
# ======================================================
def init():
    ss = st.session_state
    ss.setdefault("queue", deque())
    ss.setdefault("courts", {})
    ss.setdefault("locked", {})
    ss.setdefault("scores", {})
    ss.setdefault("history", [])
    ss.setdefault("started", False)
    ss.setdefault("court_count", 2)
    ss.setdefault("players", {})

init()

# ======================================================
# DELETE PLAYER
# ======================================================
def delete_player(name):
    st.session_state.queue = deque([p for p in st.session_state.queue if p[0] != name])

    for cid, teams in st.session_state.courts.items():
        if not teams:
            continue
        new_teams = []
        for team in teams:
            new_teams.append([p for p in team if p[0] != name])

        if len(new_teams[0]) < 2 or len(new_teams[1]) < 2:
            st.session_state.courts[cid] = None
            st.session_state.locked[cid] = False
        else:
            st.session_state.courts[cid] = new_teams

    st.session_state.players.pop(name, None)

# ======================================================
# MATCH ENGINE
# ======================================================
def take_four_safe():
    q = list(st.session_state.queue)
    if len(q) < 4:
        return None

    for combo in combinations(range(len(q)), 4):
        group = [q[i] for i in combo]
        if safe_group(group):
            for i in sorted(combo, reverse=True):
                del q[i]
            st.session_state.queue = deque(q)
            return group
    return None

def start_match(cid):
    if st.session_state.locked.get(cid):
        return

    players = take_four_safe()
    if not players:
        return

    st.session_state.courts[cid] = make_teams(players)
    st.session_state.locked[cid] = True
    st.session_state.scores[cid] = [0, 0]

def finish_match(cid):
    teams = st.session_state.courts[cid]
    scoreA, scoreB = st.session_state.scores[cid]
    teamA, teamB = teams

    if scoreA > scoreB:
        winner = "Team A"
        winners, losers = teamA, teamB
    elif scoreB > scoreA:
        winner = "Team B"
        winners, losers = teamB, teamA
    else:
        winner = "DRAW"
        winners = losers = []

    for p in teamA + teamB:
        st.session_state.players[p[0]]["games"] += 1

    for p in winners:
        st.session_state.players[p[0]]["wins"] += 1

    for p in losers:
        st.session_state.players[p[0]]["losses"] += 1

    # Supabase update
    try:
        for p in teamA + teamB:
            name = p[0]
            stats = st.session_state.players[name]
            supabase.table("players").update({
                "games": stats["games"],
                "wins": stats["wins"]
            }).eq("name", name).execute()
    except:
        pass

    st.session_state.history.append({
        "Court": cid,
        "Team A": " & ".join(p[0] for p in teamA),
        "Team B": " & ".join(p[0] for p in teamB),
        "Score A": scoreA,
        "Score B": scoreB,
        "Winner": winner
    })

    players = teamA + teamB
    random.shuffle(players)
    st.session_state.queue.extend(players)

    st.session_state.courts[cid] = None
    st.session_state.locked[cid] = False
    st.session_state.scores[cid] = [0, 0]

def auto_fill():
    if not st.session_state.started:
        return
    for cid in st.session_state.courts:
        if st.session_state.courts[cid] is None:
            start_match(cid)

# ======================================================
# PROFILE SAVE / LOAD / DELETE
# ======================================================
SAVE_DIR = "profiles"
os.makedirs(SAVE_DIR, exist_ok=True)

def save_profile(name):
    data = {
        "queue": list(st.session_state.queue),
        "courts": st.session_state.courts,
        "locked": st.session_state.locked,
        "scores": st.session_state.scores,
        "history": st.session_state.history,
        "started": st.session_state.started,
        "court_count": st.session_state.court_count,
        "players": st.session_state.players
    }
    with open(os.path.join(SAVE_DIR, f"{name}.json"), "w") as f:
        json.dump(data, f)
    st.success("Profile saved!")

def load_profile(name):
    with open(os.path.join(SAVE_DIR, f"{name}.json"), "r") as f:
        data = json.load(f)

    st.session_state.queue = deque(data["queue"])
    st.session_state.courts = {int(k): v for k,v in data["courts"].items()}
    st.session_state.locked = {int(k): v for k,v in data["locked"].items()}
    st.session_state.scores = {int(k): v for k,v in data["scores"].items()}
    st.session_state.history = data["history"]
    st.session_state.started = data["started"]
    st.session_state.court_count = data["court_count"]
    st.session_state.players = data["players"]

def delete_profile(name):
    os.remove(os.path.join(SAVE_DIR, f"{name}.json"))
    st.success("Profile deleted!")
    st.rerun()

# ======================================================
# SIDEBAR
# ======================================================
with st.sidebar:

    st.header("⚙ Setup")

    st.session_state.court_count = st.selectbox(
    "Courts",
    [1, 2, 3, 4, 5, 6],
    index=st.session_state.court_count - 1
)

    # Add Player from Supabase
    try:
        registered = supabase.table("players").select("*").execute().data
    except:
        registered = []

    names = [p["name"] for p in registered]

    with st.form("add_form", clear_on_submit=True):
        selected = st.selectbox("Select Player", [""] + names)
        if st.form_submit_button("Add Player") and selected:
            if selected not in st.session_state.players:
                data = next(p for p in registered if p["name"] == selected)
                st.session_state.queue.appendleft((selected, data["skill"].upper(), data["dupr"]))
                st.session_state.players[selected] = {
                    "dupr": data["dupr"],
                    "games":0,
                    "wins":0,
                    "losses":0
                }

    # Delete Player
    if st.session_state.players:
        st.divider()
        remove = st.selectbox("❌ Remove Player", list(st.session_state.players.keys()))
        if st.button("Delete Player"):
            delete_player(remove)
            st.rerun()

    st.divider()

    col1, col2 = st.columns(2)
    if col1.button("🚀 Start"):
        st.session_state.started = True
        st.session_state.courts = {i:None for i in range(1, st.session_state.court_count+1)}
        st.session_state.locked = {i:False for i in st.session_state.courts}
        st.session_state.scores = {i:[0,0] for i in st.session_state.courts}
        st.rerun()

    if col2.button("🔄 Reset"):
        st.session_state.clear()
        st.rerun()

    st.divider()

    # Profiles
    profile_name = st.text_input("Profile Name")
    col1, col2 = st.columns(2)

    if col1.button("Save Profile") and profile_name:
        save_profile(profile_name)

    profiles = [f[:-5] for f in os.listdir(SAVE_DIR) if f.endswith(".json")]
    selected_profile = st.selectbox("Select Profile", [""] + profiles)

    if col2.button("Load Profile") and selected_profile:
        load_profile(selected_profile)
        st.rerun()

    if st.button("Delete Profile") and selected_profile:
        delete_profile(selected_profile)

# ======================================================
# MAIN
# ======================================================
auto_fill()

st.subheader("⏳ Waiting Queue")
if st.session_state.queue:
    st.markdown(
        f'<div class="waiting-box">{", ".join(fmt(p) for p in st.session_state.queue)}</div>',
        unsafe_allow_html=True
    )
else:
    st.success("No players waiting 🎉")

if not st.session_state.started:
    st.stop()

st.divider()
st.subheader("🏟 Live Courts")

cols = st.columns(2)

for i, cid in enumerate(st.session_state.courts):

    with cols[i % 2]:

        st.markdown('<div class="court-card">', unsafe_allow_html=True)
        st.markdown(f"### Court {cid}")

        teams = st.session_state.courts[cid]

        if not teams:
            st.info("Waiting for safe players...")
            st.markdown('</div>', unsafe_allow_html=True)
            continue

        st.write("**Team A**  \n" + " & ".join(fmt(p) for p in teams[0]))
        st.write("**Team B**  \n" + " & ".join(fmt(p) for p in teams[1]))

        c1, c2 = st.columns(2)

        if c1.button("🔀 Shuffle Teams", key=f"shuffle_{cid}"):
            players = teams[0] + teams[1]
            random.shuffle(players)
            st.session_state.courts[cid] = [players[:2], players[2:]]
            st.rerun()

        if c2.button("🔁 Rematch", key=f"rematch_{cid}"):
            st.session_state.scores[cid] = [0,0]
            st.rerun()

        st.divider()

        a = st.number_input("Score A", 0, key=f"A_{cid}")
        b = st.number_input("Score B", 0, key=f"B_{cid}")

        if st.button("✅ Submit Score", key=f"submit_{cid}"):
            st.session_state.scores[cid] = [a,b]
            finish_match(cid)
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        # Swap Section
        st.divider()
        st.markdown("**🔁 Swap Player**")

        flat = teams[0] + teams[1]
        queue_list = list(st.session_state.queue)

        if flat and queue_list:

            out_player = st.selectbox(
                "Player OUT",
                [p[0] for p in flat],
                key=f"swap_out_{cid}"
            )

            in_player = st.selectbox(
                "Player IN",
                [p[0] for p in queue_list],
                key=f"swap_in_{cid}"
            )

            if st.button("🔄 Swap", key=f"swap_btn_{cid}"):

                ci = next(i for i,p in enumerate(flat) if p[0]==out_player)
                qi = next(i for i,p in enumerate(queue_list) if p[0]==in_player)

                flat[ci], queue_list[qi] = queue_list[qi], flat[ci]

                st.session_state.courts[cid] = [flat[:2], flat[2:]]
                st.session_state.queue = deque(queue_list)

                st.rerun()
