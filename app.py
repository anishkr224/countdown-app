import streamlit as st
import psycopg2
import hashlib
from datetime import datetime, date
from streamlit_autorefresh import st_autorefresh

# =============================
# DATABASE CONNECTION
# =============================
SUPABASE_DB_URL = st.secrets["SUPABASE_DB_URL"]

conn = psycopg2.connect(SUPABASE_DB_URL)
conn.autocommit = True
cursor = conn.cursor()

# =============================
# HELPERS
# =============================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hash_password(password))
        )
        return True
    except:
        return False

def login_user(username, password):
    cursor.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (username, hash_password(password))
    )
    return cursor.fetchone()

def get_user_by_id(user_id):
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    return cursor.fetchone()

def change_password(user_id, new_password):
    cursor.execute(
        "UPDATE users SET password=%s WHERE id=%s",
        (hash_password(new_password), user_id)
    )

def delete_account(user_id):
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))

def add_countdown(user_id, title, target):
    try:
        cursor.execute(
            """
            INSERT INTO countdowns (user_id, title, created_at, target)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, title, datetime.now(), target)
        )
        return True
    except:
        return False

def update_countdown(cid, user_id, title, target):
    try:
        cursor.execute(
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
    cursor.execute("DELETE FROM countdowns WHERE id=%s", (cid,))

def get_countdown_by_id(cid):
    cursor.execute("SELECT * FROM countdowns WHERE id=%s", (cid,))
    return cursor.fetchone()

def get_filtered_countdowns(user_id, search_query, filter_option):

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

if "edit_data" not in st.session_state:
    st.session_state.edit_data = None

st.set_page_config(page_title="Supabase Countdown", layout="wide")

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

    # Session validation
    if not get_user_by_id(user_id):
        st.session_state.user = None
        st.rerun()

    st.title(f"⏳ Welcome, {username}")

    # =============================
    # ACCOUNT MANAGEMENT
    # =============================
    colA, colB, colC = st.columns(3)

    with colA:
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

    with colB:
        with st.expander("🔑 Change Password"):
            current_pass = st.text_input("Current Password", type="password")
            new_pass = st.text_input("New Password", type="password")

            if st.button("Update Password"):
                stored_hash = get_user_by_id(user_id)[2]

                if hash_password(current_pass) != stored_hash:
                    st.error("Current password incorrect.")
                elif not new_pass:
                    st.error("New password cannot be empty.")
                else:
                    change_password(user_id, new_pass)
                    st.success("Password updated.")

    with colC:
        with st.expander("⚠ Delete Account"):
            confirm_pass = st.text_input("Enter Password", type="password")
            confirm_check = st.checkbox("I understand this is permanent.")

            if st.button("Delete My Account"):
                stored_hash = get_user_by_id(user_id)[2]

                if hash_password(confirm_pass) != stored_hash:
                    st.error("Password incorrect.")
                elif not confirm_check:
                    st.error("Please confirm deletion.")
                else:
                    delete_account(user_id)
                    st.session_state.user = None
                    st.success("Account deleted.")
                    st.rerun()

    # =============================
    # HANDLE EDIT PREFILL
    # =============================
    if st.session_state.edit_id and not st.session_state.edit_data:
        record = get_countdown_by_id(st.session_state.edit_id)
        if record:
            _, _, title, created_at, target = record
            target_dt = target

            st.session_state.edit_data = {
                "title": title,
                "date": target_dt.date(),
                "hour": target_dt.hour,
                "minute": target_dt.minute,
                "second": target_dt.second
            }

    # =============================
    # SIDEBAR FILTERS
    # =============================
    st.sidebar.header("🔎 Search & Filter")
    search_query = st.sidebar.text_input("Search by Title")
    filter_option = st.sidebar.selectbox(
        "Filter by Status",
        ["All", "Active", "Expired"]
    )

    # =============================
    # ADD / EDIT COUNTDOWN
    # =============================
    with st.expander("➕ Add / Edit Countdown", expanded=True):

        default_title = ""
        default_date = date.today()
        default_hour = 0
        default_minute = 0
        default_second = 0

        if st.session_state.edit_data:
            default_title = st.session_state.edit_data["title"]
            default_date = st.session_state.edit_data["date"]
            default_hour = st.session_state.edit_data["hour"]
            default_minute = st.session_state.edit_data["minute"]
            default_second = st.session_state.edit_data["second"]

        title = st.text_input("Title", value=default_title)
        selected_date = st.date_input("Date", value=default_date, min_value=date.today())

        col1, col2, col3 = st.columns(3)
        with col1:
            hour = st.selectbox("Hour", list(range(0, 24)), index=default_hour)
        with col2:
            minute = st.selectbox("Minute", list(range(0, 60)), index=default_minute)
        with col3:
            second = st.selectbox("Second", list(range(0, 60)), index=default_second)

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
                if st.session_state.edit_id:
                    success = update_countdown(
                        st.session_state.edit_id,
                        user_id,
                        title,
                        target_dt
                    )
                else:
                    success = add_countdown(user_id, title, target_dt)

                if not success:
                    st.error("Title must be unique per user.")
                else:
                    st.session_state.edit_id = None
                    st.session_state.edit_data = None
                    st.rerun()

    # =============================
    # DISPLAY COUNTDOWNS
    # =============================
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

        col1, col2, col3 = st.columns([6,1,1])

        with col1:
            st.markdown(f"### {title}")

            if diff.total_seconds() > 0:

                days = diff.days
                hours, rem = divmod(diff.seconds, 3600)
                minutes, seconds = divmod(rem, 60)
                st.write(f"{days}d {hours}h {minutes}m {seconds}s remaining")

                total_duration = (target - created_at).total_seconds()
                elapsed = (now - created_at).total_seconds()
                progress = min(max(elapsed / total_duration, 0), 1)
                percent = int(progress * 100)

                remaining_ratio = 1 - progress

                if remaining_ratio > 0.5:
                    color = "#2ea043"
                elif remaining_ratio > 0.2:
                    color = "#d29922"
                else:
                    color = "#cf222e"

                st.markdown(
                    f"""
                    <div style="display:flex;align-items:center;gap:12px;margin-top:8px;">
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

        with col2:
            if st.button("✏", key=f"edit_{cid}"):
                st.session_state.edit_id = cid
                st.session_state.edit_data = None
                st.rerun()

        with col3:
            if st.button("🗑", key=f"del_{cid}"):
                delete_countdown(cid)
                st.rerun()

    st_autorefresh(interval=1000, key="refresh")
