"""
FinanceTracker – app.py (archivo único, sin dependencias locales)
"""

import uuid
import hashlib
import base64
import json
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ═══════════════════════════════════════════════════════════════════════════════
#  GITHUB STORAGE  (antes en storage.py)
# ═══════════════════════════════════════════════════════════════════════════════

class GitHubStorage:
    USERS_PATH        = "data/users.json"
    TRANSACTIONS_PATH = "data/transactions.json"

    def __init__(self):
        self.token   = st.secrets["github"]["token"]
        self.repo    = st.secrets["github"]["repo"]
        self.branch  = st.secrets["github"].get("branch", "main")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept":        "application/vnd.github.v3+json",
        }
        self._base = f"https://api.github.com/repos/{self.repo}/contents"

    def _get(self, path):
        url = f"{self._base}/{path}"
        r   = requests.get(url, headers=self.headers, timeout=10)
        if r.status_code == 200:
            raw  = r.json()
            text = base64.b64decode(raw["content"]).decode("utf-8")
            return json.loads(text), raw["sha"]
        return None, None

    def _put(self, path, data, sha=None, message=""):
        url     = f"{self._base}/{path}"
        message = message or f"Update {path} [{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}]"
        encoded = base64.b64encode(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")
        body = {"message": message, "content": encoded, "branch": self.branch}
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=self.headers, json=body, timeout=15)
        return r.status_code in (200, 201)

    def get_users(self):
        data, sha = self._get(self.USERS_PATH)
        return (data or {}), sha

    def save_users(self, users, sha=None):
        return self._put(self.USERS_PATH, users, sha, "Update users")

    def get_transactions(self):
        data, sha = self._get(self.TRANSACTIONS_PATH)
        return (data or []), sha

    def save_transactions(self, transactions, sha=None):
        return self._put(self.TRANSACTIONS_PATH, transactions, sha, "Update transactions")

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="FinanceTracker 💰",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

SIN_ASIGNAR = "📌 Sin asignar"

DEFAULT_CATEGORIES = {
    "Gasto": [
        "🍽️ Alimentación", "🚗 Transporte", "🏠 Vivienda / Arriendo",
        "💊 Salud", "🎬 Entretenimiento", "📚 Educación",
        "👕 Ropa y calzado", "💡 Servicios públicos", "🐾 Mascotas",
        "✈️ Viajes", "🎁 Regalos", "📱 Tecnología / Suscripciones",
        "🏋️ Deporte y bienestar", "💄 Cuidado personal", "🔧 Reparaciones",
    ],
    "Ingreso": [
        "💼 Salario", "🖥️ Freelance / Consultoría", "📈 Rendimientos / Dividendos",
        "🏠 Arriendo recibido", "🎁 Regalo recibido", "💰 Bonificación / Prima", "💵 Ventas",
    ],
    "Inversión": [
        "📈 Acciones / ETF", "₿ Criptomonedas", "🏠 Bienes raíces",
        "🏦 CDT / Fondos de inversión", "💱 Divisas / Forex", "🥇 Commodities / Oro",
    ],
}

TYPE_COLORS = {"Gasto": "#FF6B6B", "Ingreso": "#51CF66", "Inversión": "#339AF0"}

MONTHS_ES = {
    1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril",
    5:"Mayo", 6:"Junio", 7:"Julio", 8:"Agosto",
    9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _hash(password):
    return hashlib.sha256(f"FinanceTracker_s4lt_2024!{password}".encode()).hexdigest()

def _greeting(user):
    trat = user.get("tratamiento", "")
    nombre = user.get("nombre", "")
    return f"Hola, {trat} {nombre}! 👋" if trat else f"Hola, {nombre}! 👋"

def _user_categories(user):
    cats = user.get("categories", {})
    result = {}
    for tipo in DEFAULT_CATEGORIES:
        lista = list(cats.get(tipo, DEFAULT_CATEGORIES[tipo]))
        if SIN_ASIGNAR not in lista:
            lista.append(SIN_ASIGNAR)
        result[tipo] = lista
    return result

def _safe_category(category, user_cats, trans_type):
    if not category:
        return SIN_ASIGNAR
    return category if category in user_cats.get(trans_type, []) else SIN_ASIGNAR

def _init_session():
    for k, v in {
        "logged_in": False, "username": None, "user_data": None,
        "page": "home", "auth_mode": "landing", "storage": None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════════════
#  CSS RESPONSIVE
# ═══════════════════════════════════════════════════════════════════════════════

def _inject_css():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #f0f2f6; }
    [data-testid="stSidebar"]          { background: #1e1e2e; }
    [data-testid="stSidebar"] *        { color: #cdd6f4 !important; }

    @media (max-width: 768px) {
        [data-testid="stSidebar"] { min-width:200px!important; max-width:240px!important; }
        [data-testid="stAppViewBlockContainer"] { padding:0.5rem 0.6rem!important; }
        [data-testid="stHorizontalBlock"] { flex-wrap:wrap!important; }
        [data-testid="stHorizontalBlock"] > [data-testid="stVerticalBlock"] {
            min-width:100%!important; flex:1 1 100%!important;
        }
        .stButton > button { min-height:48px!important; font-size:1rem!important; }
        .stTextInput input, .stNumberInput input { min-height:44px!important; font-size:1rem!important; }
        .main-header h1 { font-size:1.4rem!important; }
        .main-header    { padding:1.2rem 1rem!important; }
    }

    .main-header {
        background: linear-gradient(135deg,#667eea 0%,#764ba2 100%);
        padding:2rem 2.5rem; border-radius:16px; color:white;
        margin-bottom:1.5rem; box-shadow:0 8px 32px rgba(102,126,234,.35);
    }
    .main-header h1 { margin:0; font-size:2rem; }
    .main-header p  { margin:.4rem 0 0; opacity:.85; }

    .sidebar-user {
        background:linear-gradient(135deg,#667eea,#764ba2);
        padding:1.1rem .9rem; border-radius:14px; text-align:center; margin-bottom:1rem;
    }
    .sidebar-user .avatar { font-size:2rem; }
    .sidebar-user .name   { font-weight:700; font-size:.9rem; margin-top:.3rem; color:#fff!important; }
    .sidebar-user .handle { font-size:.72rem; opacity:.8; color:#fff!important; }

    .tx-card {
        display:flex; justify-content:space-between; align-items:center;
        padding:.75rem 1rem; background:white; border-radius:10px;
        margin:.35rem 0; box-shadow:0 1px 6px rgba(0,0,0,.07);
    }
    @media (max-width:480px) {
        .tx-card { flex-direction:column; align-items:flex-start; gap:.4rem; }
        .tx-card > div:last-child { text-align:left!important; }
    }

    [data-testid="metric-container"] {
        background:white; border-radius:12px; padding:.9rem 1rem;
        box-shadow:0 2px 8px rgba(0,0,0,.07);
    }
    .stButton > button { border-radius:8px!important; font-weight:600!important; }
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div { border-radius:8px!important; }

    .cat-pill {
        display:inline-flex; align-items:center; gap:.4rem;
        background:white; border:1.5px solid #e2e8f0; border-radius:20px;
        padding:.35rem .75rem; margin:.2rem; font-size:.87rem;
    }
    </style>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def _render_sidebar():
    user = st.session_state.user_data
    with st.sidebar:
        st.markdown(
            f"""<div class="sidebar-user">
                <div class="avatar">👤</div>
                <div class="name">{_greeting(user)}</div>
                <div class="handle">@{st.session_state.username}</div>
               </div>""",
            unsafe_allow_html=True,
        )
        st.markdown("### Menú")
        for label, key in {
            "🏠 Inicio":            "home",
            "➕ Nueva transacción": "add",
            "📋 Mis transacciones": "list",
            "📊 Dashboard":         "dashboard",
            "🏷️ Mis categorías":    "categories",
        }.items():
            if st.button(label, use_container_width=True,
                         type="primary" if st.session_state.page == key else "secondary",
                         key=f"nav_{key}"):
                st.session_state.page = key
                st.rerun()
        st.markdown("---")
        if st.button("🚪 Cerrar sesión", use_container_width=True, key="btn_logout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
#  PÁGINAS PÚBLICAS
# ═══════════════════════════════════════════════════════════════════════════════

_HIDE_SIDEBAR = "<style>[data-testid='stSidebar']{display:none!important;}</style>"

def page_landing():
    st.markdown(_HIDE_SIDEBAR, unsafe_allow_html=True)
    st.markdown("""
        <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                    padding:3rem 1.5rem 2.8rem;border-radius:20px;text-align:center;
                    color:white;margin-bottom:2rem;box-shadow:0 12px 40px rgba(102,126,234,.4);">
            <div style="font-size:4rem;margin-bottom:.4rem;">💰</div>
            <h1 style="font-size:2.2rem;margin:0;">FinanceTracker</h1>
            <p style="font-size:1rem;opacity:.88;margin:.6rem auto 0;max-width:460px;">
                Tu gestor de finanzas personal · gastos, ingresos e inversiones
                de forma privada y segura.
            </p>
        </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑  Iniciar sesión", use_container_width=True, type="primary", key="land_login"):
            st.session_state.auth_mode = "login"; st.rerun()
    with col2:
        if st.button("✨  Crear cuenta", use_container_width=True, type="secondary", key="land_register"):
            st.session_state.auth_mode = "register"; st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;color:#667eea;margin-bottom:1rem;'>¿Qué puedes hacer?</h3>",
                unsafe_allow_html=True)

    cols = st.columns(2)
    for i, (icon, title, desc) in enumerate([
        ("🔐", "Privado",         "Cada usuario ve solo sus propios datos."),
        ("📝", "Registra todo",   "Gastos, ingresos e inversiones categorizados."),
        ("📊", "Dashboard",       "Gráficas interactivas y filtros por período."),
        ("🏷️", "Tus categorías", "Personaliza y organiza las categorías a tu gusto."),
    ]):
        with cols[i % 2]:
            st.markdown(
                f"""<div style="background:white;border-radius:14px;padding:1.1rem 1rem;
                                text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.08);margin-bottom:.8rem;">
                        <div style="font-size:1.8rem;">{icon}</div>
                        <h4 style="color:#1a1a2e;margin:.4rem 0 .2rem;font-size:.93rem;">{title}</h4>
                        <p style="color:#666;font-size:.82rem;line-height:1.45;margin:0;">{desc}</p>
                    </div>""", unsafe_allow_html=True)


def page_login():
    st.markdown(_HIDE_SIDEBAR, unsafe_allow_html=True)
    _, col, _ = st.columns([0.5, 3, 0.5])
    with col:
        st.markdown("""<div style="text-align:center;padding:1.5rem 0 1rem;">
            <div style="font-size:3rem;">💰</div>
            <h2 style="color:#667eea;margin:.2rem 0 0;">Iniciar sesión</h2>
            <p style="color:#888;">Bienvenido/a de vuelta</p></div>""", unsafe_allow_html=True)

        username = st.text_input("👤 Usuario", key="li_user", placeholder="tu_usuario")
        password = st.text_input("🔒 Contraseña", type="password", key="li_pass", placeholder="••••••••")
        st.markdown("")

        if st.button("Entrar →", use_container_width=True, type="primary", key="btn_login"):
            if not username or not password:
                st.error("Completa todos los campos.")
            else:
                users, _ = st.session_state.storage.get_users()
                if username in users and users[username]["password"] == _hash(password):
                    st.session_state.logged_in = True
                    st.session_state.username  = username
                    st.session_state.user_data = users[username]
                    st.session_state.page      = "home"
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Volver al inicio", key="login_back", use_container_width=True):
            st.session_state.auth_mode = "landing"; st.rerun()
        st.markdown("<p style='text-align:center;color:#888;font-size:.88rem;margin-top:.8rem;'>¿No tienes cuenta?</p>",
                    unsafe_allow_html=True)
        if st.button("✨ Crear cuenta gratis", key="login_to_reg", use_container_width=True):
            st.session_state.auth_mode = "register"; st.rerun()


def page_register():
    st.markdown(_HIDE_SIDEBAR, unsafe_allow_html=True)
    _, col, _ = st.columns([0.5, 3, 0.5])
    with col:
        st.markdown("""<div style="text-align:center;padding:1.5rem 0 1rem;">
            <div style="font-size:3rem;">✨</div>
            <h2 style="color:#667eea;margin:.2rem 0 0;">Crear cuenta</h2>
            <p style="color:#888;">Tus datos son completamente privados</p></div>""", unsafe_allow_html=True)

        r_nombre = st.text_input("📝 Nombre(s)", key="r_nombre", placeholder="Juan Carlos")
        r_trat   = st.selectbox("¿Cómo le gusta que le digan?",
                                 ["(ninguno)", "Señor", "Señora", "Dr.", "Dra."], key="r_trat")
        r_user   = st.text_input("👤 Usuario", key="r_user", placeholder="juancarlos123  (mín. 3 caracteres)")
        r_email  = st.text_input("📧 Email (opcional)", key="r_email", placeholder="juan@email.com")

        c3, c4 = st.columns(2)
        with c3:
            r_pass1 = st.text_input("🔒 Contraseña", type="password", key="r_pass1", placeholder="Mínimo 6 caracteres")
        with c4:
            r_pass2 = st.text_input("🔒 Confirmar", type="password", key="r_pass2", placeholder="Repite la contraseña")

        r_currency = st.selectbox("💱 Moneda",
                                   ["COP 🇨🇴", "USD 🇺🇸", "EUR 🇪🇺", "MXN 🇲🇽", "ARS 🇦🇷", "BRL 🇧🇷"],
                                   key="r_currency")
        st.markdown("")

        if st.button("Crear mi cuenta →", use_container_width=True, type="primary", key="btn_reg"):
            errs = []
            if not r_nombre:        errs.append("El nombre es requerido.")
            if len(r_user) < 3:    errs.append("El usuario necesita al menos 3 caracteres.")
            if len(r_pass1) < 6:   errs.append("La contraseña necesita al menos 6 caracteres.")
            if r_pass1 != r_pass2: errs.append("Las contraseñas no coinciden.")

            if errs:
                for e in errs: st.error(e)
            else:
                storage = st.session_state.storage
                users, sha = storage.get_users()
                if r_user in users:
                    st.error("Ese nombre de usuario ya existe.")
                else:
                    user_cats = {t: list(l) + [SIN_ASIGNAR] for t, l in DEFAULT_CATEGORIES.items()}
                    users[r_user] = {
                        "nombre":      r_nombre,
                        "tratamiento": "" if r_trat == "(ninguno)" else r_trat,
                        "email":       r_email,
                        "password":    _hash(r_pass1),
                        "currency":    r_currency,
                        "categories":  user_cats,
                        "created_at":  datetime.utcnow().isoformat(),
                    }
                    if storage.save_users(users, sha):
                        st.success("✅ ¡Cuenta creada! Inicia sesión para entrar.")
                        st.balloons()
                    else:
                        st.error("Error al guardar. Revisa el token de GitHub.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Volver al inicio", key="reg_back", use_container_width=True):
            st.session_state.auth_mode = "landing"; st.rerun()
        st.markdown("<p style='text-align:center;color:#888;font-size:.88rem;margin-top:.8rem;'>¿Ya tienes cuenta?</p>",
                    unsafe_allow_html=True)
        if st.button("🔑 Iniciar sesión", key="reg_to_login", use_container_width=True):
            st.session_state.auth_mode = "login"; st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
#  PÁGINAS AUTENTICADAS
# ═══════════════════════════════════════════════════════════════════════════════

def page_home():
    user = st.session_state.user_data
    now  = datetime.now()
    st.markdown(f"""<div class="main-header">
        <h1>{_greeting(user)}</h1>
        <p>Tu gestor de finanzas · {now.strftime("%d/%m/%Y")}</p></div>""",
        unsafe_allow_html=True)

    transactions, _ = st.session_state.storage.get_transactions()
    df_all  = pd.DataFrame(transactions) if transactions else pd.DataFrame()
    df_user = pd.DataFrame()

    if not df_all.empty:
        df_user = df_all[df_all["username"] == st.session_state.username].copy()
        df_user["date"] = pd.to_datetime(df_user["date"])

    df_month = (df_user[(df_user["date"].dt.year == now.year) &
                         (df_user["date"].dt.month == now.month)]
                if not df_user.empty else pd.DataFrame())

    st.markdown(f"### 📅 {MONTHS_ES[now.month]} {now.year}")
    ing = df_month[df_month["type"] == "Ingreso"   ]["amount"].sum() if not df_month.empty else 0
    gas = df_month[df_month["type"] == "Gasto"     ]["amount"].sum() if not df_month.empty else 0
    inv = df_month[df_month["type"] == "Inversión" ]["amount"].sum() if not df_month.empty else 0
    bal = ing - gas - inv

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💚 Ingresos",    f"${ing:,.0f}")
    c2.metric("🔴 Gastos",      f"${gas:,.0f}")
    c3.metric("🔵 Inversiones", f"${inv:,.0f}")
    c4.metric("🟡 Balance",     f"${bal:,.0f}", delta=f"{bal/ing*100:.1f}% del ingreso" if ing else None)

    st.markdown("### 🕐 Últimas transacciones")
    if df_user.empty:
        st.info("Aún no tienes transacciones. ¡Empieza agregando una!")
        if st.button("➕ Agregar primera transacción", type="primary"):
            st.session_state.page = "add"; st.rerun()
        return

    user_cats = _user_categories(user)
    for _, row in df_user.sort_values("date", ascending=False).head(8).iterrows():
        color    = TYPE_COLORS.get(row["type"], "#888")
        desc     = row.get("description", "") or ""
        fecha    = pd.Timestamp(row["date"]).strftime("%d/%m/%Y")
        category = _safe_category(row.get("category", ""), user_cats, row["type"])
        st.markdown(
            f"""<div class="tx-card" style="border-left:4px solid {color};">
                <div><strong>{category}</strong>
                {"<br><span style='color:#888;font-size:.82rem;'>" + desc + "</span>" if desc else ""}
                </div>
                <div style="text-align:right;">
                    <strong style="color:{color};font-size:1.05rem;">${row['amount']:,.0f}</strong>
                    <br><span style="color:#aaa;font-size:.8rem;">{fecha} · {row['type']}</span>
                </div></div>""",
            unsafe_allow_html=True)


def page_add():
    st.markdown("## ➕ Nueva Transacción")
    user      = st.session_state.user_data
    user_cats = _user_categories(user)

    trans_type = st.selectbox("📂 Tipo", list(DEFAULT_CATEGORIES.keys()), key="add_type")
    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox("🏷️ Categoría", user_cats.get(trans_type, [SIN_ASIGNAR]), key="add_cat")
    with col2:
        amount = st.number_input("💵 Monto", min_value=0.0, step=1000.0, format="%.2f", key="add_amount")

    trans_date  = st.date_input("📅 Fecha", value=date.today(), key="add_date")
    description = st.text_input("📝 Descripción (opcional)",
                                 placeholder="Ej.: Mercado semanal, pago Netflix…", key="add_desc")
    st.markdown("")

    if st.button("💾 Guardar transacción", type="primary", use_container_width=True, key="btn_save"):
        if amount <= 0:
            st.error("El monto debe ser mayor que 0."); return
        storage = st.session_state.storage
        transactions, sha = storage.get_transactions()
        transactions.append({
            "id":          str(uuid.uuid4()),
            "username":    st.session_state.username,
            "type":        trans_type,
            "amount":      float(amount),
            "category":    category or SIN_ASIGNAR,
            "date":        trans_date.isoformat(),
            "description": description.strip(),
            "created_at":  datetime.utcnow().isoformat(),
        })
        if storage.save_transactions(transactions, sha):
            st.success(f"✅ Guardado: **{category}** — ${amount:,.2f}")
            st.balloons()
        else:
            st.error("No se pudo guardar. Revisa la configuración de GitHub.")


def page_list():
    st.markdown("## 📋 Mis Transacciones")
    transactions, _ = st.session_state.storage.get_transactions()
    if not transactions:
        st.info("No tienes transacciones registradas."); return

    df_all  = pd.DataFrame(transactions)
    df_user = df_all[df_all["username"] == st.session_state.username].copy()
    if df_user.empty:
        st.info("No tienes transacciones registradas."); return

    user_cats = _user_categories(st.session_state.user_data)
    df_user["category"] = df_user.apply(
        lambda r: _safe_category(r.get("category", ""), user_cats, r["type"]), axis=1)
    df_user["date"] = pd.to_datetime(df_user["date"])
    df_user.sort_values("date", ascending=False, inplace=True)

    with st.expander("🔍 Filtros", expanded=False):
        f_type  = st.multiselect("Tipo", list(DEFAULT_CATEGORIES.keys()),
                                  default=list(DEFAULT_CATEGORIES.keys()), key="fl_type")
        years   = sorted(df_user["date"].dt.year.unique(), reverse=True)
        f_year  = st.multiselect("Año", years, default=list(years[:1]), key="fl_year")
        f_month = st.multiselect("Mes", list(MONTHS_ES.values()), key="fl_month")
        f_search= st.text_input("🔎 Buscar", key="fl_search", placeholder="Palabra clave…")

    filtered = df_user.copy()
    if f_type:   filtered = filtered[filtered["type"].isin(f_type)]
    if f_year:   filtered = filtered[filtered["date"].dt.year.isin(f_year)]
    if f_month:
        nums = [k for k, v in MONTHS_ES.items() if v in f_month]
        filtered = filtered[filtered["date"].dt.month.isin(nums)]
    if f_search: filtered = filtered[filtered["description"].fillna("").str.contains(f_search, case=False)]

    ing = filtered[filtered["type"] == "Ingreso"   ]["amount"].sum()
    gas = filtered[filtered["type"] == "Gasto"     ]["amount"].sum()
    inv = filtered[filtered["type"] == "Inversión" ]["amount"].sum()

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("💚 Ingresos",    f"${ing:,.0f}")
    mc2.metric("🔴 Gastos",      f"${gas:,.0f}")
    mc3.metric("🔵 Inversiones", f"${inv:,.0f}")
    mc4.metric("🟡 Balance",     f"${ing-gas-inv:,.0f}")

    st.markdown(f"**{len(filtered):,} transacciones**")
    show = filtered[["date","type","category","amount","description"]].copy()
    show["date"]   = show["date"].dt.strftime("%d/%m/%Y")
    show["amount"] = show["amount"].apply(lambda x: f"${x:,.2f}")
    show.columns   = ["Fecha","Tipo","Categoría","Monto","Descripción"]
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Descargar CSV", data=show.to_csv(index=False).encode("utf-8"),
                       file_name=f"transacciones_{datetime.now():%Y%m%d}.csv", mime="text/csv")


def page_dashboard():
    st.markdown("## 📊 Dashboard Financiero")
    transactions, _ = st.session_state.storage.get_transactions()
    if not transactions:
        st.info("Sin datos para mostrar."); return

    df_all  = pd.DataFrame(transactions)
    df_user = df_all[df_all["username"] == st.session_state.username].copy()
    if df_user.empty:
        st.info("Sin transacciones para mostrar."); return

    user_cats = _user_categories(st.session_state.user_data)
    df_user["category"] = df_user.apply(
        lambda r: _safe_category(r.get("category",""), user_cats, r["type"]), axis=1)
    df_user["date"] = pd.to_datetime(df_user["date"])

    vista = st.radio("Modo de vista", ["Año / Mes", "Rolling N meses"], horizontal=True)
    years = sorted(df_user["date"].dt.year.unique(), reverse=True)
    sel_year = years[0]; sel_month = "Todos"; rolling_months = 6

    c1, c2 = st.columns(2)
    with c1:
        if vista == "Año / Mes":
            sel_year  = st.selectbox("Año", years, key="db_year")
            sel_month = st.selectbox("Mes", ["Todos"] + list(MONTHS_ES.values()), key="db_month")
        else:
            rolling_months = st.slider("Últimos N meses", 1, 36, 6, key="db_rolling")
    with c2:
        sel_types = st.multiselect("Tipos", list(DEFAULT_CATEGORIES.keys()),
                                    default=list(DEFAULT_CATEGORIES.keys()), key="db_types")

    if vista == "Año / Mes":
        filtered = df_user[df_user["date"].dt.year == sel_year].copy()
        if sel_month != "Todos":
            m_num    = [k for k,v in MONTHS_ES.items() if v == sel_month][0]
            filtered = filtered[filtered["date"].dt.month == m_num]
    else:
        filtered = df_user[df_user["date"] >= datetime.now() - timedelta(days=rolling_months*30)].copy()

    if sel_types:
        filtered = filtered[filtered["type"].isin(sel_types)]
    if filtered.empty:
        st.warning("No hay datos para el período seleccionado."); return

    ing  = filtered[filtered["type"] == "Ingreso"   ]["amount"].sum()
    gas  = filtered[filtered["type"] == "Gasto"     ]["amount"].sum()
    inv  = filtered[filtered["type"] == "Inversión" ]["amount"].sum()
    bal  = ing - gas - inv
    tasa = (ing - gas) / ing * 100 if ing else 0

    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("💚 Ingresos",      f"${ing:,.0f}")
    k2.metric("🔴 Gastos",        f"${gas:,.0f}")
    k3.metric("🔵 Inversiones",   f"${inv:,.0f}")
    k4.metric("🟡 Balance neto",  f"${bal:,.0f}", delta=f"{bal/ing*100:.1f}% ingreso" if ing else None)
    k5.metric("📊 Tasa de ahorro", f"{tasa:.1f}%")
    st.markdown("---")

    filtered = filtered.copy()
    filtered["mes"] = filtered["date"].dt.to_period("M").astype(str)

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown("#### 📈 Evolución mensual")
        monthly = filtered.groupby(["mes","type"])["amount"].sum().reset_index().sort_values("mes")
        fig1 = px.bar(monthly, x="mes", y="amount", color="type", barmode="group",
                      color_discrete_map=TYPE_COLORS, labels={"amount":"Monto","mes":"Mes","type":"Tipo"})
        fig1.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            legend=dict(orientation="h",y=1.12), margin=dict(l=0,r=0,t=10,b=0), height=320)
        st.plotly_chart(fig1, use_container_width=True)

    with r1c2:
        st.markdown("#### 🥧 Distribución por tipo")
        fig2 = px.pie(filtered.groupby("type")["amount"].sum().reset_index(),
                      values="amount", names="type", color="type",
                      color_discrete_map=TYPE_COLORS, hole=0.42)
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=10,b=0),
                            height=320, legend=dict(orientation="h",y=-0.15))
        st.plotly_chart(fig2, use_container_width=True)

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown("#### 🏷️ Top categorías de Gasto")
        gdf = filtered[filtered["type"] == "Gasto"]
        if not gdf.empty:
            cat_g = gdf.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=True).tail(10)
            fig3  = px.bar(cat_g, x="amount", y="category", orientation="h",
                           color="amount", color_continuous_scale="Reds",
                           labels={"amount":"Monto","category":"Categoría"})
            fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                margin=dict(l=0,r=0,t=10,b=0), height=320,
                                coloraxis_showscale=False, showlegend=False)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Sin gastos en este período.")

    with r2c2:
        st.markdown("#### 💹 Balance acumulado")
        fs = filtered.sort_values("date").copy()
        fs["delta"] = fs.apply(lambda r: r["amount"] if r["type"]=="Ingreso" else -r["amount"], axis=1)
        fs["acum"]  = fs["delta"].cumsum()
        fig4 = px.area(fs, x="date", y="acum",
                       labels={"acum":"Balance acumulado","date":"Fecha"},
                       color_discrete_sequence=["#667eea"])
        fig4.update_traces(fill="tozeroy", line_color="#667eea", fillcolor="rgba(102,126,234,.18)")
        fig4.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=0,r=0,t=10,b=0), height=320)
        st.plotly_chart(fig4, use_container_width=True)

    if vista == "Rolling N meses":
        st.markdown("#### 📉 Tendencia rolling")
        pivot = filtered.groupby(["mes","type"])["amount"].sum().unstack(fill_value=0).reset_index()
        fig5  = go.Figure()
        for t, c in TYPE_COLORS.items():
            if t in pivot.columns:
                fig5.add_trace(go.Scatter(x=pivot["mes"], y=pivot[t], name=t,
                                          mode="lines+markers", line=dict(color=c, width=2.5),
                                          marker=dict(size=7)))
        fig5.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            legend=dict(orientation="h"), margin=dict(l=0,r=0,t=0,b=0),
                            height=280, xaxis_title="Mes", yaxis_title="Monto")
        st.plotly_chart(fig5, use_container_width=True)

    st.markdown("#### 💼 Fuentes de Ingreso")
    idf = filtered[filtered["type"] == "Ingreso"]
    if not idf.empty:
        fig6 = px.pie(idf.groupby("category")["amount"].sum().reset_index(),
                      values="amount", names="category",
                      color_discrete_sequence=px.colors.qualitative.Pastel, hole=0.35)
        fig6.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=10,b=0),
                            height=290, legend=dict(orientation="h",y=-0.25))
        st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("Sin ingresos en este período.")


def page_categories():
    st.markdown("## 🏷️ Mis Categorías")
    st.markdown(f"Personaliza las categorías de cada tipo. "
                f"**{SIN_ASIGNAR}** siempre estará disponible como respaldo y no se puede eliminar.")

    storage    = st.session_state.storage
    users, sha = storage.get_users()
    username   = st.session_state.username
    user       = users[username]
    user_cats  = _user_categories(user)
    changed    = False

    for tab, tipo in zip(st.tabs(["🔴 Gasto","💚 Ingreso","🔵 Inversión"]),
                         ["Gasto","Ingreso","Inversión"]):
        with tab:
            current = list(user_cats[tipo])
            cats_display = [c for c in current if c != SIN_ASIGNAR]
            st.markdown(f"**{len(cats_display)} categorías** (+ Sin asignar siempre disponible)")

            for cat in cats_display:
                col_name, col_del = st.columns([8, 1])
                col_name.markdown(f"<div class='cat-pill'>{cat}</div>", unsafe_allow_html=True)
                if col_del.button("✕", key=f"del_{tipo}_{cat}", help=f"Eliminar '{cat}'"):
                    new_list = [c for c in current if c != cat]
                    if SIN_ASIGNAR not in new_list: new_list.append(SIN_ASIGNAR)
                    user_cats[tipo] = new_list
                    changed = True

            st.markdown(
                f"<div class='cat-pill' style='opacity:.45;border-style:dashed;'>"
                f"{SIN_ASIGNAR} 🔒</div>", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**➕ Agregar categoría:**")
            st.caption({"Gasto":"🛒 🛍️ 🏥 🎮 🧾 ⚡",
                        "Ingreso":"💡 🤝 📦 🎓 💎",
                        "Inversión":"🪙 🏗️ 🌱 📊 🎯"}.get(tipo,""))

            nc1, nc2 = st.columns([5, 1])
            with nc1:
                new_cat = st.text_input(f"cat_{tipo}", key=f"new_cat_{tipo}",
                                         placeholder="Ej.: 🛒 Supermercado especial",
                                         label_visibility="collapsed")
            with nc2:
                if st.button("Agregar", key=f"add_cat_{tipo}", type="primary", use_container_width=True):
                    new_cat = new_cat.strip()
                    if not new_cat:
                        st.warning("Escribe el nombre.")
                    elif new_cat in user_cats[tipo]:
                        st.warning("Ya existe.")
                    else:
                        lst = [c for c in user_cats[tipo] if c != SIN_ASIGNAR]
                        lst += [new_cat, SIN_ASIGNAR]
                        user_cats[tipo] = lst
                        changed = True

    if changed:
        user["categories"] = user_cats
        users[username]    = user
        if storage.save_users(users, sha):
            st.session_state.user_data = user
            st.success("✅ Categorías actualizadas.")
            st.rerun()
        else:
            st.error("Error al guardar.")

    st.markdown("---")
    with st.expander("⚠️ Restaurar categorías originales"):
        st.warning("Esto reemplazará todas tus categorías con los valores por defecto.")
        if st.button("Restaurar defaults", type="secondary", key="restore_defaults"):
            reset = {t: list(l) + [SIN_ASIGNAR] for t, l in DEFAULT_CATEGORIES.items()}
            user["categories"] = reset
            users[username]    = user
            if storage.save_users(users, sha):
                st.session_state.user_data = user
                st.success("✅ Categorías restauradas.")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    _init_session()
    _inject_css()

    if st.session_state.storage is None:
        try:
            st.session_state.storage = GitHubStorage()
        except Exception as exc:
            st.error(f"⚠️ Error de configuración: {exc}\n\n"
                     "Verifica los Secrets en Streamlit Cloud.")
            st.stop()

    if not st.session_state.logged_in:
        {"login": page_login, "register": page_register}.get(
            st.session_state.get("auth_mode", "landing"), page_landing)()
        return

    _render_sidebar()
    {"home": page_home, "add": page_add, "list": page_list,
     "dashboard": page_dashboard, "categories": page_categories
     }.get(st.session_state.page, page_home)()

if __name__ == "__main__":
    main()
