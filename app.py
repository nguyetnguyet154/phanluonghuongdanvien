import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import quote_plus
import uuid

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

    if DB_OK:
        st.success("🟢 Aiven MySQL: Đã kết nối")

    menu = st.radio(
        "MENU",
        [
            "📊 Tổng quan",
            "🧭 Phân công HDV",
            "🚌 Quản lý tour",
            "👤 Danh sách HDV",
            "📋 Lịch sử điều hành",
        ],
    )

    st.divider()
    st.caption(f"Database: {DB['database']}")
    st.caption("Dữ liệu được lưu trực tiếp trên Aiven MySQL.")

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
