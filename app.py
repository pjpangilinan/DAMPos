import streamlit as st
from streamlit_lottie import st_lottie
from streamlit_extras.stylable_container import stylable_container
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import random
import uuid
import pandas as pd
import math
from supabase import create_client
import bcrypt
import re
import time
import json
import base64

# ------------------------ DB Functions ------------------------ #
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ------------------------ Supabase User Functions ------------------------ #
def get_user(username):
    result = supabase.table("users").select("*").eq("username", username).execute()
    if result.data and len(result.data) == 1:
        return result.data[0]
    return None

def add_user(username, password):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    empty_fs = json.dumps({"root": {}})
    empty_disk = json.dumps([None] * 64) 
    supabase.table("users").insert({
        "username": username,
        "password_hash": hashed,
        "fs_json": empty_fs,
        "disk_json": empty_disk
    }).execute()

def update_user_password(username, new_hash):
    supabase.table("users").update({"password_hash": new_hash}).eq("username", username).execute()

def save_fs_to_db(username):
    fs_json = json.dumps(st.session_state.fs)
    disk_json = json.dumps(st.session_state.disk)
    supabase.table("users").update({
        "fs_json": fs_json,
        "disk_json": disk_json
    }).eq("username", username).execute()

# ------------------------ Utility Functions ------------------------ #
def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def is_strong_password(password):
    pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$'
    return re.match(pattern, password)

def encode_bytes(b):
    return base64.b64encode(b).decode('utf-8')

def decode_string(s):
    return base64.b64decode(s.encode('utf-8'))

# ------------------------ Styling ------------------------ #
def set_styles():
    st.markdown("""
        <style>
        .login-box {
            max-width: 450px;
            margin: 5rem auto;
            background: #ffffff;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }

        .login-header {
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            background: #333;
            color: white;
            border-radius: 8px 8px 0 0;
            padding: 10px 0;
            margin: -2rem -2rem 1.5rem -2rem;
        }
        </style>
    """, unsafe_allow_html=True)

# ------------------------ Start UP Animation ------------------------ #
def load_lottie_file(filepath: str):
    with open(filepath, "r") as f:
        return json.load(f)

def startup_screen():
    lottie_animation = load_lottie_file("startup.json")
    st_lottie(lottie_animation, height=400, width=670, key="startup")
    st.markdown("<h3 style='text-align: center;'>Starting DAMPos...</h3>", unsafe_allow_html=True)
    time.sleep(6.3)

DISK_SIZE = 64
BLOCK_SIZE = 1 * 1024 * 1024  # 1 MB per block

# ------------------------ Home Page ------------------------ #
def home_page():
    username = st.session_state.get("username", "me")

    # Get local time (GMT+8 - Manila)
    local_time = datetime.now(ZoneInfo("Asia/Manila"))
    date_str = local_time.strftime("%B %d, %Y")
    time_str = local_time.strftime("%I:%M %p")

    def encode_image(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()

    st.markdown(f"""
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="margin-bottom: 0;">👋 Welcome, <span style="color:#007BFF;">{username}</span>!</h1>
            <p style="font-size: 18px; margin: 4px 0;">Today is <strong>{date_str}</strong></p>
            <p style="font-size: 16px; color: gray;">
            It is currently <span style="font-family: monospace; background-color: #eee; padding: 2px 4px; border-radius: 4px;">{time_str} GMT+8</span>
            </p>
        </div>
        <hr style="margin: 1.5rem 0;">
    """, unsafe_allow_html=True)

    def icon_card_button(icon_path, label, key, target_page):
        encoded_img = encode_image(icon_path)
        btn_content = f"![icon](data:image/png;base64,{encoded_img})\n**{label}**"

        with stylable_container(
            key=f"icon_card_{key}",
            css_styles="""
                button {
                    display: flex;
                    justify-content: center;
                    margin: 0.5rem auto;
                    height: 8rem !important;
                    width: 8rem !important;
                    padding: 0.5rem !important;
                    border-radius: 1.2rem !important;
                    border: 2px solid #e0e0e0 !important;
                    background-color: white !important;
                    transition: transform 0.2s ease, background-color 0.2s ease;
                }
                button:hover {
                    background-color: #f0f0f0 !important;
                    transform: scale(1.05);
                    border-color: #aaaaaa !important;
                    color: #067dfc !important;
                }
                img {
                    width: 100%;
                    max-width: 120px;
                    height: auto;
                    object-fit: contain;
                    display: block;
                    margin: 0 auto;
                }
            """
        ):
            if st.button(btn_content, key=key):
                st.session_state.page = target_page
                st.rerun()

    cols = st.columns(5)
    with cols[0]:
        icon_card_button("assets/folder.png", "Files", "go_fs", "fs")
    with cols[1]:
        icon_card_button("assets/task.png", "Task Manager", "tm", "tm")
    with cols[2]:
        icon_card_button("assets/robot.png", "DAMPbot", "cbot", "cbot")
    with cols[3]:
        icon_card_button("assets/game.png", "Game", "game", "game")
    with cols[4]:
        icon_card_button("assets/settings.png", "System Information", "settings", "settings")
    
# ------------------------ File System Management ------------------------ #
def file_system_page():
    if st.button("\U0001F519 Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    if "disk" not in st.session_state:
        user_data = get_user(st.session_state.username) if "username" in st.session_state else None
        if user_data and "disk_json" in user_data and user_data["disk_json"]:
            try:
                st.session_state.disk = json.loads(user_data["disk_json"])
            except:
                st.session_state.disk = [None] * DISK_SIZE
        else:
            st.session_state.disk = [None] * DISK_SIZE

    if "current_path" not in st.session_state:
        st.session_state.current_path = ["root"]
    if "allocation_strategy" not in st.session_state:
        st.session_state.allocation_strategy = "First-Fit"
    if "fs" not in st.session_state:
        user_data = get_user(st.session_state.username) if "username" in st.session_state else None
        if user_data and "fs_json" in user_data and user_data["fs_json"]:
            st.session_state.fs = json.loads(user_data["fs_json"])
        else:
            st.session_state.fs = {"root": {}}

    def get_current_dir():
        ref = st.session_state.fs
        for p in st.session_state.current_path:
            ref = ref[p]
        return ref

    def allocate_contiguous_blocks(size_bytes):
        needed_blocks = math.ceil(size_bytes / BLOCK_SIZE)
        free_ranges = []
        start = None

        for i in range(DISK_SIZE + 1):
            if i < DISK_SIZE and st.session_state.disk[i] is None:
                if start is None:
                    start = i
            else:
                if start is not None:
                    length = i - start
                    if length >= needed_blocks:
                        free_ranges.append((start, length))
                    start = None

        if not free_ranges:
            return None

        strategy = st.session_state.allocation_strategy
        if strategy == "First-Fit":
            chosen = free_ranges[0]
        elif strategy == "Best-Fit":
            chosen = min(free_ranges, key=lambda x: x[1])
        else:
            return None

        start_block = chosen[0]
        for j in range(start_block, start_block + needed_blocks):
            st.session_state.disk[j] = "ALLOCATED"
        return list(range(start_block, start_block + needed_blocks))

    def deallocate_blocks(blocks):
        for i in blocks:
            if 0 <= i < DISK_SIZE:
                st.session_state.disk[i] = None

    def remove_file_by_path(directory, path_parts):
        if len(path_parts) == 1:
            if path_parts[0] in directory:
                del directory[path_parts[0]]
                return True
        else:
            subdir = path_parts[0]
            if subdir in directory and isinstance(directory[subdir], dict):
                return remove_file_by_path(directory[subdir], path_parts[1:])
        return False

    def search_files(name_query, directory=None, path="root"):
        if directory is None:
            directory = st.session_state.fs["root"]
        results = []
        for key, value in directory.items():
            current_path = f"{path}/{key}"
            if isinstance(value, dict):
                if "content" in value:
                    if name_query.lower() in key.lower():
                        results.append((key, current_path, value))
                else:
                    results.extend(search_files(name_query, value, current_path))
        return results

    def render_disk():
        with st.expander("\U0001F4BE Disk Block View", expanded=False):
            used = sum(1 for b in st.session_state.disk if b is not None)
            st.progress(
                used / DISK_SIZE,
                text=f"Used {used} / {DISK_SIZE} blocks ({used * BLOCK_SIZE / (1024**2):.2f} MB / {(DISK_SIZE * BLOCK_SIZE) / (1024**2):.0f} MB)"
            )
            cols = st.columns(10)
            for i in range(DISK_SIZE):
                with cols[i % 10]:
                    color = "\U0001F7E9" if st.session_state.disk[i] is None else "\U0001F535"
                    st.write(f"{color} {i}")

    def render_directory(current_dir):
        folders = [k for k in current_dir if isinstance(current_dir[k], dict) and "content" not in current_dir[k]]
        files = [k for k in current_dir if isinstance(current_dir[k], dict) and "content" in current_dir[k]]

        cols = st.columns([4, 1])
        with cols[0]:
            st.markdown(f"<h4 style='line-height: 2.5;'>🗂️ Path: /{'/'.join(st.session_state.current_path[1:])}</h4>", unsafe_allow_html=True)
        with cols[1]:
            if len(st.session_state.current_path) > 1:
                st.markdown("<div style='margin-top: 14px;'>", unsafe_allow_html=True)
                if st.button("⬅️ Go Back", key="go_back_btn"):
                    st.session_state.current_path.pop()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get("clipboard"):
            if st.button("📥 Paste Here", key="paste_here", use_container_width=True):
                name = st.session_state.clipboard_path
                if name in current_dir:
                    st.warning("A file with the same name already exists here.")
                else:
                    if st.session_state.clipboard_move:
                        current_dir[name] = st.session_state.clipboard
                        if "clipboard_origin" in st.session_state:
                            remove_file_by_path(st.session_state.fs, st.session_state.clipboard_origin)
                        st.session_state.clipboard_move = False
                        st.success(f"Moved '{name}' here.")
                    else:
                        size = st.session_state.clipboard["size"]
                        new_blocks = allocate_contiguous_blocks(size)
                        if new_blocks:
                            new_file = {
                                "type": st.session_state.clipboard["type"],
                                "content": st.session_state.clipboard["content"],
                                "mime": st.session_state.clipboard.get("mime", ""),
                                "size": size,
                                "blocks": new_blocks
                            }
                            current_dir[name] = new_file
                            st.success(f"Copied '{name}' here.")
                        else:
                            st.error("Not enough contiguous space to copy the file.")
                    st.session_state.clipboard = None
                    save_fs_to_db(st.session_state.username)
                    st.rerun()

        for folder in folders:
            with st.expander(f"📁 {folder}"):
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button(f"📂 Open {folder}", key=f"open_{folder}", use_container_width=True):
                        st.session_state.current_path.append(folder)
                        st.rerun()
                with col2:
                    if st.button(f"🗑️ Delete {folder}", key=f"del_{folder}", use_container_width=True):
                        if current_dir[folder]:
                            st.warning(f"Folder '{folder}' is not empty.")
                        else:
                            del current_dir[folder]
                            save_fs_to_db(st.session_state.username)
                            st.success(f"Folder '{folder}' deleted.")
                            st.rerun()

        for file in files:
            file_data = current_dir[file]
            size_mb = round(file_data['size'] / (1024 * 1024), 2)
            blocks_str = f"📦 Blocks: {file_data['blocks']}"
            st.markdown(
                f"### 📄 **{file}** ({size_mb} MB) &nbsp;&nbsp;&nbsp; <span style='font-size: 0.9em; color: gray;'>{blocks_str}</span>",
                unsafe_allow_html=True
            )

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                if st.button("📂 Move", use_container_width=True, key=f"move_{file}"):
                    st.session_state.clipboard = file_data
                    st.session_state.clipboard_path = file
                    st.session_state.clipboard_move = True
                    st.session_state.clipboard_origin = st.session_state.current_path + [file]
                    st.success(f"Ready to move '{file}'")

            with col2:
                if st.button("📋 Copy", use_container_width=True, key=f"copy_{file}"):
                    st.session_state.clipboard = file_data
                    st.session_state.clipboard_path = file
                    st.session_state.clipboard_move = False
                    st.success(f"Copied '{file}'")

            with col3:
                if file_data['type'] == "text":
                    st.download_button("⬇️ Download", file_data['content'], file_name=f"{file}.txt", mime="text/plain", use_container_width=True, key=f"dl_{file}")
                elif file_data['type'] == "binary":
                    try:
                        decoded = decode_string(file_data["content"])
                        mime = file_data.get("mime", "application/octet-stream")
                        st.download_button("⬇️ Download", decoded, file_name=file, mime=mime, use_container_width=True, key=f"dl_{file}")
                    except:
                        st.warning("⚠️ Unable to decode or download.")

            with col4:
                if st.button("🗑️ Delete", use_container_width=True, key=f"delete_{file}"):
                    deallocate_blocks(file_data['blocks'])
                    del current_dir[file]
                    save_fs_to_db(st.session_state.username)
                    st.rerun()

            with col5:
                rename_key = f"rename_{file}"
                if st.button("✏️ Rename", use_container_width=True, key=rename_key):
                    st.session_state["rename_file"] = file

            if st.session_state.get("rename_file") == file:
                new_name = st.text_input("Enter new name", value=file, key=f"new_name_{file}")
                
                cols_btn = st.columns([1, 1])
                with cols_btn[0]:
                    if st.button("✅ Confirm Rename", key=f"confirm_rename_{file}", use_container_width=True):
                        if new_name == file:
                            st.info("Filename unchanged.")
                        elif new_name in current_dir:
                            st.error("A file or folder with that name already exists.")
                        else:
                            current_dir[new_name] = current_dir.pop(file)
                            st.session_state.pop("rename_file")
                            save_fs_to_db(st.session_state.username)
                            st.success(f"Renamed '{file}' to '{new_name}'")
                            st.rerun()
                with cols_btn[1]:
                    if st.button("❌ Cancel", key=f"cancel_rename_{file}", use_container_width=True):
                        st.session_state.pop("rename_file")
                        st.rerun()

            # Optional preview
            if file_data['type'] == "text":
                st.code(file_data['content'])
            elif file_data['type'] == "binary":
                mime = file_data.get("mime", "")
                try:
                    content = decode_string(file_data["content"])
                except:
                    content = None
                if mime.startswith("image/"):
                    with st.expander("🖼️ View Image"):
                        if content:
                            st.image(content)
                        else:
                            st.warning("Could not load image content.")
                elif mime == "application/pdf":
                    st.info("PDF file ready for download.")
                else:
                    st.info("No preview available for this file type.")

    def create_folder_or_file(current_dir):
        st.markdown("### ➕ Create New")
        cols = st.columns([3, 2])
        with cols[0]:
            name = st.text_area("Name", placeholder="Enter file or folder name", height=68, key="create_name")
        with cols[1]:
            ftype = st.radio("Type", ["Folder", "Text File", "Upload File"], key="create_type")

        content = ""
        upload = None
        if ftype == "Text File":
            content = st.text_area("File content", key="create_text")
        elif ftype == "Upload File":
            upload = st.file_uploader("Upload any file", type=None, key="create_upload")

        if st.button("Create", use_container_width=True, key="create_btn"):
            if name in current_dir:
                st.error("Name already exists.")
            else:
                if ftype == "Folder":
                    current_dir[name] = {}
                    save_fs_to_db(st.session_state.username)
                    st.rerun()
                elif ftype == "Text File":
                    size = len(content.encode("utf-8"))
                    blocks = allocate_contiguous_blocks(size)
                    if blocks:
                        current_dir[name] = {
                            "type": "text",
                            "content": content,
                            "size": size,
                            "blocks": blocks
                        }
                        save_fs_to_db(st.session_state.username)
                        st.success(f"Text file '{name}' created.")
                        st.rerun()
                    else:
                        st.error("\U0001F6AB Not enough contiguous blocks. Out of space.")
                elif ftype == "Upload File" and upload is not None:
                    file_bytes = upload.read()
                    size = len(file_bytes)
                    blocks = allocate_contiguous_blocks(size)
                    if blocks:
                        current_dir[upload.name] = {
                            "type": "binary",
                            "mime": upload.type,
                            "content": encode_bytes(file_bytes),
                            "size": size,
                            "blocks": blocks
                        }
                        save_fs_to_db(st.session_state.username)
                        st.success(f"Uploaded '{upload.name}' ({upload.type}, {size / (1024 * 1024):.2f} MB)")
                        st.rerun()
                    else:
                        st.error("\U0001F6AB Not enough contiguous blocks. Out of space.")
    
    c1, c2 = st.columns([4, 1])

    with c1:
        st.markdown("### 🔍 Search Files")
        query = st.text_input("Enter filename to search (partial names allowed)")

    with c2:
        st.markdown("<div style='padding-top: 5.55rem'></div>", unsafe_allow_html=True)
        st.session_state.allocation_strategy = st.selectbox(
            label=" ",
            options=["First-Fit", "Best-Fit"],
            index=0 if st.session_state.allocation_strategy == "First-Fit" else 1,
            label_visibility="collapsed"
        )

    if query:
        results = search_files(query)
        if results:
            st.markdown("#### 📄 Search Results")
            for name, path, data in results:
                st.write(f"**{name}** in `{path}` ({round(data['size'] / (1024 * 1024), 2)} MB)")
                if data['type'] == "text":
                    st.code(data["content"])
                elif data['type'] == "binary":
                    mime = data.get("mime", "")
                    try:
                        content = decode_string(data["content"])
                    except:
                        st.warning(f"Error decoding content for {name}")
                        continue

                    if mime.startswith("image/"):
                        st.image(content)
                    elif mime == "application/pdf":
                        st.download_button("Download PDF", content, file_name=name, mime=mime)
                    else:
                        st.download_button("Download File", content, file_name=name, mime=mime)
                        st.info("No preview available for this file type.")
        else:
            st.warning("No files found.")

    render_disk()
        
    curr_dir = get_current_dir()
    render_directory(curr_dir)
    create_folder_or_file(curr_dir)

def tm_page():
    if st.button("\U0001F519 Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    if "tasks" not in st.session_state:
        st.session_state.tasks = []
    if "running" not in st.session_state:
        st.session_state.running = False
    if "current_task_id" not in st.session_state:
        st.session_state.current_task_id = None
    if "last_update" not in st.session_state:
        st.session_state.last_update = time.time()
    if "algorithm" not in st.session_state:
        st.session_state.algorithm = "FCFS"
    if "time_quantum" not in st.session_state:
        st.session_state.time_quantum = 2
    if "rr_counter" not in st.session_state:
        st.session_state.rr_counter = 0
    if "gantt_log" not in st.session_state:
        st.session_state.gantt_log = []
    if "start_reference_time" not in st.session_state:
        st.session_state.start_reference_time = None
    if "sim_time" not in st.session_state:
        st.session_state.sim_time = 0
    if "pending_next_task_id" not in st.session_state:
        st.session_state.pending_next_task_id = None
    if "defer_next_tick" not in st.session_state:
        st.session_state.defer_next_tick = False
    if "cpu_active_time" not in st.session_state:
        st.session_state.cpu_active_time = 0

    # --- Layout Split ---
    left, right = st.columns(2)

    # --- Task Scheduler Section ---
    with left:
        st.markdown("<h2 style='text-align: center;'>Task Scheduler</h3>", unsafe_allow_html=True)
        st.session_state.algorithm = st.selectbox("Scheduling Algorithm", ["FCFS", "SJF", "Priority", "Round Robin"])
        if st.session_state.algorithm == "Round Robin":
            st.session_state.time_quantum = st.number_input("Time Quantum", min_value=1, value=2)

        with st.form("add_task_form"):
            name = st.text_input("Task Name", f"Task {len(st.session_state.tasks)+1}")
            burst = st.number_input("Burst Time", min_value=1, value=5)
            priority = st.number_input("Priority (lower = higher)", min_value=1, value=1)
            submitted = st.form_submit_button("➕ Add Task", use_container_width=True)
            if submitted:
                now = st.session_state.sim_time
                st.session_state.tasks.append({
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "burst": burst,
                    "remaining": burst,
                    "priority": priority,
                    "state": "Waiting",
                    "start_time": None,
                    "end_time": None,
                    "arrival_time": now,
                    "memory": random.randint(5, 25)
                })

        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶️ Start", use_container_width=True):
                if st.session_state.tasks:
                    st.session_state.running = True
                    st.session_state.rr_counter = 0
                    st.session_state.sim_time = 0
                    st.session_state.cpu_active_time = 0
                    st.session_state.defer_next_tick = False
                    st.session_state.start_reference_time = min(t["arrival_time"] for t in st.session_state.tasks)

                    if st.session_state.algorithm == "SJF":
                        st.session_state.tasks.sort(key=lambda x: x["burst"])
                    elif st.session_state.algorithm == "Priority":
                        st.session_state.tasks.sort(key=lambda x: x["priority"])
                    elif st.session_state.algorithm == "FCFS":
                        st.session_state.tasks.sort(key=lambda x: x["arrival_time"])

                    for t in st.session_state.tasks:
                        if t["state"] == "Waiting":
                            t["state"] = "Running"
                            t["start_time"] = st.session_state.sim_time
                            st.session_state.current_task_id = t["id"]
                            break
                    st.rerun()

        with c2:
            if st.button("🔄 Reset", use_container_width=True):
                for key in [
                    "tasks", "running", "current_task_id", "last_update", "algorithm",
                    "time_quantum", "rr_counter", "gantt_log", "start_reference_time",
                    "sim_time", "pending_next_task_id", "defer_next_tick", "cpu_active_time"
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    # --- Task Manager Section ---
    with right:
        st.markdown("<h2 style='text-align: center;'>Task Manager</h3>", unsafe_allow_html=True)
        for t in st.session_state.tasks.copy():
            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(
                    f"**{t['name']}** — Status: `{t['state']}` — ⏳ Remaining: `{t['remaining']}s` — "
                    f"💥 Burst: `{t['burst']}s` — 🔹 Priority: `{t['priority']}`"
                )
                st.progress((t['burst'] - t['remaining']) / t['burst'] if t['burst'] > 0 else 1.0)
            with col2:
                if st.button("❌ Kill", key=f"kill_{t['id']}"):
                    if t["id"] == st.session_state.current_task_id:
                        st.session_state.running = False
                        st.session_state.current_task_id = None
                    st.session_state.tasks.remove(t)
                    st.rerun()

    # --- CPU Execution Logic ---
    if st.session_state.running:
        if st.session_state.defer_next_tick:
            st.session_state.defer_next_tick = False
            st.session_state.sim_time += 1
            st.rerun()

        if st.session_state.pending_next_task_id:
            pending_task = next(t for t in st.session_state.tasks if t["id"] == st.session_state.pending_next_task_id)
            if pending_task["state"] == "Waiting" and pending_task["arrival_time"] <= st.session_state.sim_time:
                pending_task["state"] = "Running"
                pending_task["start_time"] = st.session_state.sim_time
                st.session_state.current_task_id = pending_task["id"]
            st.session_state.pending_next_task_id = None

        current_task = next((t for t in st.session_state.tasks if t["id"] == st.session_state.current_task_id), None)

        if current_task and current_task["state"] == "Running":
            current_task["remaining"] -= 1
            st.session_state.rr_counter += 1
            st.session_state.cpu_active_time += 1

            if current_task["remaining"] <= 0:
                current_task["state"] = "Finished"
                current_task["end_time"] = st.session_state.sim_time + 1
                st.session_state.gantt_log.append({
                    "Task": current_task["name"],
                    "Start": current_task["start_time"],
                    "Finish": current_task["end_time"]
                })
                st.session_state.rr_counter = 0
                st.session_state.current_task_id = None

                next_task = None
                if st.session_state.algorithm in ["SJF", "Priority"]:
                    queue = [t for t in st.session_state.tasks if t["state"] == "Waiting"]
                    if st.session_state.algorithm == "SJF":
                        queue.sort(key=lambda x: x["burst"])
                    else:
                        queue.sort(key=lambda x: x["priority"])
                    next_task = queue[0] if queue else None
                else:
                    for t in st.session_state.tasks:
                        if t["state"] == "Waiting":
                            next_task = t
                            break

                if next_task:
                    st.session_state.pending_next_task_id = next_task["id"]
                else:
                    st.session_state.running = False

                st.session_state.defer_next_tick = True
                st.rerun()

            elif st.session_state.algorithm == "Round Robin" and st.session_state.rr_counter >= st.session_state.time_quantum:
                current_task["state"] = "Waiting"
                st.session_state.rr_counter = 0

                all_tasks = st.session_state.tasks
                current_idx = all_tasks.index(current_task)
                for offset in range(1, len(all_tasks)):
                    next_idx = (current_idx + offset) % len(all_tasks)
                    if all_tasks[next_idx]["state"] == "Waiting":
                        all_tasks[next_idx]["state"] = "Running"
                        all_tasks[next_idx]["start_time"] = st.session_state.sim_time
                        st.session_state.current_task_id = all_tasks[next_idx]["id"]
                        break
                else:
                    st.session_state.running = False
                    st.session_state.current_task_id = None

                st.rerun()

    # Resource Utilization 
    if st.session_state.sim_time > 0:
        cpu_util = st.session_state.cpu_active_time / st.session_state.sim_time
        if not st.session_state.running:
            cpu_util = 0.0
        cpu_util = min(cpu_util, 1.0)
        st.markdown(f"### 🖥️ CPU Utilization: {cpu_util * 100:.1f}%")
        st.progress(cpu_util)

        mem_total = sum(t["memory"] for t in st.session_state.tasks)
        mem_used = sum(t["memory"] for t in st.session_state.tasks if t["state"] == "Running")
        mem_util = mem_used / mem_total if mem_total > 0 else 0
        mem_util = min(mem_util, 1.0)
        st.markdown(f"### 📦 Memory Utilization: {mem_util * 100:.1f}%")
        st.progress(mem_util)

    # Task Execution Summary
    summary_rows = []
    reference = (
        st.session_state.get("start_reference_time") or
        (min(t["arrival_time"] for t in st.session_state.tasks) if st.session_state.tasks else 0)
    )

    for t in st.session_state.tasks:
        if t["state"] == "Finished":
            arrival_time = int(t["arrival_time"] - reference)
            start_time = int(t["start_time"] - reference) if t["start_time"] is not None else "-"
            waiting_time = start_time - arrival_time if isinstance(start_time, int) else "-"
            completion_time = int(t["end_time"] - reference) if t["end_time"] is not None else "-"
            turnaround_time = completion_time - arrival_time if isinstance(completion_time, int) else "-"

            summary_rows.append({
                "PID": t["name"],
                "Arrival Time (s)": arrival_time,
                "Burst Time": t["burst"],
                "Start Time (s)": start_time,
                "Completion Time (s)": completion_time,
                "Waiting Time (s)": waiting_time,
                "Turnaround Time (s)": turnaround_time
            })

    if summary_rows and not st.session_state.running:
        df = pd.DataFrame(summary_rows)
        st.markdown("### 📊 Task Execution Summary")
        st.dataframe(df, use_container_width=True)

    if st.session_state.running:
        time.sleep(0.5)
        st.session_state.sim_time += 1
        st.rerun()

def cbot():
    if st.button("\U0001F519 Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()
        
    GROQ_API_KEY = st.secrets["groq_api_key"]
    MODEL = "llama3-8b-8192"         

    st.title("Ask me anything!")
    st.caption(f"Running on Groq API (`{MODEL}` model)")

    # === Initialize Chat History ===
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # === Display Past Messages ===
    for role, content in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(content)

    # === Chat Input ===
    prompt = st.chat_input("Ask something...")

    if prompt:
        st.session_state.chat_history.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply_box = st.empty()
                reply = ""

                # Format messages in OpenAI format
                messages = [
                    {"role": role, "content": content}
                    for role, content in st.session_state.chat_history
                ]

                # Prepare Groq request
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "stream": False
                }

                try:
                    response = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    response.raise_for_status()

                    content = response.json()["choices"][0]["message"]["content"]

                    # Typing effect
                    for token in content:
                        reply += token
                        reply_box.markdown(reply + "▌")
                        time.sleep(0.01)

                    reply_box.markdown(reply)

                except Exception as e:
                    reply = f"❌ Error: {e}"
                    reply_box.markdown(reply)

                st.session_state.chat_history.append(("assistant", reply))

def game_page():
    if st.button("\U0001F519 Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    if "score" not in st.session_state:
        st.session_state.score = 0
    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "dot_position" not in st.session_state:
        st.session_state.dot_position = (0, 0)
    if "game_active" not in st.session_state:
        st.session_state.game_active = False
    if "duration" not in st.session_state:
        st.session_state.duration = 30
    if "dot_type" not in st.session_state:
        st.session_state.dot_type = "normal"
    if "last_dot_time" not in st.session_state:
        st.session_state.last_dot_time = 0

    def spawn_dot():
        st.session_state.dot_position = (random.randint(0, 4), random.randint(0, 4))
        st.session_state.dot_type = "bomb" if random.random() < 0.3 else "normal"
        st.session_state.last_dot_time = time.time()

    st.markdown("<h1 style='text-align: center; background-color: red; border-radius: 1rem; color: white; margin-bottom: 0.7rem;'>Click the Dot</h1>", unsafe_allow_html=True)
    
    with st.expander("ℹ️ How to Play / Game Mechanics", expanded=False):
        st.markdown("""
        - **Objective:** Click the red dot (🔴) as fast as you can to score points!
        - **Bombs:** Be careful — if you click a black dot (⚫), you lose 1 point.
        - **End of Game:** When time runs out, your final score is shown.
        """)

    if not st.session_state.game_active:
        st.session_state.duration = st.selectbox("🕒 Select Time Limit (seconds)", [15, 30, 60], index=1)
        if st.button("▶️ Start Game", use_container_width=True):
            st.session_state.score = 0
            st.session_state.start_time = time.time()
            st.session_state.game_active = True
            spawn_dot()
            st.rerun()
    else:
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.duration - elapsed

        if remaining <= 0:
            st.success(f"⏱️ Time's up! Your score: {st.session_state.score}")
            if st.button("🔁 Play Again", use_container_width=True):
                st.session_state.game_active = False
                st.rerun()
        else:
            st.markdown(f"**Time Left:** `{int(remaining)}` seconds")
            st.markdown(f"**Score:** `{st.session_state.score}`")

            grid = [st.columns(5) for _ in range(5)]
            dot_x, dot_y = st.session_state.dot_position

            for i in range(5):
                for j in range(5):
                    if (i, j) == (dot_x, dot_y):
                        label = "🔴" if st.session_state.dot_type == "normal" else "⚫"
                        if grid[i][j].button(label, key=f"dot_{i}_{j}"):
                            if st.session_state.dot_type == "normal":
                                st.session_state.score += 1
                            else:
                                st.session_state.score = max(0, st.session_state.score - 1)
                            spawn_dot()
                            st.rerun()
                    else:
                        grid[i][j].write("")

            now = time.time()
            spawn_delay = 0.7 if remaining <= 10 else 1 if remaining <= 20 else 2
            if now - st.session_state.last_dot_time > spawn_delay:
                spawn_dot()
                st.rerun()

            time.sleep(1)
            st.rerun()

def settings_page():
    if st.button("🔙 Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    st.markdown("### 🖥️ System Information")
    col1, col2 = st.columns(2)

    if "disk" not in st.session_state:
        user_data = get_user(st.session_state.username) if "username" in st.session_state else None
        if user_data and "disk_json" in user_data and user_data["disk_json"]:
            try:
                st.session_state.disk = json.loads(user_data["disk_json"])
            except:
                st.session_state.disk = [None] * DISK_SIZE
        else:
            st.session_state.disk = [None] * DISK_SIZE

    with col1:
        st.markdown(f"**Username:** `{st.session_state.get('username', 'N/A')}`")

        # Toggleable password
        if "show_password" not in st.session_state:
            st.session_state.show_password = False

        st.session_state.show_password = st.toggle("Show Password", key="toggle_pw")
        pw_display = st.session_state.get("plain_password", "******") if st.session_state.show_password else "******"
        st.markdown(f"**Password:** `{pw_display}`")

    with col2:
        st.markdown(f"**Streamlit Version:** `{st.__version__}`")
        device_name = socket.gethostname()
        st.markdown(f"**Device Name:** `{device_name}`")

        if "disk" in st.session_state:
            used_blocks = sum(1 for b in st.session_state.disk if b is not None)
            total_blocks = len(st.session_state.disk)
            used_mb = used_blocks * (BLOCK_SIZE / (1024 * 1024))
            total_mb = total_blocks * (BLOCK_SIZE / (1024 * 1024))
            st.markdown(f"**Memory Usage:** `{used_mb:.2f} / {total_mb:.0f} MB`")
        else:
            st.markdown("**Memory Usage:** `N/A`")

    st.markdown("---")

    if st.button("🚪 Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key != "loaded":
                del st.session_state[key]
        st.session_state.loaded = False
        st.rerun()

# ------------------------ Login UI ------------------------ #
def login_ui():
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "Login"

    with stylable_container(
        key="login_container",
        css_styles="""
            border-radius: 16px;
            max-width: 700px;
            margin: auto;
            padding: 2rem;
            background-color: #ffffff;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        """
    ):
        def get_base64_image(path):
            with open(path, "rb") as f:
                data = f.read()
            return base64.b64encode(data).decode()

        base64_logo = get_base64_image("logo.png")

        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 1.5rem;">
                <img src="data:image/png;base64,{base64_logo}" width="500" style="border-radius: 12px;" />
            </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔐 Login", use_container_width=True):
                st.session_state.auth_mode = "Login"
        with col2:
            if st.button("📝 Sign Up", use_container_width=True):
                st.session_state.auth_mode = "Sign Up"
        with col3:
            if st.button("🔄 Forgot Password", use_container_width=True):
                st.session_state.auth_mode = "Reset"

        if st.session_state.auth_mode in ["Login", "Sign Up"]:
            with st.form("auth_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")

                button_text = "Create Account" if st.session_state.auth_mode == "Sign Up" else "Login"
                submitted = st.form_submit_button(button_text, use_container_width=True)

                if submitted:
                    if st.session_state.auth_mode == "Sign Up":
                        if get_user(username):
                            st.warning("⚠️ Username already exists.")
                        elif not is_strong_password(password):
                            st.error("Password must be at least 8 characters with uppercase, lowercase, number, and symbol.")
                        else:
                            add_user(username, password)
                            st.success("✅ Account created successfully!")
                            st.session_state.auth_mode = "Login"
                    else:
                        user = get_user(username)
                        if not user:
                            st.error("❌ Username not found.")
                        elif not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                            st.error("🔐 Incorrect password.")
                        else:
                            st.success(f"🎉 Welcome, {username}!")
                            time.sleep(0.5)
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.session_state.page = "home"
                            st.session_state.plain_password = password
                            st.rerun()

        elif st.session_state.auth_mode == "Reset":
            with st.form("reset_form", clear_on_submit=False):
                st.markdown("### 🔄 Reset Password")
                username = st.text_input("Username for Reset")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                reset_submit = st.form_submit_button("Reset Password", use_container_width=True)

                if reset_submit:
                    user = get_user(username)
                    if not user:
                        st.error("❌ Username not found.")
                    elif new_password != confirm_password:
                        st.error("❌ Passwords do not match.")
                    elif not is_strong_password(new_password):
                        st.warning("⚠️ Password must include uppercase, lowercase, number, symbol, and be 8+ characters.")
                    else:
                        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                        update_user_password(username, new_hash)
                        st.success("✅ Password updated! You can now log in.")
                        st.session_state.auth_mode = "Login"

if __name__ == "__main__":
    st.set_page_config(page_title="DAMPos", page_icon="icon.png", initial_sidebar_state="collapsed")
    set_styles()

    if "loaded" not in st.session_state:
        startup_screen()
        st.session_state.loaded = True
        st.rerun()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "page" not in st.session_state:
        st.session_state.page = "home"

    if st.session_state.authenticated:
        if st.session_state.page == "home":
            home_page()
        elif st.session_state.page == "fs":
            file_system_page()
        elif st.session_state.page == 'tm':
            tm_page()
        elif st.session_state.page == "cbot":
            cbot()
        elif st.session_state.page == "game":
            game_page()
        elif st.session_state.page == "settings":
            settings_page()
    else:
        login_ui()
