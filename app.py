import streamlit as st
from streamlit_lottie import st_lottie
from streamlit_extras.stylable_container import stylable_container
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import deque
from platform import python_version
import zlib
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

# ------------------------ Process Management ------------------------ #
class Process:
    def __init__(self, id, name, arrival_time, burst_time, priority=None, addition_order=0): 
        self.id = id
        self.name = name
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.priority = priority
        self.addition_order = addition_order 

        self.remaining_time = burst_time
        self.state = "Waiting" # "Waiting", "Running", "Finished"
        self.start_execution_time = None # The very first time it gets CPU
        self.last_run_time = None # The last tick it executed
        self.completion_time = None

    def calculate_metrics(self):
        # Only calculate for finished processes
        if self.state != "Finished":
            return {}

        turnaround_time = self.completion_time - self.arrival_time if self.completion_time is not None else None
        
        # Waiting time = Turnaround Time - Burst Time
        waiting_time = turnaround_time - self.burst_time if turnaround_time is not None else None
        
        response_time = self.start_execution_time - self.arrival_time if self.start_execution_time is not None else None
        
        return {
            "PID": self.name,
            "Arrival Time (s)": self.arrival_time,
            "Burst Time": self.burst_time,
            "Priority": self.priority if self.priority is not None else "-",
            "Start Time (s)": self.start_execution_time,
            "Completion Time (s)": self.completion_time,
            "Turnaround Time (s)": turnaround_time,
            "Waiting Time (s)": waiting_time,
            "Response Time (s)": response_time
        }

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

def compress_json(obj):
    return base64.b64encode(zlib.compress(json.dumps(obj).encode())).decode()

def decompress_json(s):
    return json.loads(zlib.decompress(base64.b64decode(s.encode())).decode())

def save_fs_to_db(username):
    fs_compressed = compress_json(st.session_state.fs)
    disk_compressed = compress_json(st.session_state.disk)

    supabase.table("users").update({
        "fs_json": fs_compressed,
        "disk_json": disk_compressed
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
    time.sleep(6)

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
                    width: 100% !important;
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
                loaded_disk = decompress_json(user_data["disk_json"])
                if isinstance(loaded_disk, list) and len(loaded_disk) == DISK_SIZE:
                    st.session_state.disk = loaded_disk
                else:
                    st.session_state.disk = [None] * DISK_SIZE
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
            try:
                st.session_state.fs = decompress_json(user_data["fs_json"]) 
            except:
                st.session_state.fs = {"root": {}}
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
            try:
                if isinstance(value, dict):
                    if "content" in value:
                        if name_query.lower() in key.lower():
                            results.append((key, current_path, value))
                    else:
                        results.extend(search_files(name_query, value, current_path))
            except Exception as e:
                st.warning(f"Skipped a file or folder due to an error: {e}")
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
            for idx, (name, path, data) in enumerate(results): 
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
                        st.download_button("Download PDF", content, file_name=name, mime=mime, key=f"dl_pdf_{idx}", use_container_width=True)
                    else:
                        st.download_button("Download File", content, file_name=name, mime=mime, key=f"dl_file_{idx}", use_container_width=True)
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

    # --- Session State Initialization ---
    if "processes" not in st.session_state:
        st.session_state.processes = []
    if "running" not in st.session_state:
        st.session_state.running = False
    if "current_process_id" not in st.session_state:
        st.session_state.current_process_id = None
    if "last_tick_time" not in st.session_state:
        st.session_state.last_tick_time = time.time()
    if "algorithm" not in st.session_state:
        st.session_state.algorithm = "FCFS"
    if "time_quantum" not in st.session_state:
        st.session_state.time_quantum = 2
    if "rr_quantum_counter" not in st.session_state:
        st.session_state.rr_quantum_counter = 0
    if "gantt_raw_log" not in st.session_state: # Stores (Task Name, Start Time, End Time)
        st.session_state.gantt_raw_log = []
    if "sim_time" not in st.session_state:
        st.session_state.sim_time = 0
    if "cpu_active_time" not in st.session_state:
        st.session_state.cpu_active_time = 0
    if "ready_queue" not in st.session_state:
        st.session_state.ready_queue = deque()
    if "un_arrived_processes" not in st.session_state:
        st.session_state.un_arrived_processes = deque()
    if "completed_processes" not in st.session_state:
        st.session_state.completed_processes = []
    if "prev_executed_pid" not in st.session_state: # For Gantt chart consolidation
        st.session_state.prev_executed_pid = None


    # --- Task Scheduler Section (now entirely in sidebar) ---
    with st.sidebar: # This wraps the entire previous 'left' column content
        st.markdown("<h2 style='text-align: center;'>Task Scheduler</h3>", unsafe_allow_html=True)
        st.session_state.algorithm = st.selectbox("Scheduling Algorithm", ["FCFS", "SJF", "Priority", "Round Robin"])
        if st.session_state.algorithm == "Round Robin":
            st.session_state.time_quantum = st.number_input("Time Quantum", min_value=1, value=2, key="rr_quantum_input")

        with st.form("add_task_form"):
            name = st.text_input("Task Name", f"Task {len(st.session_state.processes)+1}")
            arrival = st.number_input("Arrival Time", min_value=0, value=0)
            burst = st.number_input("Burst Time", min_value=1, value=5)
            priority = st.number_input("Priority (lower = higher)", min_value=1, value=1)

            submitted = st.form_submit_button("➕ Add Task", use_container_width=True)
            if submitted:
                new_process = Process(
                    id=str(uuid.uuid4()),
                    name=name,
                    arrival_time=arrival,
                    burst_time=burst,
                    priority=priority,
                    addition_order=len(st.session_state.processes)
                )
                st.session_state.processes.append(new_process)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Start", use_container_width=True):
                if st.session_state.processes:
                    st.session_state.running = True
                    st.session_state.sim_time = 0
                    st.session_state.cpu_active_time = 0
                    st.session_state.rr_quantum_counter = 0
                    st.session_state.current_process_id = None
                    st.session_state.gantt_raw_log = []
                    st.session_state.ready_queue = deque()
                    st.session_state.completed_processes = []
                    st.session_state.prev_executed_pid = None

                    # Reset all processes to their initial state for a new run
                    for p in st.session_state.processes:
                        p.remaining_time = p.burst_time
                        p.state = "Waiting"
                        p.start_execution_time = None
                        p.last_run_time = None
                        p.completion_time = None
                    
                    # Initialize un_arrived_processes deque for use in scheduling loop
                    # Sort by arrival time (primary) then addition order (secondary for tie-breaking)
                    st.session_state.un_arrived_processes = deque(sorted(st.session_state.processes, key=lambda x: (x.arrival_time, x.addition_order)))

                    st.rerun()

        with c2:
            if st.button("Reset", use_container_width=True):
                for key in [
                    "processes", "running", "current_process_id", "last_tick_time", "algorithm",
                    "time_quantum", "rr_quantum_counter", "gantt_raw_log", "sim_time",
                    "cpu_active_time", "ready_queue", "un_arrived_processes", "completed_processes",
                    "prev_executed_pid"
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    # --- Main Content Area ---
    st.markdown("<h2 style='text-align: center;'>Task Manager</h2>", unsafe_allow_html=True)

    st.markdown("""
        <div style='display: flex; justify-content: center; margin-top: -1rem; margin-left: -1.5rem;'>
            <p style='font-size: 0.9em; color: gray;'>Task Scheduler is in the sidebar.</p>
        </div>
    """, unsafe_allow_html=True)

    for p in st.session_state.processes:
        col1, col2 = st.columns([6, 1])
        with col1:
            st.markdown(
                f"**{p.name}** — Status: `{p.state}` — ⏳ Remaining: `{p.remaining_time}s` — "
                f"💥 Burst: `{p.burst_time}s` — 🔹 Priority: `{p.priority}` — 🕰️ Arrival: `{p.arrival_time}s`"
            )
        with col2:
            if st.button("❌ Kill", key=f"kill_{p.id}"):
                # Mark as finished/killed
                if p.state != "Finished":
                    p.state = "Finished"
                    p.remaining_time = 0
                    p.completion_time = st.session_state.sim_time # Killed at current sim_time
                    
                    # Log the current segment if it was running
                    if p.id == st.session_state.current_process_id and p.start_execution_time is not None and p.last_run_time is not None:
                        # Adjust the last gantt segment to end at current sim_time
                        if st.session_state.gantt_raw_log and st.session_state.gantt_raw_log[-1][0] == p.name:
                            st.session_state.gantt_raw_log[-1] = (p.name, st.session_state.gantt_raw_log[-1][1], st.session_state.sim_time)


                    if p not in st.session_state.completed_processes:
                        st.session_state.completed_processes.append(p)
                
                # Remove from other queues if still present
                st.session_state.ready_queue = deque([task for task in st.session_state.ready_queue if task.id != p.id])
                st.session_state.un_arrived_processes = deque([task for task in st.session_state.un_arrived_processes if task.id != p.id])

                if p.id == st.session_state.current_process_id:
                    st.session_state.current_process_id = None # Clear current running process
                    st.session_state.rr_quantum_counter = 0 # Reset for next
                    st.session_state.prev_executed_pid = None # Break Gantt consolidation

                # If all tasks are now finished (or killed) stop the simulation
                if len(st.session_state.completed_processes) == len(st.session_state.processes):
                    st.session_state.running = False
                
                st.rerun()
        st.progress((p.burst_time - p.remaining_time) / p.burst_time if p.burst_time > 0 else 1.0)

    # --- CPU Execution Logic (scheduler_tick function) ---
    def scheduler_tick():
        # 1. Add newly arrived processes to ready queue
        while st.session_state.un_arrived_processes and \
            st.session_state.un_arrived_processes[0].arrival_time <= st.session_state.sim_time:
            p = st.session_state.un_arrived_processes.popleft()
            if p.state != "Finished": # Only add if not already killed
                st.session_state.ready_queue.append(p)

        # 2. Determine current running process and potential next process
        current_process = next((p for p in st.session_state.processes if p.id == st.session_state.current_process_id), None)
        
        next_process_to_run = None

        # Handle process selection based on algorithm
        if st.session_state.algorithm == "FCFS":
            # FCFS: Sort by arrival, then by addition_order (for tie-breaking)
            st.session_state.ready_queue = deque(sorted(st.session_state.ready_queue, key=lambda x: (x.arrival_time, x.addition_order)))
            if st.session_state.ready_queue:
                next_process_to_run = st.session_state.ready_queue[0] # FCFS picks from front
            
            # In FCFS, once a process starts, it runs to completion (non-preemptive)
            if current_process and current_process.state == "Running" and current_process.remaining_time > 0:
                next_process_to_run = current_process # Continue running current process


        elif st.session_state.algorithm == "SJF": # Non-Preemptive SJF
            # Consider processes that are "Waiting" and have arrived
            available_processes_in_queue = [p for p in st.session_state.ready_queue if p.state == "Waiting"]
            # Sort by burst_time, then arrival_time, then addition_order for tie-breaking
            available_processes_in_queue.sort(key=lambda x: (x.burst_time, x.arrival_time, x.addition_order))
            
            if available_processes_in_queue:
                next_process_to_run = available_processes_in_queue[0]
            
            # If a process is currently running and hasn't finished, it continues (non-preemptive)
            if current_process and current_process.state == "Running" and current_process.remaining_time > 0:
                next_process_to_run = current_process


        elif st.session_state.algorithm == "Priority": # Non-Preemptive Priority
            available_processes_in_queue = [p for p in st.session_state.ready_queue if p.state == "Waiting"]
            # Sort by priority (lower number = higher priority), then arrival_time, then addition_order
            available_processes_in_queue.sort(key=lambda x: (x.priority, x.arrival_time, x.addition_order))
            
            if available_processes_in_queue:
                next_process_to_run = available_processes_in_queue[0]

            # If a process is currently running and hasn't finished, it continues (non-preemptive)
            if current_process and current_process.state == "Running" and current_process.remaining_time > 0:
                next_process_to_run = current_process


        elif st.session_state.algorithm == "Round Robin":
            # Round Robin logic. `ready_queue` is managed as a true circular queue.
            # If current_process is running and not finished and its quantum hasn't expired, it stays.
            if current_process and current_process.state == "Running" and current_process.remaining_time > 0:
                next_process_to_run = current_process
            else: # Quantum expired, or current_process finished, or nothing was running
                if st.session_state.ready_queue:
                    next_process_to_run = st.session_state.ready_queue[0]


        # 3. Handle state transitions (running a new process, or CPU idle)
        if next_process_to_run and next_process_to_run.state != "Finished":
            if current_process is None or current_process.id != next_process_to_run.id:
                # Context switch: a new process is chosen
                if current_process and current_process.state == "Running": # Preempt the old process
                    current_process.state = "Waiting"
                    # Log the segment for the preempted task up to current_time
                    # This should be implicitly handled by `gantt_raw_log` consolidation logic

                next_process_to_run.state = "Running"
                if next_process_to_run.start_execution_time is None:
                    next_process_to_run.start_execution_time = st.session_state.sim_time
                
                st.session_state.current_process_id = next_process_to_run.id
                st.session_state.rr_quantum_counter = 0 # Reset quantum for new process
                st.session_state.prev_executed_pid = None # Break Gantt consolidation

                # If the process was picked from the front of the ready queue (FCFS, SJF, Priority)
                # or for RR when it's genuinely the next in the circular queue
                if next_process_to_run in st.session_state.ready_queue:
                    if st.session_state.algorithm != "Round Robin" or (st.session_state.algorithm == "Round Robin" and next_process_to_run == st.session_state.ready_queue[0]):
                        if st.session_state.ready_queue:
                            try:
                                st.session_state.ready_queue.remove(next_process_to_run)
                            except ValueError:
                                pass
        else: # No process selected to run (CPU idle or all processes finished)
            st.session_state.current_process_id = None
            st.session_state.prev_executed_pid = None # Break Gantt consolidation
            
            remaining_tasks = [p for p in st.session_state.processes if p.state != "Finished"]
            
            if not remaining_tasks: # All processes are done
                st.session_state.running = False
                return
            
            # If there are tasks but none are ready (CPU idle until next arrival)
            if not st.session_state.ready_queue and st.session_state.un_arrived_processes:
                st.session_state.sim_time = st.session_state.un_arrived_processes[0].arrival_time - 1 
                st.session_state.cpu_active_time = st.session_state.sim_time 

        # 4. Execute current process for 1 tick (if one is selected)
        current_process = next((p for p in st.session_state.processes if p.id == st.session_state.current_process_id), None)
        if current_process and current_process.state == "Running":
            current_process.remaining_time -= 1
            st.session_state.cpu_active_time += 1
            current_process.last_run_time = st.session_state.sim_time

            # Update Gantt log
            if st.session_state.gantt_raw_log and st.session_state.prev_executed_pid == current_process.id:
                last_entry = st.session_state.gantt_raw_log[-1]
                if last_entry[0] == current_process.name:
                    st.session_state.gantt_raw_log[-1] = (last_entry[0], last_entry[1], st.session_state.sim_time + 1)
                else:
                    st.session_state.gantt_raw_log.append((current_process.name, st.session_state.sim_time, st.session_state.sim_time + 1))
            else:
                st.session_state.gantt_raw_log.append((current_process.name, st.session_state.sim_time, st.session_state.sim_time + 1))
            st.session_state.prev_executed_pid = current_process.id 

            # 5. Handle completion or preemption (Round Robin quantum)
            if current_process.remaining_time <= 0:
                current_process.state = "Finished"
                current_process.completion_time = st.session_state.sim_time + 1 
                st.session_state.completed_processes.append(current_process)
                st.session_state.current_process_id = None 
                st.session_state.prev_executed_pid = None 

                if current_process in st.session_state.ready_queue:
                    st.session_state.ready_queue.remove(current_process)


            elif st.session_state.algorithm == "Round Robin":
                st.session_state.rr_quantum_counter += 1
                if st.session_state.rr_quantum_counter >= st.session_state.time_quantum:
                    current_process.state = "Waiting"
                    st.session_state.rr_quantum_counter = 0 
                    st.session_state.current_process_id = None 

                    if current_process.remaining_time > 0:
                        if current_process in st.session_state.ready_queue: 
                            st.session_state.ready_queue.remove(current_process)
                        st.session_state.ready_queue.append(current_process)
                    
                    st.session_state.prev_executed_pid = None 
        else: 
            st.session_state.prev_executed_pid = None 

        st.session_state.ready_queue = deque([
            p for p in st.session_state.ready_queue if p.state != "Finished"
        ])

    if st.session_state.running:
        time.sleep(0.5) 
        scheduler_tick()
        st.session_state.sim_time += 1
        st.rerun()

    st.markdown("---")
    st.markdown("<h2 style='text-align: center;'>System Metrics</h2>", unsafe_allow_html=True)

    finished_processes = [p for p in st.session_state.processes if p.state == "Finished"]
    df = None
    cpu_util = 0.0

    if st.session_state.sim_time > 0:
        cpu_util = st.session_state.cpu_active_time / st.session_state.sim_time

        top_col1, top_col2 = st.columns(2)

        with top_col1:
            st.subheader("System Time")
            st.markdown(f"**Current Simulation Time:** `{st.session_state.sim_time}s`")
            st.markdown(f"**Total CPU Active Time:** `{st.session_state.cpu_active_time}s`")

        with top_col2:
            st.subheader("Average Metrics")
            if finished_processes:
                summary_rows = [p.calculate_metrics() for p in finished_processes]
                df = pd.DataFrame(summary_rows)

                avg_turnaround_time = df["Turnaround Time (s)"].mean()
                avg_waiting_time = df["Waiting Time (s)"].mean()
                avg_response_time = df["Response Time (s)"].mean()

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Turnaround", f"{avg_turnaround_time:.2f}s")
                with col2:
                    st.metric("Waiting", f"{avg_waiting_time:.2f}s")
                with col3:
                    st.metric("Response", f"{avg_response_time:.2f}s")

        st.markdown(f"### 🖥️ CPU Utilization: {cpu_util * 100:.1f}%")
        st.progress(cpu_util)

        if df is not None:
            st.markdown("### 📊 Task Execution Summary")
            st.dataframe(df, use_container_width=True)

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

            # This ensures the app refreshes every second
            time.sleep(1)
            st.rerun()

def settings_page():
    if st.button("🔙 Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    st.markdown("### 🖥️ System Information")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
            <div style="text-align: justify; font-size: 0.95rem;">
            <strong>As part of their final requirement for CPEN95 - Operating Systems</strong>, the students were tasked with creating a mini operating system called <strong>DAMPos</strong> 
            (<em>Dizon, Alimpolos, Mojica, and Pangilinan’s Operating System</em>) that simulates core functionalities of real-world OS designs.<br><br>
            To accomplish this, the team used <strong>Python</strong> as the primary programming language, integrating various modules to build system-like components. 
            For the graphical user interface and to support web deployment, they utilized a Python framework called <strong>Streamlit</strong>, 
            which allowed for rapid prototyping and an interactive frontend.
            </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
            <div style="text-align: justify; font-size: 0.95rem;">
            <strong>Key Features Implemented:</strong>
            <ul style="padding-left: 1.2rem;">
                <li><strong>User Authentication System:</strong> Basic login simulation using username and password validation.</li>
                <li><strong>File Management System:</strong> Simulates file creation, deletion, and listing using <em>contiguous allocation</em> with a simple directory structure.</li>
                <li><strong>Memory Management:</strong> Models fixed-size memory blocks and supports basic allocation strategies like <em>First-Fit</em> and <em>Best-Fit</em>.</li>
                <li><strong>Process Scheduling:</strong> Emulates classic algorithms including <em>FCFS, SJF, Priority Scheduling</em>, and <em>Round Robin</em>, with customizable parameters such as arrival time, burst time, priority, and time quantum.</li>
            </ul>
            </div>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    if "disk" not in st.session_state:
        user_data = get_user(st.session_state.username) if "username" in st.session_state else None
        if user_data and "disk_json" in user_data and user_data["disk_json"]:
            try:
                st.session_state.disk = decompress_json(user_data["disk_json"])  
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
        st.markdown(f"**Python Version:** `{python_version()}`")
        st.markdown(f"**Streamlit Version:** `{st.__version__}`")

        # Memory usage
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

    st.markdown("""
        <style>
        .stButton > button {
            background-color: #3394ed !important;
            color: white !important;
            font-weight: bold !important;
            border-radius: 8px;
            padding: 0.5em 1em;
        }
        </style>
    """, unsafe_allow_html=True)

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
            if st.button("Login", use_container_width=True):
                st.session_state.auth_mode = "Login"
        with col2:
            if st.button("Sign Up", use_container_width=True):
                st.session_state.auth_mode = "Sign Up"
        with col3:
            if st.button("Forgot Password", use_container_width=True):
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
                username = st.text_input("Username for Reset")
                original_password = st.text_input("Original Password", type="password")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                reset_submit = st.form_submit_button("Reset Password", use_container_width=True)

                if reset_submit:
                    user = get_user(username)
                    if not user:
                        st.error("❌ Username not found.")
                    elif not bcrypt.checkpw(original_password.encode(), user["password_hash"].encode()):
                        st.error("❌ Original password is incorrect.")
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
