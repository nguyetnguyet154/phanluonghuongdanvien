import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import uuid

# ============================================================
# CẤU HÌNH
# ============================================================
st.set_page_config(
    page_title="GuideFlow - Phân luồng hướng dẫn viên",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CSS GIAO DIỆN
# ============================================================
st.markdown("""
<style>
    .stApp {
        background: #f4f7fb;
    }

    .hero {
        padding: 30px 35px;
        border-radius: 20px;
        margin-bottom: 22px;
        color: white;
        min-height: 190px;
        background:
            linear-gradient(90deg, rgba(8,48,73,.95), rgba(8,48,73,.42)),
            url("https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85");
        background-size: cover;
        background-position: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 8px 30px rgba(0,0,0,.10);
    }

    .hero h1 {
        margin: 0;
        font-size: 38px;
        font-weight: 800;
    }

    .hero p {
        margin: 8px 0 0 0;
        font-size: 16px;
        opacity: .94;
    }

    .card {
        background: white;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #e9edf3;
        box-shadow: 0 3px 15px rgba(0,0,0,.05);
    }

    .section-title {
        color: #12344d;
        font-size: 22px;
        font-weight: 800;
        margin: 24px 0 12px 0;
    }

    .status-green {
        background: #e8f7ee;
        color: #177245;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 700;
    }

    .status-yellow {
        background: #fff5d9;
        color: #946200;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 700;
    }

    .status-red {
        background: #fdecec;
        color: #b42318;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 700;
    }

    div[data-testid="stSidebar"] {
        background: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# KHỞI TẠO DỮ LIỆU
# ============================================================
if "guides" not in st.session_state:
    st.session_state.guides = pd.DataFrame([
        {
            "Mã HDV": "HDV001",
            "Họ tên": "Nguyễn Minh Anh",
            "SĐT": "0901000001",
            "Ngoại ngữ": "Tiếng Anh",
            "Chuyên tuyến": "Vũng Tàu",
            "Kinh nghiệm (năm)": 3,
            "Trạng thái": "Sẵn sàng",
            "Ghi chú": ""
        },
        {
            "Mã HDV": "HDV002",
            "Họ tên": "Trần Hoàng Nam",
            "SĐT": "0901000002",
            "Ngoại ngữ": "Tiếng Anh, Trung",
            "Chuyên tuyến": "TP.HCM - Vũng Tàu",
            "Kinh nghiệm (năm)": 5,
            "Trạng thái": "Sẵn sàng",
            "Ghi chú": ""
        },
        {
            "Mã HDV": "HDV003",
            "Họ tên": "Lê Ngọc Hà",
            "SĐT": "0901000003",
            "Ngoại ngữ": "Tiếng Hàn",
            "Chuyên tuyến": "Vũng Tàu - Côn Đảo",
            "Kinh nghiệm (năm)": 4,
            "Trạng thái": "Bận",
            "Ghi chú": "Đang dẫn tour"
        },
        {
            "Mã HDV": "HDV004",
            "Họ tên": "Phạm Quốc Bảo",
            "SĐT": "0901000004",
            "Ngoại ngữ": "Tiếng Việt, Anh",
            "Chuyên tuyến": "Đông Nam Bộ",
            "Kinh nghiệm (năm)": 2,
            "Trạng thái": "Sẵn sàng",
            "Ghi chú": ""
        },
    ])

if "tours" not in st.session_state:
    st.session_state.tours = pd.DataFrame([
        {
            "Mã tour": "TOUR001",
            "Tên tour": "Khám phá Vũng Tàu 2N1Đ",
            "Ngày đi": "2026-10-02",
            "Giờ tập trung": "07:00",
            "Điểm đón": "TP.HCM",
            "Điểm đến": "Vũng Tàu",
            "Số khách": 28,
            "Ngoại ngữ khách": "Tiếng Việt",
            "Loại tour": "Đoàn",
            "HDV": "Nguyễn Minh Anh",
            "Mã HDV": "HDV001",
            "Trạng thái": "Đã phân công",
            "Ghi chú": ""
        },
        {
            "Mã tour": "TOUR002",
            "Tên tour": "Vũng Tàu - Côn Đảo",
            "Ngày đi": "2026-10-05",
            "Giờ tập trung": "06:30",
            "Điểm đón": "Vũng Tàu",
            "Điểm đến": "Côn Đảo",
            "Số khách": 18,
            "Ngoại ngữ khách": "Tiếng Hàn",
            "Loại tour": "Đoàn",
            "HDV": "",
            "Mã HDV": "",
            "Trạng thái": "Chờ phân công",
            "Ghi chú": ""
        },
    ])

if "logs" not in st.session_state:
    st.session_state.logs = pd.DataFrame([
        {
            "Thời gian": "2026-09-29 08:30:00",
            "Người thao tác": "Điều hành",
            "Hành động": "Phân công HDV",
            "Mã tour": "TOUR001",
            "Nội dung": "Phân công Nguyễn Minh Anh"
        }
    ])

# ============================================================
# HÀM HỖ TRỢ
# ============================================================
def make_id(prefix):
    return prefix + uuid.uuid4().hex[:6].upper()

def add_log(action, tour_code="", content=""):
    row = pd.DataFrame([{
        "Thời gian": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Người thao tác": "Điều hành",
        "Hành động": action,
        "Mã tour": tour_code,
        "Nội dung": content
    }])
    st.session_state.logs = pd.concat(
        [row, st.session_state.logs],
        ignore_index=True
    )

def guide_is_suitable(guide_row, tour_row):
    status = str(guide_row["Trạng thái"]).strip().lower()
    if status != "sẵn sàng":
        return False

    tour_destination = str(tour_row["Điểm đến"]).lower()
    guide_route = str(guide_row["Chuyên tuyến"]).lower()

    language = str(tour_row["Ngoại ngữ khách"]).lower()
    guide_language = str(guide_row["Ngoại ngữ"]).lower()

    language_ok = (
        language in ["", "tiếng việt"]
        or language in guide_language
        or "anh" in guide_language and "anh" in language
        or "hàn" in guide_language and "hàn" in language
        or "trung" in guide_language and "trung" in language
    )

    route_ok = (
        tour_destination in guide_route
        or guide_route in tour_destination
        or "đông nam bộ" in guide_route
        or "vũng tàu" in guide_route and "vũng tàu" in tour_destination
    )

    return language_ok and route_ok

def recommend_guides(tour_row):
    candidates = []
    for _, g in st.session_state.guides.iterrows():
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
# SIDEBAR
# ============================================================
with st.sidebar:
    st.image(
        "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=900&q=80",
        use_container_width=True
    )

    st.markdown("### 🧭 GuideFlow")
    st.caption("Hệ thống phân luồng hướng dẫn viên nội bộ")

    menu = st.radio(
        "MENU",
        [
            "📊 Tổng quan",
            "🧭 Phân công HDV",
            "🚌 Quản lý tour",
            "👤 Danh sách HDV",
            "📋 Lịch sử điều hành"
        ]
    )

    st.divider()

    st.info(
        "💡 App phù hợp cho bộ phận Điều hành/Sales nội bộ "
        "theo dõi tour và phân công hướng dẫn viên."
    )

# ============================================================
# HEADER
# ============================================================
st.markdown("""
<div class="hero">
    <h1>🧭 GUIDE FLOW</h1>
    <p>Phân luồng & điều phối hướng dẫn viên nội bộ công ty</p>
</div>
""", unsafe_allow_html=True)

guides = st.session_state.guides
tours = st.session_state.tours

# ============================================================
# TỔNG QUAN
# ============================================================
if menu == "📊 Tổng quan":

    total_tours = len(tours)
    waiting = int((tours["Trạng thái"] == "Chờ phân công").sum())
    assigned = int((tours["Trạng thái"] == "Đã phân công").sum())
    available = int((guides["Trạng thái"] == "Sẵn sàng").sum())
    busy = int((guides["Trạng thái"] == "Bận").sum())
    total_guests = int(tours["Số khách"].sum())

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
                f"""
                <div class="card">
                    <div style="color:#6b7785;font-size:13px">{icon} {title}</div>
                    <div style="font-size:30px;font-weight:800;color:#12344d">{value:,}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown('<div class="section-title">📅 Tour cần xử lý</div>', unsafe_allow_html=True)

    waiting_df = tours[tours["Trạng thái"] == "Chờ phân công"].copy()

    if waiting_df.empty:
        st.success("🎉 Hiện tại không có tour nào đang chờ phân công.")
    else:
        st.dataframe(
            waiting_df[
                ["Mã tour", "Tên tour", "Ngày đi", "Giờ tập trung",
                 "Điểm đến", "Số khách", "Ngoại ngữ khách", "Trạng thái"]
            ],
            use_container_width=True,
            hide_index=True
        )

    st.markdown('<div class="section-title">📊 Phân bổ trạng thái HDV</div>', unsafe_allow_html=True)

    chart = guides["Trạng thái"].value_counts()
    st.bar_chart(chart)

# ============================================================
# PHÂN CÔNG HDV
# ============================================================
elif menu == "🧭 Phân công HDV":

    st.markdown('<div class="section-title">🧭 Phân công hướng dẫn viên cho tour</div>', unsafe_allow_html=True)

    waiting_df = tours[tours["Trạng thái"] != "Hoàn thành"].copy()

    if waiting_df.empty:
        st.info("Chưa có tour cần xử lý.")
    else:
        tour_code = st.selectbox(
            "Chọn tour",
            waiting_df["Mã tour"].tolist()
        )

        tour_idx = st.session_state.tours.index[
            st.session_state.tours["Mã tour"] == tour_code
        ][0]

        tour = st.session_state.tours.loc[tour_idx]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tour", tour["Tên tour"])
        c2.metric("Số khách", int(tour["Số khách"]))
        c3.metric("Điểm đến", tour["Điểm đến"])
        c4.metric("Ngoại ngữ", tour["Ngoại ngữ khách"])

        st.markdown("### 🤖 Gợi ý HDV phù hợp")

        recommended = recommend_guides(tour)

        if recommended:
            rec_df = pd.DataFrame(recommended)[
                ["Mã HDV", "Họ tên", "Ngoại ngữ", "Chuyên tuyến",
                 "Kinh nghiệm (năm)", "Trạng thái"]
            ]
            st.dataframe(rec_df, use_container_width=True, hide_index=True)

            options = [
                f'{g["Mã HDV"]} | {g["Họ tên"]} | {g["Ngoại ngữ"]}'
                for g in recommended
            ]

            selected = st.selectbox(
                "Chọn HDV",
                options
            )

            selected_code = selected.split(" | ")[0]

            if st.button("✅ XÁC NHẬN PHÂN CÔNG", type="primary", use_container_width=True):
                guide_idx = st.session_state.guides.index[
                    st.session_state.guides["Mã HDV"] == selected_code
                ][0]

                guide_name = st.session_state.guides.loc[guide_idx, "Họ tên"]

                st.session_state.tours.loc[tour_idx, "HDV"] = guide_name
                st.session_state.tours.loc[tour_idx, "Mã HDV"] = selected_code
                st.session_state.tours.loc[tour_idx, "Trạng thái"] = "Đã phân công"

                st.session_state.guides.loc[guide_idx, "Trạng thái"] = "Bận"

                add_log(
                    "Phân công HDV",
                    tour_code,
                    f"Phân công {guide_name} ({selected_code})"
                )

                st.success(f"Đã phân công {guide_name} cho {tour_code}.")
                st.rerun()

        else:
            st.warning(
                "⚠️ Không tìm thấy HDV đang sẵn sàng phù hợp đồng thời "
                "với tuyến và ngoại ngữ của tour."
            )

            available = guides[guides["Trạng thái"] == "Sẵn sàng"]

            if not available.empty:
                st.markdown("### 👤 HDV đang sẵn sàng để điều hành xem xét")
                st.dataframe(
                    available[
                        ["Mã HDV", "Họ tên", "Ngoại ngữ",
                         "Chuyên tuyến", "Kinh nghiệm (năm)"]
                    ],
                    use_container_width=True,
                    hide_index=True
                )

# ============================================================
# QUẢN LÝ TOUR
# ============================================================
elif menu == "🚌 Quản lý tour":

    st.markdown('<div class="section-title">🚌 Danh sách tour</div>', unsafe_allow_html=True)

    st.dataframe(
        tours[
            ["Mã tour", "Tên tour", "Ngày đi", "Giờ tập trung",
             "Điểm đón", "Điểm đến", "Số khách", "Ngoại ngữ khách",
             "HDV", "Trạng thái"]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("### ➕ Tạo tour mới")

    with st.form("new_tour"):
        c1, c2 = st.columns(2)

        tour_name = c1.text_input(
            "Tên tour *",
            placeholder="Ví dụ: Vũng Tàu 2N1Đ"
        )

        destination = c2.text_input(
            "Điểm đến *",
            placeholder="Ví dụ: Vũng Tàu"
        )

        c3, c4, c5 = st.columns(3)

        travel_date = c3.date_input(
            "Ngày đi",
            value=date.today()
        )

        meeting_time = c4.time_input(
            "Giờ tập trung",
            value=time(7, 0)
        )

        guests = c5.number_input(
            "Số khách",
            min_value=1,
            max_value=10000,
            value=20,
            step=1
        )

        c6, c7, c8 = st.columns(3)

        pickup = c6.text_input("Điểm đón", "TP.HCM")

        language = c7.selectbox(
            "Ngoại ngữ khách",
            ["Tiếng Việt", "Tiếng Anh", "Tiếng Hàn", "Tiếng Trung", "Khác"]
        )

        tour_type = c8.selectbox(
            "Loại tour",
            ["Đoàn", "Khách lẻ", "MICE", "VIP", "Inbound"]
        )

        note = st.text_area(
            "Ghi chú",
            placeholder="Yêu cầu đặc biệt của đoàn..."
        )

        submit = st.form_submit_button(
            "➕ TẠO TOUR",
            use_container_width=True,
            type="primary"
        )

        if submit:
            if not tour_name.strip() or not destination.strip():
                st.error("Vui lòng nhập đầy đủ Tên tour và Điểm đến.")
            else:
                code = make_id("TOUR")

                new_row = pd.DataFrame([{
                    "Mã tour": code,
                    "Tên tour": tour_name.strip(),
                    "Ngày đi": travel_date.strftime("%Y-%m-%d"),
                    "Giờ tập trung": meeting_time.strftime("%H:%M"),
                    "Điểm đón": pickup.strip(),
                    "Điểm đến": destination.strip(),
                    "Số khách": guests,
                    "Ngoại ngữ khách": language,
                    "Loại tour": tour_type,
                    "HDV": "",
                    "Mã HDV": "",
                    "Trạng thái": "Chờ phân công",
                    "Ghi chú": note.strip()
                }])

                st.session_state.tours = pd.concat(
                    [st.session_state.tours, new_row],
                    ignore_index=True
                )

                add_log(
                    "Tạo tour",
                    code,
                    f"Tạo tour {tour_name.strip()}"
                )

                st.success(f"Đã tạo tour {code}.")
                st.rerun()

    st.markdown("### 🔄 Cập nhật trạng thái tour")

    if not tours.empty:
        update_code = st.selectbox(
            "Chọn mã tour",
            tours["Mã tour"].tolist(),
            key="update_tour"
        )

        update_idx = st.session_state.tours.index[
            st.session_state.tours["Mã tour"] == update_code
        ][0]

        new_status = st.selectbox(
            "Trạng thái mới",
            ["Chờ phân công", "Đã phân công", "Đang thực hiện", "Hoàn thành", "Đã hủy"]
        )

        if st.button("💾 CẬP NHẬT TRẠNG THÁI", use_container_width=True):
            old_status = st.session_state.tours.loc[update_idx, "Trạng thái"]
            st.session_state.tours.loc[update_idx, "Trạng thái"] = new_status

            if new_status in ["Hoàn thành", "Đã hủy"]:
                guide_code = st.session_state.tours.loc[update_idx, "Mã HDV"]

                if guide_code:
                    guide_matches = st.session_state.guides.index[
                        st.session_state.guides["Mã HDV"] == guide_code
                    ]

                    if len(guide_matches) > 0:
                        st.session_state.guides.loc[
                            guide_matches[0], "Trạng thái"
                        ] = "Sẵn sàng"

            add_log(
                "Cập nhật tour",
                update_code,
                f"{old_status} → {new_status}"
            )

            st.success("Đã cập nhật.")
            st.rerun()

# ============================================================
# DANH SÁCH HDV
# ============================================================
elif menu == "👤 Danh sách HDV":

    st.markdown('<div class="section-title">👤 Quản lý hướng dẫn viên</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Tổng HDV",
        len(guides)
    )

    c2.metric(
        "Sẵn sàng",
        int((guides["Trạng thái"] == "Sẵn sàng").sum())
    )

    c3.metric(
        "Đang bận",
        int((guides["Trạng thái"] == "Bận").sum())
    )

    st.dataframe(
        guides,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("### ➕ Thêm hướng dẫn viên")

    with st.form("new_guide"):
        c1, c2 = st.columns(2)

        guide_name = c1.text_input("Họ tên HDV *")
        phone = c2.text_input("Số điện thoại")

        c3, c4 = st.columns(2)

        language = c3.multiselect(
            "Ngoại ngữ",
            ["Tiếng Việt", "Tiếng Anh", "Tiếng Hàn", "Tiếng Trung", "Tiếng Nhật"],
            default=["Tiếng Việt"]
        )

        route = c4.text_input(
            "Chuyên tuyến",
            placeholder="Ví dụ: Vũng Tàu - Côn Đảo"
        )

        c5, c6 = st.columns(2)

        experience = c5.number_input(
            "Kinh nghiệm (năm)",
            min_value=0,
            max_value=50,
            value=1
        )

        status = c6.selectbox(
            "Trạng thái",
            ["Sẵn sàng", "Bận", "Nghỉ phép"]
        )

        note = st.text_input("Ghi chú")

        add_guide = st.form_submit_button(
            "➕ THÊM HDV",
            use_container_width=True,
            type="primary"
        )

        if add_guide:
            if not guide_name.strip():
                st.error("Vui lòng nhập họ tên HDV.")
            else:
                code = make_id("HDV")

                new_guide = pd.DataFrame([{
                    "Mã HDV": code,
                    "Họ tên": guide_name.strip(),
                    "SĐT": phone.strip(),
                    "Ngoại ngữ": ", ".join(language),
                    "Chuyên tuyến": route.strip(),
                    "Kinh nghiệm (năm)": experience,
                    "Trạng thái": status,
                    "Ghi chú": note.strip()
                }])

                st.session_state.guides = pd.concat(
                    [st.session_state.guides, new_guide],
                    ignore_index=True
                )

                add_log(
                    "Thêm HDV",
                    "",
                    f"Thêm HDV {guide_name.strip()}"
                )

                st.success(f"Đã thêm HDV {guide_name.strip()}.")
                st.rerun()

# ============================================================
# LỊCH SỬ
# ============================================================
elif menu == "📋 Lịch sử điều hành":

    st.markdown('<div class="section-title">📋 Nhật ký điều hành</div>', unsafe_allow_html=True)

    logs = st.session_state.logs.copy()

    st.dataframe(
        logs,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇️ TẢI NHẬT KÝ CSV",
        logs.to_csv(index=False).encode("utf-8-sig"),
        "nhat_ky_dieu_hanh.csv",
        "text/csv",
        use_container_width=True
    )

# ============================================================
# FOOTER
# ============================================================
st.divider()

st.caption(
    "🧭 GuideFlow • Phân luồng hướng dẫn viên nội bộ • "
    f"Cập nhật phiên: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
)
