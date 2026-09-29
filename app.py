import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import quote_plus
import uuid
import hashlib
import secrets

# ============================================================
# GUIDE FLOW - MYSQL / AIVEN VERSION
# ============================================================
st.set_page_config(
    page_title="GuideFlow - Phân luồng hướng dẫn viên",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# AIVEN MYSQL
# Thông tin dưới đây lấy từ Aiven Connection Information.
# Khi đưa app lên GitHub công khai, NÊN chuyển các giá trị này
# sang Streamlit Secrets. App vẫn có fallback để chạy ngay.
# ============================================================
DEFAULT_DB = {
    "host": "mysql-29a6db25-tranthikimnguyet8-df0c.i.aivencloud.com",
    "port": 19586,
    "user": "avnadmin",
    "password": "AVNS_6y8qIYGcoOj22F0rJKB",
    "database": "defaultdb",
}

def get_db_config():
    try:
        sec = st.secrets.get("mysql", {})
        if sec:
            return {
                "host": sec.get("host", DEFAULT_DB["host"]),
                "port": int(sec.get("port", DEFAULT_DB["port"])),
                "user": sec.get("user", DEFAULT_DB["user"]),
                "password": sec.get("password", DEFAULT_DB["password"]),
                "database": sec.get("database", DEFAULT_DB["database"]),
                "ca": sec.get("ca", ""),
            }
    except Exception:
        pass

    return {**DEFAULT_DB, "ca": ""}

DB = get_db_config()

@st.cache_resource(show_spinner=False)
def get_engine():
    # Aiven yêu cầu SSL. Nếu có CA trong Secrets thì dùng CA để
    # xác thực chứng chỉ; nếu chưa có CA, kết nối vẫn được mã hóa.
    ssl_args = {"check_hostname": False}
    if DB.get("ca"):
        ssl_args["ca"] = DB["ca"]

    return create_engine(
        "mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4".format(
            user=quote_plus(DB["user"]),
            password=quote_plus(DB["password"]),
            host=DB["host"],
            port=DB["port"],
            database=DB["database"],
        ),
        connect_args={"ssl": ssl_args},
        pool_pre_ping=True,
        pool_recycle=280,
        pool_size=3,
        max_overflow=5,
    )

def db_test():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Đã kết nối Aiven MySQL"
    except Exception as e:
        return False, str(e)

# ============================================================
# DATABASE SETUP
# ============================================================
CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS guides (
        id INT AUTO_INCREMENT PRIMARY KEY,
        guide_code VARCHAR(30) NOT NULL UNIQUE,
        full_name VARCHAR(150) NOT NULL,
        phone VARCHAR(30),
        languages VARCHAR(255),
        routes VARCHAR(255),
        experience_years INT DEFAULT 0,
        status VARCHAR(50) DEFAULT 'Sẵn sàng',
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_guides_status (status),
        INDEX idx_guides_code (guide_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS tours (
        id INT AUTO_INCREMENT PRIMARY KEY,
        tour_code VARCHAR(30) NOT NULL UNIQUE,
        tour_name VARCHAR(255) NOT NULL,
        travel_date DATE NOT NULL,
        meeting_time TIME,
        pickup_point VARCHAR(255),
        destination VARCHAR(255),
        guest_count INT DEFAULT 1,
        guest_language VARCHAR(100),
        tour_type VARCHAR(100),
        guide_code VARCHAR(30),
        status VARCHAR(50) DEFAULT 'Chờ phân công',
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_tours_date (travel_date),
        INDEX idx_tours_status (status),
        INDEX idx_tours_guide (guide_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS assignments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        tour_code VARCHAR(30) NOT NULL,
        guide_code VARCHAR(30) NOT NULL,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_by VARCHAR(100) DEFAULT 'Điều hành',
        status VARCHAR(50) DEFAULT 'Đang phân công',
        note TEXT,
        INDEX idx_assign_tour (tour_code),
        INDEX idx_assign_guide (guide_code),
        INDEX idx_assign_date (assigned_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(80) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(150) NOT NULL,
        role VARCHAR(30) NOT NULL,
        guide_code VARCHAR(30) DEFAULT NULL,
        active TINYINT(1) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_accounts_role (role),
        INDEX idx_accounts_guide (guide_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        action VARCHAR(100),
        tour_code VARCHAR(30),
        content TEXT,
        created_by VARCHAR(100) DEFAULT 'Điều hành',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_logs_time (created_at),
        INDEX idx_logs_tour (tour_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
]

def setup_database():
    engine = get_engine()
    with engine.begin() as conn:
        for sql in CREATE_TABLES_SQL:
            conn.execute(text(sql))

def query_df(sql, params=None):
    return pd.read_sql(text(sql), get_engine(), params=params or {})

def execute_sql(sql, params=None):
    with get_engine().begin() as conn:
        conn.execute(text(sql), params or {})

def add_log(action, tour_code="", content="", created_by="Điều hành"):
    execute_sql(
        """
        INSERT INTO logs (action, tour_code, content, created_by)
        VALUES (:action, :tour_code, :content, :created_by)
        """,
        {
            "action": action,
            "tour_code": tour_code,
            "content": content,
            "created_by": created_by,
        },
    )

def make_id(prefix):
    return prefix + uuid.uuid4().hex[:6].upper()

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return f"pbkdf2_sha256$120000${salt}${digest}"

def verify_password(password, stored):
    try:
        algorithm, iterations, salt, digest = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)).hex()
        return secrets.compare_digest(check, digest)
    except Exception:
        return False

def seed_accounts():
    count = int(query_df("SELECT COUNT(*) AS n FROM accounts").iloc[0]["n"])
    if count > 0:
        return
    demo_accounts = [
        ("admin", "admin123", "Quản trị viên", "Admin", None),
        ("dieuhanh", "dieuhanh123", "Nhân viên Điều hành", "Điều hành", None),
        ("hdv001", "123456", "Nguyễn Minh Anh", "HDV", "HDV001"),
    ]
    with get_engine().begin() as conn:
        for username, password, full_name, role, guide_code in demo_accounts:
            conn.execute(text("""
                INSERT INTO accounts(username, password_hash, full_name, role, guide_code, active)
                VALUES (:username, :password_hash, :full_name, :role, :guide_code, 1)
            """), {
                "username": username, "password_hash": hash_password(password),
                "full_name": full_name, "role": role, "guide_code": guide_code
            })

def authenticate(username, password):
    row = query_df(
        "SELECT username, password_hash, full_name, role, guide_code, active FROM accounts WHERE username=:username LIMIT 1",
        {"username": username.strip()}
    )
    if row.empty or int(row.iloc[0]["active"]) != 1:
        return None
    record = row.iloc[0]
    if not verify_password(password, record["password_hash"]):
        return None
    return {
        "username": record["username"], "full_name": record["full_name"],
        "role": record["role"], "guide_code": record["guide_code"] or ""
    }

def seed_demo_data():
    guide_count = int(query_df("SELECT COUNT(*) AS n FROM guides").iloc[0]["n"])
    tour_count = int(query_df("SELECT COUNT(*) AS n FROM tours").iloc[0]["n"])

    if guide_count == 0:
        demo_guides = [
            ("HDV001", "Nguyễn Minh Anh", "0901000001", "Tiếng Anh", "Vũng Tàu", 3, "Sẵn sàng", ""),
            ("HDV002", "Trần Hoàng Nam", "0901000002", "Tiếng Anh, Trung", "TP.HCM - Vũng Tàu", 5, "Sẵn sàng", ""),
            ("HDV003", "Lê Ngọc Hà", "0901000003", "Tiếng Hàn", "Vũng Tàu - Côn Đảo", 4, "Bận", "Đang dẫn tour"),
            ("HDV004", "Phạm Quốc Bảo", "0901000004", "Tiếng Việt, Anh", "Đông Nam Bộ", 2, "Sẵn sàng", ""),
        ]
        with get_engine().begin() as conn:
            for g in demo_guides:
                conn.execute(
                    text("""
                    INSERT INTO guides
                    (guide_code, full_name, phone, languages, routes,
                     experience_years, status, note)
                    VALUES
                    (:code, :name, :phone, :languages, :routes,
                     :experience, :status, :note)
                    """),
                    {
                        "code": g[0], "name": g[1], "phone": g[2],
                        "languages": g[3], "routes": g[4],
                        "experience": g[5], "status": g[6], "note": g[7],
                    },
                )

    if tour_count == 0:
        demo_tours = [
            ("TOUR001", "Khám phá Vũng Tàu 2N1Đ", "2026-10-02", "07:00",
             "TP.HCM", "Vũng Tàu", 28, "Tiếng Việt", "Đoàn",
             "HDV001", "Đã phân công", ""),
            ("TOUR002", "Vũng Tàu - Côn Đảo", "2026-10-05", "06:30",
             "Vũng Tàu", "Côn Đảo", 18, "Tiếng Hàn", "Đoàn",
             "", "Chờ phân công", ""),
        ]
        with get_engine().begin() as conn:
            for t in demo_tours:
                conn.execute(
                    text("""
                    INSERT INTO tours
                    (tour_code, tour_name, travel_date, meeting_time,
                     pickup_point, destination, guest_count,
                     guest_language, tour_type, guide_code, status, note)
                    VALUES
                    (:code, :name, :travel_date, :meeting_time,
                     :pickup, :destination, :guests,
                     :language, :tour_type, :guide_code, :status, :note)
                    """),
                    {
                        "code": t[0], "name": t[1], "travel_date": t[2],
                        "meeting_time": t[3], "pickup": t[4],
                        "destination": t[5], "guests": t[6],
                        "language": t[7], "tour_type": t[8],
                        "guide_code": t[9], "status": t[10], "note": t[11],
                    },
                )

# ============================================================
# KHỞI TẠO DATABASE
# ============================================================
try:
    setup_database()
    seed_demo_data()
    seed_accounts()
    DB_OK = True
    DB_ERROR = ""
except Exception as e:
    DB_OK = False
    DB_ERROR = str(e)

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
.stApp { background:#f4f7fb; }
.hero {
    padding:30px 35px; border-radius:20px; margin-bottom:22px;
    color:white; min-height:190px;
    background:
      linear-gradient(90deg,rgba(8,48,73,.95),rgba(8,48,73,.42)),
      url("https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85");
    background-size:cover; background-position:center;
    display:flex; flex-direction:column; justify-content:center;
    box-shadow:0 8px 30px rgba(0,0,0,.10);
}
.hero h1 { margin:0; font-size:38px; font-weight:800; }
.hero p { margin:8px 0 0; font-size:16px; opacity:.94; }
.card {
    background:white; padding:20px; border-radius:16px;
    border:1px solid #e9edf3; box-shadow:0 3px 15px rgba(0,0,0,.05);
}
.section-title { color:#12344d; font-size:22px; font-weight:800; margin:24px 0 12px; }
div[data-testid="stSidebar"] { background:#fff; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# ERROR DB
# ============================================================
if not DB_OK:
    st.error("❌ Không kết nối được Aiven MySQL.")
    st.code(DB_ERROR)
    st.info(
        "Kiểm tra Host, Port, User, Password, Database và SSL của Aiven. "
        "App dùng SSL vì Aiven yêu cầu kết nối mã hóa."
    )
    st.stop()

# ============================================================
# ĐĂNG NHẬP & PHÂN QUYỀN
# ============================================================
if "current_user" not in st.session_state:
    st.session_state.current_user = None

if st.session_state.current_user is None:
    st.markdown("""
    <div class="hero">
        <h1>🧭 GUIDE FLOW</h1>
        <p>Hệ thống điều hành tour & phân luồng hướng dẫn viên nội bộ</p>
    </div>
    """, unsafe_allow_html=True)
    left, center, right = st.columns([1, 1.4, 1])
    with center:
        st.markdown("### 🔐 Đăng nhập hệ thống")
        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập", placeholder="Nhập tài khoản")
            password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu")
            submitted = st.form_submit_button("🚀 ĐĂNG NHẬP", type="primary", use_container_width=True)
            if submitted:
                user = authenticate(username, password)
                if user:
                    st.session_state.current_user = user
                    st.rerun()
                else:
                    st.error("Sai tài khoản, mật khẩu hoặc tài khoản đã bị khóa.")
        st.info("Tài khoản mẫu: admin / admin123 • dieuhanh / dieuhanh123 • hdv001 / 123456")
    st.stop()

current_user = st.session_state.current_user
role = current_user["role"]

# ============================================================
# LOAD DATA
# ============================================================
guides = query_df("""
    SELECT guide_code AS `Mã HDV`,
           full_name AS `Họ tên`,
           phone AS `SĐT`,
           languages AS `Ngoại ngữ`,
           routes AS `Chuyên tuyến`,
           experience_years AS `Kinh nghiệm (năm)`,
           status AS `Trạng thái`,
           note AS `Ghi chú`
    FROM guides
    ORDER BY id DESC
""")

tours = query_df("""
    SELECT tour_code AS `Mã tour`,
           tour_name AS `Tên tour`,
           DATE_FORMAT(travel_date, '%Y-%m-%d') AS `Ngày đi`,
           TIME_FORMAT(meeting_time, '%H:%i') AS `Giờ tập trung`,
           pickup_point AS `Điểm đón`,
           destination AS `Điểm đến`,
           guest_count AS `Số khách`,
           guest_language AS `Ngoại ngữ khách`,
           tour_type AS `Loại tour`,
           COALESCE(
             (SELECT full_name FROM guides g
              WHERE g.guide_code = t.guide_code LIMIT 1), ''
           ) AS `HDV`,
           guide_code AS `Mã HDV`,
           status AS `Trạng thái`,
           note AS `Ghi chú`
    FROM tours t
    ORDER BY travel_date, meeting_time
""")

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.image(
        "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=900&q=80",
        use_container_width=True
    )
    st.markdown("### 🧭 GuideFlow")
    st.caption("Phân luồng hướng dẫn viên nội bộ")
    st.success(f"👤 {current_user['full_name']}\n\n🔑 {role}")

    if role == "Admin":
        menu_items = [
            "📊 Tổng quan", "👥 Quản lý tài khoản", "👤 Danh sách HDV",
            "🚌 Quản lý tour", "🧭 Phân công HDV", "📅 Xem lịch",
            "📈 Báo cáo", "📋 Lịch sử điều hành"
        ]
    elif role == "Điều hành":
        menu_items = [
            "📊 Tổng quan", "🚌 Tạo tour", "🔎 Tìm HDV",
            "🧭 Phân công HDV", "📅 Xem lịch"
        ]
    else:
        menu_items = [
            "📊 Tổng quan", "🚌 Tour được giao", "📅 Lịch cá nhân",
            "🔄 Cập nhật trạng thái"
        ]

    menu = st.radio("MENU", menu_items)
    st.divider()
    if st.button("🚪 Đăng xuất", use_container_width=True):
        st.session_state.current_user = None
        st.rerun()
    if DB_OK:
        st.caption("🟢 Aiven MySQL: Đã kết nối")
    st.caption(f"Database: {DB['database']}")

# ============================================================
# HEADER
# ============================================================
st.markdown("""
<div class="hero">
    <h1>🧭 GUIDE FLOW</h1>
    <p>Phân luồng & điều phối hướng dẫn viên nội bộ công ty</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# LOGIC GỢI Ý HDV
# ============================================================
def guide_is_suitable(guide_row, tour_row):
    if str(guide_row["Trạng thái"]).strip().lower() != "sẵn sàng":
        return False

    destination = str(tour_row["Điểm đến"]).lower()
    route = str(guide_row["Chuyên tuyến"]).lower()
    language = str(tour_row["Ngoại ngữ khách"]).lower()
    guide_language = str(guide_row["Ngoại ngữ"]).lower()

    language_ok = (
        language in ["", "tiếng việt"]
        or language in guide_language
        or ("anh" in guide_language and "anh" in language)
        or ("hàn" in guide_language and "hàn" in language)
        or ("trung" in guide_language and "trung" in language)
    )

    route_ok = (
        destination in route
        or route in destination
        or "đông nam bộ" in route
        or ("vũng tàu" in route and "vũng tàu" in destination)
    )

    return language_ok and route_ok

def recommend_guides(tour_row):
    candidates = []
    for _, g in guides.iterrows():
        if guide_is_suitable(g, tour_row):
            score = 0
            if str(tour_row["Ngoại ngữ khách"]).lower() in str(g["Ngoại ngữ"]).lower():
                score += 50
            if str(tour_row["Điểm đến"]).lower() in str(g["Chuyên tuyến"]).lower():
                score += 30
            score += min(int(g["Kinh nghiệm (năm)"]) * 2, 20)
            candidates.append((score, g))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in candidates]

# ============================================================
# QUẢN LÝ TÀI KHOẢN - ADMIN
# ============================================================
if menu == "👥 Quản lý tài khoản":
    st.markdown('<div class="section-title">👥 Quản lý tài khoản nhân viên</div>', unsafe_allow_html=True)
    accounts = query_df("""
        SELECT username AS `Tài khoản`, full_name AS `Họ tên`, role AS `Vai trò`,
               COALESCE(guide_code, '') AS `Mã HDV`,
               CASE WHEN active=1 THEN 'Đang hoạt động' ELSE 'Đã khóa' END AS `Trạng thái`,
               DATE_FORMAT(created_at,'%d/%m/%Y %H:%i') AS `Ngày tạo`
        FROM accounts ORDER BY id DESC
    """)
    st.dataframe(accounts, use_container_width=True, hide_index=True)
    st.markdown("### ➕ Thêm tài khoản nhân viên")
    with st.form("create_account"):
        c1,c2=st.columns(2)
        username=c1.text_input("Tên đăng nhập *")
        full_name=c2.text_input("Họ tên *")
        c3,c4,c5=st.columns(3)
        new_password=c3.text_input("Mật khẩu *", type="password")
        new_role=c4.selectbox("Vai trò", ["Admin","Điều hành","HDV"])
        guide_code=c5.text_input("Mã HDV", placeholder="Chỉ nhập nếu vai trò là HDV")
        create=st.form_submit_button("➕ TẠO TÀI KHOẢN", type="primary", use_container_width=True)
        if create:
            if not username.strip() or not full_name.strip() or not new_password:
                st.error("Vui lòng nhập đầy đủ tài khoản, họ tên và mật khẩu.")
            elif new_role=="HDV" and not guide_code.strip():
                st.error("Tài khoản HDV phải liên kết với Mã HDV.")
            else:
                try:
                    with get_engine().begin() as conn:
                        if new_role=="HDV":
                            exists=conn.execute(text("SELECT COUNT(*) FROM guides WHERE guide_code=:code"),{"code":guide_code.strip()}).scalar()
                            if not exists:
                                st.error("Mã HDV không tồn tại.")
                                st.stop()
                        conn.execute(text("""
                            INSERT INTO accounts(username,password_hash,full_name,role,guide_code,active)
                            VALUES(:username,:password_hash,:full_name,:role,:guide_code,1)
                        """),{"username":username.strip(),"password_hash":hash_password(new_password),"full_name":full_name.strip(),"role":new_role,"guide_code":guide_code.strip() if new_role=="HDV" else None})
                    st.success("Đã tạo tài khoản.")
                    st.rerun()
                except SQLAlchemyError as e:
                    st.error("Không thể tạo tài khoản. Có thể tên đăng nhập đã tồn tại.")
                    st.code(str(e))
    st.markdown("### 🔒 Khóa / mở khóa tài khoản")
    if not accounts.empty:
        selected_user=st.selectbox("Chọn tài khoản",accounts["Tài khoản"].tolist())
        new_active=st.selectbox("Trạng thái mới",["Đang hoạt động","Đã khóa"])
        if st.button("💾 CẬP NHẬT TÀI KHOẢN",use_container_width=True):
            if selected_user==current_user["username"] and new_active=="Đã khóa":
                st.error("Không thể tự khóa tài khoản đang đăng nhập.")
            else:
                execute_sql("UPDATE accounts SET active=:active WHERE username=:username",{"active":1 if new_active=="Đang hoạt động" else 0,"username":selected_user})
                st.success("Đã cập nhật tài khoản.")
                st.rerun()

# ============================================================
# TÌM HDV - ĐIỀU HÀNH
# ============================================================
elif menu == "🔎 Tìm HDV":
    st.markdown('<div class="section-title">🔎 Tìm hướng dẫn viên</div>', unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    keyword=c1.text_input("Từ khóa",placeholder="Tên / mã HDV")
    status_filter=c2.selectbox("Trạng thái",["Tất cả","Sẵn sàng","Bận","Nghỉ phép"])
    language_filter=c3.text_input("Ngoại ngữ",placeholder="Ví dụ: Tiếng Hàn")
    q="SELECT guide_code AS `Mã HDV`,full_name AS `Họ tên`,phone AS `SĐT`,languages AS `Ngoại ngữ`,routes AS `Chuyên tuyến`,experience_years AS `Kinh nghiệm (năm)`,status AS `Trạng thái`,note AS `Ghi chú` FROM guides WHERE 1=1"
    params={}
    if keyword.strip(): q+=" AND (full_name LIKE :kw OR guide_code LIKE :kw)"; params["kw"]=f"%{keyword.strip()}%"
    if status_filter!="Tất cả": q+=" AND status=:status"; params["status"]=status_filter
    if language_filter.strip(): q+=" AND languages LIKE :lang"; params["lang"]=f"%{language_filter.strip()}%"
    q+=" ORDER BY status,experience_years DESC"
    st.dataframe(query_df(q,params),use_container_width=True,hide_index=True)

# ============================================================
# XEM LỊCH
# ============================================================
elif menu == "📅 Xem lịch":
    st.markdown('<div class="section-title">📅 Lịch tour</div>',unsafe_allow_html=True)
    c1,c2=st.columns(2)
    start_date=c1.date_input("Từ ngày",value=date.today())
    end_date=c2.date_input("Đến ngày",value=date.today())
    if start_date>end_date: st.error("Khoảng ngày không hợp lệ.")
    else:
        calendar=query_df("""
            SELECT t.tour_code AS `Mã tour`,t.tour_name AS `Tour`,DATE_FORMAT(t.travel_date,'%d/%m/%Y') AS `Ngày đi`,TIME_FORMAT(t.meeting_time,'%H:%i') AS `Giờ`,t.destination AS `Điểm đến`,t.guest_count AS `Số khách`,COALESCE(g.full_name,'Chưa phân công') AS `HDV`,t.status AS `Trạng thái`
            FROM tours t LEFT JOIN guides g ON g.guide_code=t.guide_code
            WHERE t.travel_date BETWEEN :start_date AND :end_date
            ORDER BY t.travel_date,t.meeting_time
        """,{"start_date":start_date,"end_date":end_date})
        st.dataframe(calendar,use_container_width=True,hide_index=True)

# ============================================================
# BÁO CÁO - ADMIN
# ============================================================
elif menu == "📈 Báo cáo":
    st.markdown('<div class="section-title">📈 Báo cáo & phân tích nguồn lực HDV</div>', unsafe_allow_html=True)
    st.caption("Theo dõi hiệu suất HDV, số tour theo tháng, tuyến phổ biến, nhu cầu HDV và tình trạng thiếu/quá tải.")

    # Bộ lọc thời gian và ngưỡng quá tải
    c1, c2, c3 = st.columns(3)
    report_month = c1.date_input("Tháng báo cáo", value=date.today())
    overload_limit = c2.number_input(
        "Ngưỡng quá tải (tour/HDV/tháng)",
        min_value=1,
        max_value=31,
        value=6,
        step=1,
        help="HDV có số tour được giao trong tháng bằng hoặc vượt ngưỡng này sẽ được đưa vào nhóm lịch dày/quá tải."
    )

    month_start = report_month.replace(day=1)
    if report_month.month == 12:
        next_month = date(report_month.year + 1, 1, 1)
    else:
        next_month = date(report_month.year, report_month.month + 1, 1)

    month_label = report_month.strftime("%m/%Y")

    # ------------------------------------------------------------
    # 1. HIỆU SUẤT HDV
    # ------------------------------------------------------------
    st.markdown("### 👤 Hiệu suất HDV")

    performance = query_df("""
        SELECT
            g.guide_code AS `Mã HDV`,
            g.full_name AS `HDV`,
            g.status AS `Trạng thái hiện tại`,
            COUNT(CASE
                WHEN t.travel_date >= :month_start
                 AND t.travel_date < :next_month
                 AND t.guide_code = g.guide_code
                THEN 1 END) AS `Số tour/tháng`,
            COUNT(CASE
                WHEN t.travel_date >= :month_start
                 AND t.travel_date < :next_month
                 AND t.guide_code = g.guide_code
                 AND t.status = 'Hoàn thành'
                THEN 1 END) AS `Tour hoàn thành`,
            COALESCE(SUM(CASE
                WHEN t.travel_date >= :month_start
                 AND t.travel_date < :next_month
                 AND t.guide_code = g.guide_code
                THEN t.guest_count ELSE 0 END), 0) AS `Số khách phục vụ`
        FROM guides g
        LEFT JOIN tours t ON t.guide_code = g.guide_code
        GROUP BY g.guide_code, g.full_name, g.status
        ORDER BY `Số tour/tháng` DESC, `Tour hoàn thành` DESC, g.full_name
    """, {"month_start": month_start, "next_month": next_month})

    if not performance.empty:
        performance["Tỷ lệ hoàn thành"] = performance.apply(
            lambda r: round((r["Tour hoàn thành"] / r["Số tour/tháng"] * 100), 1)
            if r["Số tour/tháng"] else 0.0,
            axis=1
        )

        st.dataframe(
            performance[
                ["Mã HDV", "HDV", "Trạng thái hiện tại", "Số tour/tháng",
                 "Tour hoàn thành", "Tỷ lệ hoàn thành", "Số khách phục vụ"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tỷ lệ hoàn thành": st.column_config.ProgressColumn(
                    "Tỷ lệ hoàn thành", min_value=0, max_value=100, format="%.1f%%"
                )
            }
        )
    else:
        st.info("Chưa có dữ liệu HDV.")

    # ------------------------------------------------------------
    # 2. SỐ TOUR / THÁNG
    # ------------------------------------------------------------
    st.markdown("### 📅 Số tour/tháng")

    monthly = query_df("""
        SELECT
            DATE_FORMAT(travel_date, '%Y-%m') AS `Tháng`,
            COUNT(*) AS `Tổng tour`,
            SUM(CASE WHEN guide_code IS NULL OR guide_code = '' THEN 1 ELSE 0 END) AS `Tour chưa có HDV`,
            SUM(CASE WHEN status = 'Hoàn thành' THEN 1 ELSE 0 END) AS `Tour hoàn thành`,
            COALESCE(SUM(guest_count), 0) AS `Tổng khách`
        FROM tours
        WHERE travel_date >= DATE_SUB(:month_start, INTERVAL 11 MONTH)
          AND travel_date < :next_month
        GROUP BY DATE_FORMAT(travel_date, '%Y-%m')
        ORDER BY `Tháng`
    """, {"month_start": month_start, "next_month": next_month})

    if not monthly.empty:
        chart_monthly = monthly.set_index("Tháng")[["Tổng tour", "Tour chưa có HDV", "Tour hoàn thành"]]
        st.line_chart(chart_monthly, use_container_width=True)
        st.dataframe(monthly, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có dữ liệu tour trong khoảng thời gian báo cáo.")

    # ------------------------------------------------------------
    # 3. TUYẾN / ĐIỂM ĐẾN PHỔ BIẾN
    # ------------------------------------------------------------
    st.markdown("### 🗺️ Tuyến phổ biến")

    popular_routes = query_df("""
        SELECT
            destination AS `Điểm đến`,
            COUNT(*) AS `Số tour`,
            COALESCE(SUM(guest_count), 0) AS `Số khách`
        FROM tours
        WHERE travel_date >= :month_start
          AND travel_date < :next_month
        GROUP BY destination
        ORDER BY `Số tour` DESC, `Số khách` DESC
    """, {"month_start": month_start, "next_month": next_month})

    if not popular_routes.empty:
        c1, c2 = st.columns([1.15, 1])
        with c1:
            st.dataframe(popular_routes, use_container_width=True, hide_index=True)
        with c2:
            st.bar_chart(popular_routes.set_index("Điểm đến")["Số tour"], use_container_width=True)
    else:
        st.info(f"Chưa có tour trong tháng {month_label}.")

    # ------------------------------------------------------------
    # 4. NHU CẦU HDV
    # ------------------------------------------------------------
    st.markdown("### 👥 Nhu cầu HDV")

    demand = query_df("""
        SELECT
            COUNT(*) AS total_tours,
            SUM(CASE WHEN guide_code IS NULL OR guide_code = '' THEN 1 ELSE 0 END) AS unassigned_tours,
            SUM(CASE WHEN guide_code IS NOT NULL AND guide_code <> '' THEN 1 ELSE 0 END) AS assigned_tours,
            COALESCE(SUM(guest_count), 0) AS total_guests
        FROM tours
        WHERE travel_date >= :month_start
          AND travel_date < :next_month
          AND status <> 'Đã hủy'
    """, {"month_start": month_start, "next_month": next_month})

    available_guides = int(query_df("""
        SELECT COUNT(*) AS n
        FROM guides
        WHERE status = 'Sẵn sàng'
    """).iloc[0]["n"])

    total_guides = int(query_df("SELECT COUNT(*) AS n FROM guides").iloc[0]["n"])
    unassigned_tours = int(demand.iloc[0]["unassigned_tours"] or 0)
    assigned_tours = int(demand.iloc[0]["assigned_tours"] or 0)
    total_tours_month = int(demand.iloc[0]["total_tours"] or 0)
    total_guests_month = int(demand.iloc[0]["total_guests"] or 0)

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("🚌 Tổng tour", total_tours_month)
    d2.metric("⏳ Tour cần HDV", unassigned_tours)
    d3.metric("👤 HDV sẵn sàng", available_guides)
    d4.metric("👥 Tổng HDV", total_guides)

    if unassigned_tours > available_guides:
        st.error(
            f"🔴 Nhu cầu đang cao: còn {unassigned_tours} tour chưa có HDV, "
            f"trong khi hiện có {available_guides} HDV đang sẵn sàng."
        )
    elif unassigned_tours > 0:
        st.warning(
            f"🟡 Có {unassigned_tours} tour chưa được phân công HDV. "
            f"Hiện có {available_guides} HDV đang sẵn sàng."
        )
    else:
        st.success("🟢 Các tour trong tháng hiện đã có HDV hoặc không còn tour chờ phân công.")

    # ------------------------------------------------------------
    # 5. HDV ĐANG THIẾU / QUÁ TẢI
    # ------------------------------------------------------------
    st.markdown("### 🚦 HDV đang thiếu / quá tải")

    workload = query_df("""
        SELECT
            g.guide_code AS `Mã HDV`,
            g.full_name AS `HDV`,
            g.status AS `Trạng thái`,
            COUNT(CASE
                WHEN t.travel_date >= :month_start
                 AND t.travel_date < :next_month
                 AND t.status <> 'Đã hủy'
                THEN t.tour_code END) AS `Số tour được giao`,
            COALESCE(SUM(CASE
                WHEN t.travel_date >= :month_start
                 AND t.travel_date < :next_month
                 AND t.status <> 'Đã hủy'
                THEN t.guest_count ELSE 0 END), 0) AS `Số khách`
        FROM guides g
        LEFT JOIN tours t ON t.guide_code = g.guide_code
        GROUP BY g.guide_code, g.full_name, g.status
        ORDER BY `Số tour được giao` DESC, g.full_name
    """, {"month_start": month_start, "next_month": next_month})

    if not workload.empty:
        workload["Phân loại"] = workload["Số tour được giao"].apply(
            lambda x: "🔴 Quá tải" if x >= overload_limit else ("🟢 Bình thường" if x > 0 else "⚪ Chưa có tour")
        )

        overloaded = workload[workload["Số tour được giao"] >= overload_limit].copy()
        no_tour = workload[workload["Số tour được giao"] == 0].copy()

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**🔴 HDV lịch dày từ {overload_limit} tour/tháng**")
            if overloaded.empty:
                st.success("Không có HDV vượt ngưỡng trong tháng này.")
            else:
                st.dataframe(
                    overloaded[["Mã HDV", "HDV", "Trạng thái", "Số tour được giao", "Số khách", "Phân loại"]],
                    use_container_width=True,
                    hide_index=True
                )

        with c2:
            st.markdown("**🟢 HDV chưa được giao tour trong tháng**")
            if no_tour.empty:
                st.info("Không có dữ liệu.")
            else:
                st.dataframe(
                    no_tour[["Mã HDV", "HDV", "Trạng thái", "Số tour được giao", "Số khách", "Phân loại"]],
                    use_container_width=True,
                    hide_index=True
                )

        st.markdown("**📊 Phân bổ khối lượng HDV**")
        st.bar_chart(
            workload.set_index("HDV")["Số tour được giao"],
            use_container_width=True
        )

        st.download_button(
            "⬇️ Tải báo cáo HDV CSV",
            workload.to_csv(index=False).encode("utf-8-sig"),
            f"bao_cao_hdv_{report_month.strftime('%Y_%m')}.csv",
            "text/csv",
            use_container_width=True,
        )
    else:
        st.info("Chưa có dữ liệu HDV để phân tích.")

# ============================================================
# HDV: TOUR ĐƯỢC GIAO
# ============================================================
elif menu == "🚌 Tour được giao":
    st.markdown('<div class="section-title">🚌 Tour được giao cho tôi</div>',unsafe_allow_html=True)
    assigned=query_df("""
        SELECT t.tour_code AS `Mã tour`,t.tour_name AS `Tên tour`,DATE_FORMAT(t.travel_date,'%d/%m/%Y') AS `Ngày đi`,TIME_FORMAT(t.meeting_time,'%H:%i') AS `Giờ tập trung`,t.pickup_point AS `Điểm đón`,t.destination AS `Điểm đến`,t.guest_count AS `Số khách`,t.guest_language AS `Ngoại ngữ`,t.status AS `Trạng thái`,t.note AS `Ghi chú`
        FROM tours t WHERE t.guide_code=:guide_code ORDER BY t.travel_date,t.meeting_time
    """,{"guide_code":current_user["guide_code"]})
    st.dataframe(assigned,use_container_width=True,hide_index=True)

# ============================================================
# HDV: LỊCH CÁ NHÂN
# ============================================================
elif menu == "📅 Lịch cá nhân":
    st.markdown('<div class="section-title">📅 Lịch cá nhân</div>',unsafe_allow_html=True)
    personal=query_df("SELECT DATE_FORMAT(travel_date,'%d/%m/%Y') AS `Ngày`,TIME_FORMAT(meeting_time,'%H:%i') AS `Giờ`,tour_name AS `Tour`,destination AS `Điểm đến`,guest_count AS `Số khách`,status AS `Trạng thái` FROM tours WHERE guide_code=:guide_code ORDER BY travel_date,meeting_time",{"guide_code":current_user["guide_code"]})
    st.dataframe(personal,use_container_width=True,hide_index=True)

# ============================================================
# HDV: CẬP NHẬT TRẠNG THÁI
# ============================================================
elif menu == "🔄 Cập nhật trạng thái":
    st.markdown('<div class="section-title">🔄 Cập nhật trạng thái tour</div>',unsafe_allow_html=True)
    my_tours=query_df("SELECT tour_code AS `Mã tour`,tour_name AS `Tên tour`,status AS `Trạng thái` FROM tours WHERE guide_code=:guide_code AND status NOT IN ('Hoàn thành','Đã hủy') ORDER BY travel_date",{"guide_code":current_user["guide_code"]})
    if my_tours.empty: st.info("Bạn hiện không có tour cần cập nhật.")
    else:
        code=st.selectbox("Chọn tour",my_tours["Mã tour"].tolist())
        status=st.selectbox("Trạng thái mới",["Đã phân công","Đang thực hiện","Hoàn thành"])
        note=st.text_input("Ghi chú")
        if st.button("💾 CẬP NHẬT",type="primary",use_container_width=True):
            try:
                with get_engine().begin() as conn:
                    conn.execute(text("UPDATE tours SET status=:status,note=:note WHERE tour_code=:code AND guide_code=:guide_code"),{"status":status,"note":note.strip(),"code":code,"guide_code":current_user["guide_code"]})
                    conn.execute(text("UPDATE assignments SET status=:status WHERE tour_code=:code AND guide_code=:guide_code"),{"status":status,"code":code,"guide_code":current_user["guide_code"]})
                    conn.execute(text("INSERT INTO logs(action,tour_code,content,created_by) VALUES ('HDV cập nhật trạng thái',:code,:content,:created_by)"),{"code":code,"content":f"HDV cập nhật → {status}. {note.strip()}","created_by":current_user["full_name"]})
                    if status=="Hoàn thành": conn.execute(text("UPDATE guides SET status='Sẵn sàng' WHERE guide_code=:guide_code"),{"guide_code":current_user["guide_code"]})
                st.success("Đã cập nhật trạng thái tour."); st.rerun()
            except SQLAlchemyError as e: st.error("Không thể cập nhật trạng thái."); st.code(str(e))

# ============================================================
# TẠO TOUR - ĐIỀU HÀNH
# ============================================================
elif menu == "🚌 Tạo tour":
    st.markdown('<div class="section-title">🚌 Tạo tour mới</div>',unsafe_allow_html=True)
    with st.form("new_tour_role"):
        c1,c2=st.columns(2); tour_name=c1.text_input("Tên tour *"); destination=c2.text_input("Điểm đến *")
        c3,c4,c5=st.columns(3); travel_date=c3.date_input("Ngày đi",value=date.today()); meeting_time=c4.time_input("Giờ tập trung",value=time(7,0)); guests=c5.number_input("Số khách",min_value=1,max_value=10000,value=20)
        c6,c7,c8=st.columns(3); pickup=c6.text_input("Điểm đón","TP.HCM"); language=c7.selectbox("Ngoại ngữ khách",["Tiếng Việt","Tiếng Anh","Tiếng Hàn","Tiếng Trung","Khác"]); tour_type=c8.selectbox("Loại tour",["Đoàn","Khách lẻ","MICE","VIP","Inbound"])
        note=st.text_area("Ghi chú")
        submit=st.form_submit_button("➕ TẠO TOUR",type="primary",use_container_width=True)
        if submit:
            if not tour_name.strip() or not destination.strip(): st.error("Vui lòng nhập Tên tour và Điểm đến.")
            else:
                code=make_id("TOUR")
                try:
                    with get_engine().begin() as conn:
                        conn.execute(text("INSERT INTO tours(tour_code,tour_name,travel_date,meeting_time,pickup_point,destination,guest_count,guest_language,tour_type,guide_code,status,note) VALUES(:code,:name,:travel_date,:meeting_time,:pickup,:destination,:guests,:language,:tour_type,'','Chờ phân công',:note)"),{"code":code,"name":tour_name.strip(),"travel_date":travel_date,"meeting_time":meeting_time,"pickup":pickup.strip(),"destination":destination.strip(),"guests":guests,"language":language,"tour_type":tour_type,"note":note.strip()})
                        conn.execute(text("INSERT INTO logs(action,tour_code,content,created_by) VALUES ('Tạo tour',:code,:content,:created_by)"),{"code":code,"content":f"Tạo tour {tour_name.strip()}","created_by":current_user["full_name"]})
                    st.success(f"Đã tạo tour {code}."); st.rerun()
                except SQLAlchemyError as e: st.error("Không thể tạo tour."); st.code(str(e))

# ============================================================
# TỔNG QUAN
# ============================================================
if menu == "📊 Tổng quan":
    total_tours = len(tours)
    waiting = int((tours["Trạng thái"] == "Chờ phân công").sum())
    assigned = int((tours["Trạng thái"] == "Đã phân công").sum())
    available = int((guides["Trạng thái"] == "Sẵn sàng").sum())
    total_guests = int(tours["Số khách"].sum()) if not tours.empty else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    metrics = [
        ("🚌", "TỔNG TOUR", total_tours),
        ("⏳", "CHỜ PHÂN CÔNG", waiting),
        ("✅", "ĐÃ PHÂN CÔNG", assigned),
        ("👤", "HDV SẴN SÀNG", available),
        ("👥", "TỔNG KHÁCH", total_guests),
    ]

    for col, (icon, title, value) in zip([c1,c2,c3,c4,c5], metrics):
        with col:
            st.markdown(
                f"""<div class="card">
                    <div style="color:#6b7785;font-size:13px">{icon} {title}</div>
                    <div style="font-size:30px;font-weight:800;color:#12344d">{value:,}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-title">📅 Tour cần xử lý</div>', unsafe_allow_html=True)
    waiting_df = tours[tours["Trạng thái"] == "Chờ phân công"].copy()

    if waiting_df.empty:
        st.success("🎉 Hiện tại không có tour nào đang chờ phân công.")
    else:
        st.dataframe(
            waiting_df[
                ["Mã tour","Tên tour","Ngày đi","Giờ tập trung",
                 "Điểm đến","Số khách","Ngoại ngữ khách","Trạng thái"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown('<div class="section-title">📊 Trạng thái HDV</div>', unsafe_allow_html=True)
    if not guides.empty:
        st.bar_chart(guides["Trạng thái"].value_counts())

# ============================================================
# PHÂN CÔNG
# ============================================================
elif menu == "🧭 Phân công HDV":
    st.markdown('<div class="section-title">🧭 Phân công hướng dẫn viên</div>', unsafe_allow_html=True)

    available_tours = tours[tours["Trạng thái"].isin(
        ["Chờ phân công", "Đã phân công"]
    )].copy()

    if available_tours.empty:
        st.info("Chưa có tour cần phân công.")
    else:
        tour_code = st.selectbox("Chọn tour", available_tours["Mã tour"].tolist())
        tour = available_tours[available_tours["Mã tour"] == tour_code].iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tour", tour["Tên tour"])
        c2.metric("Số khách", int(tour["Số khách"]))
        c3.metric("Điểm đến", tour["Điểm đến"])
        c4.metric("Ngoại ngữ", tour["Ngoại ngữ khách"])

        recommended = recommend_guides(tour)

        st.markdown("### 🤖 HDV phù hợp")

        if recommended:
            rec_df = pd.DataFrame(recommended)[
                ["Mã HDV","Họ tên","Ngoại ngữ","Chuyên tuyến",
                 "Kinh nghiệm (năm)","Trạng thái"]
            ]
            st.dataframe(rec_df, use_container_width=True, hide_index=True)

            options = [
                f'{g["Mã HDV"]} | {g["Họ tên"]} | {g["Ngoại ngữ"]}'
                for g in recommended
            ]
            selected = st.selectbox("Chọn HDV", options)
            selected_code = selected.split(" | ")[0]

            if st.button("✅ XÁC NHẬN PHÂN CÔNG", type="primary", use_container_width=True):
                try:
                    with get_engine().begin() as conn:
                        # Khóa HDV trong transaction để tránh hai thao tác
                        # đồng thời cùng phân một HDV.
                        guide = conn.execute(
                            text("""
                            SELECT guide_code, full_name, status
                            FROM guides
                            WHERE guide_code = :code
                            FOR UPDATE
                            """),
                            {"code": selected_code},
                        ).mappings().first()

                        if not guide:
                            st.error("Không tìm thấy HDV.")
                            st.stop()

                        if guide["status"] != "Sẵn sàng":
                            st.error("HDV này vừa được người khác phân công.")
                            st.stop()

                        conn.execute(
                            text("""
                            UPDATE tours
                            SET guide_code = :guide_code,
                                status = 'Đã phân công'
                            WHERE tour_code = :tour_code
                            """),
                            {"guide_code": selected_code, "tour_code": tour_code},
                        )

                        conn.execute(
                            text("""
                            UPDATE guides
                            SET status = 'Bận'
                            WHERE guide_code = :guide_code
                            """),
                            {"guide_code": selected_code},
                        )

                        conn.execute(
                            text("""
                            INSERT INTO assignments
                            (tour_code, guide_code, assigned_by, status)
                            VALUES (:tour_code, :guide_code, 'Điều hành', 'Đang phân công')
                            """),
                            {"tour_code": tour_code, "guide_code": selected_code},
                        )

                        conn.execute(
                            text("""
                            INSERT INTO logs
                            (action, tour_code, content, created_by)
                            VALUES
                            ('Phân công HDV', :tour_code, :content, 'Điều hành')
                            """),
                            {
                                "tour_code": tour_code,
                                "content": f'Phân công {guide["full_name"]} ({selected_code})',
                            },
                        )

                    st.success(f'Đã phân công {guide["full_name"]} cho {tour_code}.')
                    st.rerun()

                except SQLAlchemyError as e:
                    st.error("Không thể lưu phân công.")
                    st.code(str(e))
        else:
            st.warning(
                "⚠️ Chưa tìm thấy HDV đang sẵn sàng phù hợp cả tuyến và ngoại ngữ."
            )
            available = guides[guides["Trạng thái"] == "Sẵn sàng"]
            if not available.empty:
                st.dataframe(
                    available[
                        ["Mã HDV","Họ tên","Ngoại ngữ","Chuyên tuyến","Kinh nghiệm (năm)"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

# ============================================================
# QUẢN LÝ TOUR
# ============================================================
elif menu == "🚌 Quản lý tour":
    st.markdown('<div class="section-title">🚌 Danh sách tour</div>', unsafe_allow_html=True)

    st.dataframe(
        tours[
            ["Mã tour","Tên tour","Ngày đi","Giờ tập trung",
             "Điểm đón","Điểm đến","Số khách","Ngoại ngữ khách",
             "HDV","Trạng thái"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### ➕ Tạo tour mới")

    with st.form("new_tour"):
        c1, c2 = st.columns(2)
        tour_name = c1.text_input("Tên tour *", placeholder="Ví dụ: Vũng Tàu 2N1Đ")
        destination = c2.text_input("Điểm đến *", placeholder="Ví dụ: Vũng Tàu")

        c3, c4, c5 = st.columns(3)
        travel_date = c3.date_input("Ngày đi", value=date.today())
        meeting_time = c4.time_input("Giờ tập trung", value=time(7, 0))
        guests = c5.number_input("Số khách", min_value=1, max_value=10000, value=20)

        c6, c7, c8 = st.columns(3)
        pickup = c6.text_input("Điểm đón", "TP.HCM")
        language = c7.selectbox(
            "Ngoại ngữ khách",
            ["Tiếng Việt","Tiếng Anh","Tiếng Hàn","Tiếng Trung","Khác"],
        )
        tour_type = c8.selectbox(
            "Loại tour",
            ["Đoàn","Khách lẻ","MICE","VIP","Inbound"],
        )

        note = st.text_area("Ghi chú", placeholder="Yêu cầu đặc biệt của đoàn...")

        submit = st.form_submit_button(
            "➕ TẠO TOUR", use_container_width=True, type="primary"
        )

        if submit:
            if not tour_name.strip() or not destination.strip():
                st.error("Vui lòng nhập Tên tour và Điểm đến.")
            else:
                code = make_id("TOUR")
                try:
                    with get_engine().begin() as conn:
                        conn.execute(
                            text("""
                            INSERT INTO tours
                            (tour_code, tour_name, travel_date, meeting_time,
                             pickup_point, destination, guest_count,
                             guest_language, tour_type, guide_code, status, note)
                            VALUES
                            (:code, :name, :travel_date, :meeting_time,
                             :pickup, :destination, :guests,
                             :language, :tour_type, '', 'Chờ phân công', :note)
                            """),
                            {
                                "code": code,
                                "name": tour_name.strip(),
                                "travel_date": travel_date,
                                "meeting_time": meeting_time,
                                "pickup": pickup.strip(),
                                "destination": destination.strip(),
                                "guests": guests,
                                "language": language,
                                "tour_type": tour_type,
                                "note": note.strip(),
                            },
                        )

                        conn.execute(
                            text("""
                            INSERT INTO logs
                            (action, tour_code, content, created_by)
                            VALUES ('Tạo tour', :tour_code, :content, 'Điều hành')
                            """),
                            {
                                "tour_code": code,
                                "content": f"Tạo tour {tour_name.strip()}",
                            },
                        )

                    st.success(f"Đã tạo tour {code}.")
                    st.rerun()
                except SQLAlchemyError as e:
                    st.error("Không thể tạo tour.")
                    st.code(str(e))

    st.markdown("### 🔄 Cập nhật trạng thái tour")

    if not tours.empty:
        update_code = st.selectbox(
            "Chọn mã tour",
            tours["Mã tour"].tolist(),
            key="update_tour",
        )
        new_status = st.selectbox(
            "Trạng thái mới",
            ["Chờ phân công","Đã phân công","Đang thực hiện","Hoàn thành","Đã hủy"],
        )

        if st.button("💾 CẬP NHẬT TRẠNG THÁI", use_container_width=True):
            try:
                with get_engine().begin() as conn:
                    current = conn.execute(
                        text("""
                        SELECT status, guide_code
                        FROM tours
                        WHERE tour_code = :tour_code
                        FOR UPDATE
                        """),
                        {"tour_code": update_code},
                    ).mappings().first()

                    if not current:
                        st.error("Không tìm thấy tour.")
                        st.stop()

                    old_status = current["status"]
                    guide_code = current["guide_code"]

                    conn.execute(
                        text("""
                        UPDATE tours
                        SET status = :status
                        WHERE tour_code = :tour_code
                        """),
                        {"status": new_status, "tour_code": update_code},
                    )

                    if new_status in ["Hoàn thành", "Đã hủy"] and guide_code:
                        conn.execute(
                            text("""
                            UPDATE guides
                            SET status = 'Sẵn sàng'
                            WHERE guide_code = :guide_code
                            """),
                            {"guide_code": guide_code},
                        )

                        conn.execute(
                            text("""
                            UPDATE assignments
                            SET status = :status
                            WHERE tour_code = :tour_code
                              AND guide_code = :guide_code
                            """),
                            {
                                "status": new_status,
                                "tour_code": update_code,
                                "guide_code": guide_code,
                            },
                        )

                    conn.execute(
                        text("""
                        INSERT INTO logs
                        (action, tour_code, content, created_by)
                        VALUES ('Cập nhật tour', :tour_code, :content, 'Điều hành')
                        """),
                        {
                            "tour_code": update_code,
                            "content": f"{old_status} → {new_status}",
                        },
                    )

                st.success("Đã cập nhật.")
                st.rerun()
            except SQLAlchemyError as e:
                st.error("Không thể cập nhật.")
                st.code(str(e))

# ============================================================
# HDV
# ============================================================
elif menu == "👤 Danh sách HDV":
    st.markdown('<div class="section-title">👤 Quản lý hướng dẫn viên</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng HDV", len(guides))
    c2.metric("Sẵn sàng", int((guides["Trạng thái"] == "Sẵn sàng").sum()))
    c3.metric("Đang bận", int((guides["Trạng thái"] == "Bận").sum()))

    st.dataframe(guides, use_container_width=True, hide_index=True)

    st.markdown("### ➕ Thêm hướng dẫn viên")

    with st.form("new_guide"):
        c1, c2 = st.columns(2)
        guide_name = c1.text_input("Họ tên HDV *")
        phone = c2.text_input("Số điện thoại")

        c3, c4 = st.columns(2)
        language = c3.multiselect(
            "Ngoại ngữ",
            ["Tiếng Việt","Tiếng Anh","Tiếng Hàn","Tiếng Trung","Tiếng Nhật"],
            default=["Tiếng Việt"],
        )
        route = c4.text_input("Chuyên tuyến", placeholder="Ví dụ: Vũng Tàu - Côn Đảo")

        c5, c6 = st.columns(2)
        experience = c5.number_input(
            "Kinh nghiệm (năm)", min_value=0, max_value=50, value=1
        )
        status = c6.selectbox("Trạng thái", ["Sẵn sàng","Bận","Nghỉ phép"])
        note = st.text_input("Ghi chú")

        add_guide = st.form_submit_button(
            "➕ THÊM HDV", use_container_width=True, type="primary"
        )

        if add_guide:
            if not guide_name.strip():
                st.error("Vui lòng nhập họ tên HDV.")
            else:
                code = make_id("HDV")
                try:
                    with get_engine().begin() as conn:
                        conn.execute(
                            text("""
                            INSERT INTO guides
                            (guide_code, full_name, phone, languages, routes,
                             experience_years, status, note)
                            VALUES
                            (:code, :name, :phone, :languages, :routes,
                             :experience, :status, :note)
                            """),
                            {
                                "code": code,
                                "name": guide_name.strip(),
                                "phone": phone.strip(),
                                "languages": ", ".join(language),
                                "routes": route.strip(),
                                "experience": experience,
                                "status": status,
                                "note": note.strip(),
                            },
                        )

                        conn.execute(
                            text("""
                            INSERT INTO logs
                            (action, tour_code, content, created_by)
                            VALUES ('Thêm HDV', '', :content, 'Điều hành')
                            """),
                            {"content": f"Thêm HDV {guide_name.strip()}"},
                        )

                    st.success(f"Đã thêm HDV {guide_name.strip()} ({code}).")
                    st.rerun()
                except SQLAlchemyError as e:
                    st.error("Không thể thêm HDV.")
                    st.code(str(e))

# ============================================================
# LỊCH SỬ
# ============================================================
elif menu == "📋 Lịch sử điều hành":
    st.markdown('<div class="section-title">📋 Nhật ký điều hành</div>', unsafe_allow_html=True)

    logs = query_df("""
        SELECT
            DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') AS `Thời gian`,
            created_by AS `Người thao tác`,
            action AS `Hành động`,
            tour_code AS `Mã tour`,
            content AS `Nội dung`
        FROM logs
        ORDER BY created_at DESC
    """)

    st.dataframe(logs, use_container_width=True, hide_index=True)

    st.download_button(
        "⬇️ TẢI NHẬT KÝ CSV",
        logs.to_csv(index=False).encode("utf-8-sig"),
        "nhat_ky_dieu_hanh.csv",
        "text/csv",
        use_container_width=True,
    )

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption(
    "🧭 GuideFlow • Aiven MySQL • "
    f"Cập nhật: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
)
