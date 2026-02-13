import streamlit as st
import psycopg2
import hashlib
from datetime import datetime, date
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Supabase Countdown", layout="wide")

# =============================
# DATABASE CONNECTION (CACHED)
# =============================
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

# =============================
# HELPERS
# =============================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    try:
        cursor = get_cursor()
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hash_password(password))
        )
        return True
    except:
        return False

def login_user(username, password):
    cursor = get_cursor()
    cursor.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (username, hash_password(password))
    )
    return cursor.fetchone()

def get_user_by_id(user_id):
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    return cursor.fetchone()

def change_password(user_id, new_password):
    cursor = get_cursor()
    cursor.execute(
        "UPDATE users SET password=%s WHERE id=%s",
        (hash_password(new_password), user_id)
    )

def delete_account(user_id):
    cursor = get_cursor()
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))

def add_countdown(user_id, title, target):
    try:
        cursor = get_cursor()
        cursor.execute(
            """
            INSERT INTO countdowns (user_id, title, created_at, target)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, title, datetime.now(), target)
        )
        st.cache_data.clear()
        return True
    except:
        return False

def update_countdown(cid, user_id, title, target):
    try:
        cursor = get_cursor()
        cursor.execute(
            """
            UPDATE countdowns
            SET title=%s, target=%s
            WHERE id=%s AND user_id=%s
            """,
            (title, target, cid, user_id)
        )
        st.cache_data.clear()
        return True
    except:
        return False

def delete_countdown(cid):
    cursor = get_cursor()
    cursor.execute("DELETE FROM countdowns WHERE id=%s", (cid,))
    st.cache_data.clear()

# =============================
# CACHED QUERY (FAST LOAD)
# =============================
@st.cache_data(ttl=5)
def get_filtered_countdowns(user_id, search_query, filter_option):

    cursor = get_cursor()

    query = "SELECT * FROM countdowns WHERE user_id=%s"
    params = [user_id]

    if search_query:
        query += " AND LOWER(title) LIKE %s"
        params.append(f"%{search_query.lower()}%")

    now = datetime.now()

    if filter_option == "Active":
        query += " AND target > %s"
        params.append(now)
    elif filter_option == "Expired":
        query += " AND target <= %s"
        params.append(now)

    query += " ORDER BY target ASC"

    cursor.execute(query, tuple(params))
    return cursor.fetchall()

# =============================
# SESSION INIT
# =============================
if "user" not in st.session_state:
    st.session_state.user = None

if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

# =============================
# AUTH SECTION
# =============================
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

# =============================
# DASHBOARD
# =============================
else:

    user_id = st.session_state.user[0]
    username = st.session_state.user[1]

    st.title(f"⏳ Welcome, {username}")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

    with col2:
        with st.expander("⚠ Delete Account"):
            confirm = st.text_input("Enter Password", type="password")
            if st.button("Delete My Account"):
                stored_hash = get_user_by_id(user_id)[2]
                if hash_password(confirm) == stored_hash:
                    delete_account(user_id)
                    st.session_state.user = None
                    st.success("Account deleted.")
                    st.rerun()
                else:
                    st.error("Incorrect password.")

    # Sidebar
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

        colA, colB, colC = st.columns(3)
        with colA:
            hour = st.selectbox("Hour", list(range(0, 24)))
        with colB:
            minute = st.selectbox("Minute", list(range(0, 60)))
        with colC:
            second = st.selectbox("Second", list(range(0, 60)))

        if st.button("Save Countdown"):
            target_dt = datetime(
                selected_date.year,
                selected_date.month,
                selected_date.day,
                hour,
                minute,
                second
            )

            if target_dt <= datetime.now():
                st.error("Cannot select past time.")
            else:
                if not add_countdown(user_id, title, target_dt):
                    st.error("Title must be unique per user.")
                else:
                    st.success("Countdown added.")
                    st.rerun()

    # Display Countdowns
    st.subheader("📅 Your Countdowns")

    countdowns = get_filtered_countdowns(
        user_id,
        search_query,
        filter_option
    )

    for item in countdowns:

        cid, uid, title, created_at, target = item
        now = datetime.now()
        diff = target - now

        st.markdown(f"### {title}")

        if diff.total_seconds() > 0:

            days = diff.days
            hours, rem = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(rem, 60)

            st.write(f"{days}d {hours}h {minutes}m {seconds}s remaining")

        else:
            st.error("⏰ Time's Up!")

    # Reduced refresh frequency (faster)
    st_autorefresh(interval=5000, key="refresh")
