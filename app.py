import streamlit as st
import psycopg2
import hashlib
from datetime import datetime, date
from streamlit_autorefresh import st_autorefresh
import pytz

st.set_page_config(page_title="Supabase Countdown", layout="wide")

# ==========================================================
# TIMEZONE CONFIG (IST)
# ==========================================================
IST = pytz.timezone("Asia/Kolkata")

def get_now():
    return datetime.now(IST)

# ==========================================================
# DATABASE CONNECTION (CACHED)
# ==========================================================
@st.cache_resource
def get_connection():
    conn = psycopg2.connect(
        st.secrets["SUPABASE_DB_URL"],
        sslmode="require"
    )
    conn.autocommit = True
    return conn

conn = get_connection()

def get_cursor():
    return conn.cursor()

# ==========================================================
# PASSWORD HASHING
# ==========================================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================================================
# USER FUNCTIONS
# ==========================================================
def create_user(username, password):
    try:
        cur = get_cursor()
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hash_password(password))
        )
        return True
    except:
        return False

def login_user(username, password):
    cur = get_cursor()
    cur.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (username, hash_password(password))
    )
    return cur.fetchone()

def get_user_by_id(user_id):
    cur = get_cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    return cur.fetchone()

def change_password(user_id, new_password):
    cur = get_cursor()
    cur.execute(
        "UPDATE users SET password=%s WHERE id=%s",
        (hash_password(new_password), user_id)
    )

def delete_account(user_id):
    cur = get_cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))

# ==========================================================
# COUNTDOWN FUNCTIONS
# ==========================================================
def add_countdown(user_id, title, target):
    try:
        cur = get_cursor()
        cur.execute(
            """
            INSERT INTO countdowns (user_id, title, created_at, target)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, title, get_now(), target)
        )
        return True
    except:
        return False

def update_countdown(cid, user_id, title, target):
    try:
        cur = get_cursor()
        cur.execute(
            """
            UPDATE countdowns
            SET title=%s, target=%s
            WHERE id=%s AND user_id=%s
            """,
            (title, target, cid, user_id)
        )
        return True
    except:
        return False

def delete_countdown(cid):
    cur = get_cursor()
    cur.execute("DELETE FROM countdowns WHERE id=%s", (cid,))

def get_countdown_by_id(cid):
    cur = get_cursor()
    cur.execute("SELECT * FROM countdowns WHERE id=%s", (cid,))
    return cur.fetchone()

# ==========================================================
# CACHED QUERY (5s TTL)
# ==========================================================
@st.cache_data(ttl=5)
def get_filtered_countdowns(user_id, search_query, filter_option):
    cur = get_cursor()

    query = "SELECT * FROM countdowns WHERE user_id=%s"
    params = [user_id]

    if search_query:
        query += " AND LOWER(title) LIKE %s"
        params.append(f"%{search_query.lower()}%")

    current_time = get_now()

    if filter_option == "Active":
        query += " AND target > %s"
        params.append(current_time)
    elif filter_option == "Expired":
        query += " AND target <= %s"
        params.append(current_time)

    query += " ORDER BY target ASC"

    cur.execute(query, tuple(params))
    return cur.fetchall()

# ==========================================================
# SESSION INIT
# ==========================================================
if "user" not in st.session_state:
    st.session_state.user = None

if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

if "edit_data" not in st.session_state:
    st.session_state.edit_data = None

# ==========================================================
# AUTH
# ==========================================================
if not st.session_state.user:

    st.title("🔐 Login / Register")

    mode = st.radio("Select Option", ["Login", "Register"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if mode == "Register":
        if st.button("Create Account"):
            if create_user(username, password):
                st.success("Account created! Please login.")
            else:
                st.error("Username already exists.")

    if mode == "Login":
        if st.button("Login"):
            user = login_user(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid credentials.")

# ==========================================================
# DASHBOARD
# ==========================================================
else:

    user_id = st.session_state.user[0]
    username = st.session_state.user[1]

    if not get_user_by_id(user_id):
        st.session_state.user = None
        st.rerun()

    st.title(f"⏳ Welcome, {username}")

    st.sidebar.header("🔎 Search & Filter")
    search_query = st.sidebar.text_input("Search by Title")
    filter_option = st.sidebar.selectbox(
        "Filter by Status",
        ["All", "Active", "Expired"]
    )

    # Add Countdown
    with st.expander("➕ Add Countdown", expanded=True):

        title = st.text_input("Title")
        selected_date = st.date_input("Date", min_value=date.today())

        col1, col2, col3 = st.columns(3)
        hour = col1.selectbox("Hour", list(range(0, 24)))
        minute = col2.selectbox("Minute", list(range(0, 60)))
        second = col3.selectbox("Second", list(range(0, 60)))

        if st.button("Save Countdown"):

            naive_dt = datetime(
                selected_date.year,
                selected_date.month,
                selected_date.day,
                hour,
                minute,
                second
            )

            target_dt = IST.localize(naive_dt)

            if target_dt <= get_now():
                st.error("Cannot select past time.")
            else:
                success = add_countdown(user_id, title, target_dt)
                if not success:
                    st.error("Title must be unique per user.")
                else:
                    st.cache_data.clear()
                    st.rerun()

    # Display
    st.subheader("📅 Your Countdowns")

    countdowns = get_filtered_countdowns(
        user_id,
        search_query,
        filter_option
    )

    for cid, uid, title, created_at, target in countdowns:

        current_time = get_now()
        diff = target - current_time

        st.markdown(f"### {title}")

        if diff.total_seconds() > 0:

            days = diff.days
            hours, rem = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            st.write(f"{days}d {hours}h {minutes}m {seconds}s remaining")

            total = (target - created_at).total_seconds()
            elapsed = (current_time - created_at).total_seconds()
            progress = min(max(elapsed / total, 0), 1)
            percent = int(progress * 100)

            remaining_ratio = 1 - progress
            color = "#2ea043" if remaining_ratio > 0.5 else "#d29922" if remaining_ratio > 0.2 else "#cf222e"

            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:12px;">
                    <div style="flex-grow:1;background:#e1e4e8;border-radius:6px;height:12px;">
                        <div style="width:{percent}%;background:{color};height:100%;border-radius:6px;"></div>
                    </div>
                    <div style="min-width:50px;text-align:right;font-weight:600;">
                        {percent}%
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        else:
            st.error("⏰ Time's Up!")

    st_autorefresh(interval=5000, key="refresh")
