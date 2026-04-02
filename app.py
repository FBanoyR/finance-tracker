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

    def get_sessions(self):
        data, sha = self._get("data/sessions.json")
        return (data or {}), sha

    def save_sessions(self, sessions, sha=None):
        return self._put("data/sessions.json", sessions, sha, "Update sessions")

    # ── Groups ────────────────────────────────────────────────────────────────
    def get_group(self, group_id):
        data, sha = self._get(f"data/groups/{group_id}.json")
        return data, sha

    def save_group(self, group_id, data, sha=None):
        return self._put(f"data/groups/{group_id}.json", data, sha, f"Update group {group_id}")

    def get_group_expenses(self, group_id):
        data, sha = self._get(f"data/groups/{group_id}_expenses.json")
        return (data or []), sha

    def save_group_expenses(self, group_id, data, sha=None):
        return self._put(f"data/groups/{group_id}_expenses.json", data, sha, f"Update expenses {group_id}")

    def get_group_settlements(self, group_id):
        data, sha = self._get(f"data/groups/{group_id}_settlements.json")
        return (data or []), sha

    def save_group_settlements(self, group_id, data, sha=None):
        return self._put(f"data/groups/{group_id}_settlements.json", data, sha, f"Update settlements {group_id}")

    def get_user_groups(self, username):
        data, sha = self._get(f"data/user_groups/{username}.json")
        return (data or []), sha

    def save_user_groups(self, username, data, sha=None):
        return self._put(f"data/user_groups/{username}.json", data, sha, f"Update user groups {username}")

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="FinanceTracker 💰",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
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



def _send_reset_email(to_email: str, nombre: str, code: str) -> bool:
    """Envía el código de recuperación usando la librería oficial de Resend."""
    import resend
    try:
        resend.api_key = st.secrets["email"]["resend_api_key"]
    except Exception:
        return False

    body_html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:2rem;">
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);
                    padding:1.5rem;border-radius:14px;text-align:center;color:white;">
            <div style="font-size:2.5rem;">💰</div>
            <h2 style="margin:.3rem 0;">FinanceTracker</h2>
        </div>
        <div style="padding:1.5rem 0;">
            <p>Hola <strong>{nombre}</strong>,</p>
            <p>Recibimos una solicitud para restablecer tu contraseña.</p>
            <p>Tu código de verificación (válido por <strong>15 minutos</strong>) es:</p>
            <div style="background:var(--secondary-background-color);border-radius:12px;padding:1.2rem;
                        text-align:center;margin:1rem 0;">
                <span style="font-size:2.2rem;font-weight:700;letter-spacing:.4rem;
                             color:#667eea;">{code}</span>
            </div>
            <p style="color:var(--text-color);opacity:.6;font-size:.88rem;">
                Si no solicitaste este cambio, puedes ignorar este correo.
            </p>
        </div>
    </div>
    """

    try:
        resend.Emails.send({
            "from":    "FinanceTracker <onboarding@resend.dev>",
            "to":      [to_email],
            "subject": f"[FinanceTracker] Código de recuperación: {code}",
            "html":    body_html,
        })
        return True
    except Exception:
        return False

def _greeting(user):
    trat = user.get("tratamiento", "")
    nombre = user.get("nombre", "")
    return f"Hola, {trat} {nombre}! 👋" if trat else f"Hola, {nombre}! 👋"

def _get_display_name(users_dict, username):
    """Retorna el nombre del usuario; si no hay, retorna el username."""
    udata = users_dict.get(username, {})
    nombre = udata.get("nombre", "").strip()
    return nombre if nombre else username

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

def _get_budgets(user):
    """
    Estructura en users.json:
      "budgets": {
        "Gasto": {
          "bases": [
            {"from": "2024-01", "amount": 2000000},
            {"from": "2025-07", "amount": 1200000}
          ],
          "overrides": {"2025-12": 3000000}
        }
      }
    Compatibilidad: si existe "base" (formato anterior) se migra automáticamente.
    """
    stored = user.get("budgets", {})
    result = {}
    for tipo in DEFAULT_CATEGORIES:
        b = stored.get(tipo, {})
        if "base" in b and "bases" not in b:
            bases = [{"from": "2000-01", "amount": float(b["base"])}] if b.get("base", 0) > 0 else []
        else:
            bases = b.get("bases", [])
        result[tipo] = {
            "bases":     sorted(bases, key=lambda x: x["from"]),
            "overrides": b.get("overrides", {}),
        }
    return result

def _budget_for_month(budgets, tipo, year, month):
    """
    Presupuesto efectivo para un tipo y mes.
    Prioridad:
      1. Override puntual YYYY-MM
      2. Base más reciente cuyo from <= YYYY-MM
      3. 0
    """
    key = f"{year}-{month:02d}"
    b   = budgets.get(tipo, {})
    if key in b.get("overrides", {}):
        return b["overrides"][key]
    bases = sorted(b.get("bases", []), key=lambda x: x["from"], reverse=True)
    for base in bases:
        if base["from"] <= key:
            return base["amount"]
    return 0

def _budget_met(tipo, real, presupuesto):
    """None = sin presupuesto. True = cumplido. False = incumplido."""
    if presupuesto <= 0:
        return None
    return real <= presupuesto if tipo == "Gasto" else real >= presupuesto

def _init_session():
    for k, v in {
        "logged_in": False, "username": None, "user_data": None,
        "page": "home", "auth_mode": "landing", "storage": None,
        "reset_email_sent": False,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════════════
#  PWA META + CSS
# ═══════════════════════════════════════════════════════════════════════════════

def _inject_pwa_meta():
    """
    Inyecta meta tags PWA usando íconos reales de Twemoji CDN (PNG).
    iOS Safari y Android Chrome requieren PNG reales, no data: URIs en el manifest.
    """
    # 💰 = U+1F4B0 → twemoji usa el codepoint en hex sin el U+
    ICON_192 = "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f4b0.png"
    ICON_512 = "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/svg/1f4b0.svg"

    st.markdown(
        f"""
        <meta name="application-name" content="FinanceTracker">
        <meta name="apple-mobile-web-app-title" content="FinanceTracker">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#667eea">

        <link rel="icon" type="image/png" href="{ICON_192}">
        <link rel="apple-touch-icon" href="{ICON_192}">

        <script>
        // Registrar el manifest dinámicamente (funciona en Chrome/Android)
        const manifest = {{
            "name": "FinanceTracker",
            "short_name": "FinanceTracker",
            "description": "Tu gestor de finanzas personal",
            "start_url": window.location.pathname,
            "display": "standalone",
            "background_color": "#667eea",
            "theme_color": "#667eea",
            "orientation": "portrait-primary",
            "icons": [
                {{
                    "src": "{ICON_192}",
                    "sizes": "72x72",
                    "type": "image/png",
                    "purpose": "any"
                }},
                {{
                    "src": "{ICON_512}",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable"
                }}
            ]
        }};
        const blob = new Blob([JSON.stringify(manifest)], {{type: "application/json"}});
        const url  = URL.createObjectURL(blob);
        let link   = document.querySelector("link[rel='manifest']");
        if (!link) {{ link = document.createElement("link"); link.rel = "manifest"; document.head.appendChild(link); }}
        link.href = url;
        </script>
        """,
        unsafe_allow_html=True,
    )


def _inject_css():
    st.markdown("""
    <style>
    /* ── Variables de tema: se adaptan a dark/light automáticamente ── */
    :root {
        --card-bg:        var(--secondary-background-color);
        --card-border:    rgba(128,128,128,0.2);
        --text-main:      var(--text-color);
        --text-muted:     rgba(128,128,128,0.85);
        --shadow-sm:      0 1px 6px rgba(0,0,0,.12);
        --shadow-md:      0 2px 10px rgba(0,0,0,.12);
        --bar-track:      rgba(128,128,128,0.18);
    }

    /* ── Responsive ── */
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
    @media (max-width:480px) {
        .tx-card { flex-direction:column; align-items:flex-start; gap:.4rem; }
        .tx-card > div:last-child { text-align:left!important; }
    }

    /* ── Header principal ── */
    .main-header {
        background: linear-gradient(135deg,#667eea 0%,#764ba2 100%);
        padding:2rem 2.5rem; border-radius:16px; color:white !important;
        margin-bottom:1.5rem; box-shadow:0 8px 32px rgba(102,126,234,.35);
    }
    .main-header h1 { margin:0; font-size:2rem; color:white !important; }
    .main-header p  { margin:.4rem 0 0; opacity:.85; color:white !important; }

    /* ── Sidebar usuario ── */
    .sidebar-user {
        background:linear-gradient(135deg,#667eea,#764ba2);
        padding:1.1rem .9rem; border-radius:14px; text-align:center; margin-bottom:1rem;
    }
    .sidebar-user .avatar { font-size:2rem; }
    .sidebar-user .name   { font-weight:700; font-size:.9rem; margin-top:.3rem; color:#fff!important; }
    .sidebar-user .handle { font-size:.72rem; opacity:.8; color:#fff!important; }

    /* ── Tarjeta de transacción ── */
    .tx-card {
        display:flex; justify-content:space-between; align-items:center;
        padding:.75rem 1rem;
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius:10px;
        margin:.35rem 0;
        box-shadow: var(--shadow-sm);
        color: var(--text-main);
    }

    /* ── Métricas ── */
    [data-testid="metric-container"] {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius:12px; padding:.9rem 1rem;
        box-shadow: var(--shadow-sm);
    }

    /* ── Inputs y botones ── */
    .stButton > button { border-radius:8px!important; font-weight:600!important; }
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div { border-radius:8px!important; }

    /* ── Pills de categoría ── */
    .cat-pill {
        display:inline-flex; align-items:center; gap:.4rem;
        background: var(--card-bg);
        border: 1.5px solid var(--card-border);
        border-radius:20px;
        padding:.35rem .75rem; margin:.2rem; font-size:.87rem;
        color: var(--text-main);
    }

    /* ── Tarjeta de presupuesto ── */
    .budget-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius:14px; padding:1.2rem 1.4rem;
        box-shadow: var(--shadow-md); margin-bottom:.8rem;
        color: var(--text-main);
    }
    .budget-card strong { color: var(--text-main) !important; }
    .budget-card span   { color: var(--text-main) !important; }

    /* ── Barra de progreso ── */
    .budget-bar-bg {
        background: var(--bar-track);
        border-radius:8px; height:12px; margin:.5rem 0; overflow:hidden;
    }
    .budget-bar-fill { height:100%; border-radius:8px; transition:width .4s; }

    /* ── Semáforo de presupuesto ── */
    .semaforo-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius:12px; padding:1rem 1.4rem;
        box-shadow: var(--shadow-sm); margin-top:.5rem;
        color: var(--text-main);
    }

    /* ── Ocultar toolbar y decoraciones de Streamlit ── */
    [data-testid="stToolbar"]      { display:none !important; }
    [data-testid="stDecoration"]   { display:none !important; }
    [data-testid="collapsedControl"]{ display:none !important; }
    #MainMenu                      { display:none !important; }
    footer                         { display:none !important; }
    /* Ocultar botones Streamlit del bottom nav (solo visible la versión HTML) */
    [data-testid="stBottom"] { display:none !important; }
    /* Ocultar sidebar completamente cuando está logueado */
    [data-testid="stSidebar"]      { display:none !important; }

    /* ── Espaciado para el bottom nav ── */
    [data-testid="stAppViewBlockContainer"] { padding-bottom: 80px !important; }
    /* Los botones Streamlit del nav son funcionales pero invisibles */
    div[data-testid="stHorizontalBlock"]:has(button[key*="bnav_"]) { height:0 !important; overflow:hidden !important; margin:0 !important; padding:0 !important; opacity:0 !important; pointer-events:none !important; }

    /* ── Bottom navigation bar: Streamlit buttons estilizados como tab bar ── */
    /* Contenedor del nav (las columnas de los botones) */
    [data-testid="stAppViewBlockContainer"] { padding-bottom: 90px !important; }

    /* Fijar la última fila de columnas (el nav) al fondo */
    div[data-testid="stVerticalBlock"] > div:last-child
        > div[data-testid="stHorizontalBlock"]:last-of-type {
        position: fixed !important;
        bottom: 0 !important; left: 0 !important; right: 0 !important;
        background: var(--card-bg) !important;
        border-top: 1px solid var(--card-border) !important;
        padding: 6px 8px 10px !important;
        z-index: 9999 !important;
        box-shadow: 0 -2px 16px rgba(0,0,0,.10) !important;
        margin: 0 !important;
    }

    /* Estilo de cada botón del nav */
    div[data-testid="stVerticalBlock"] > div:last-child
        > div[data-testid="stHorizontalBlock"]:last-of-type
        button {
        border-radius: 10px !important;
        padding: 4px 2px !important;
        font-size: .7rem !important;
        white-space: pre-line !important;
        line-height: 1.2 !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        min-height: 52px !important;
    }

    /* ── Saludo intermedio ── */
    .greeting-card {
        background: linear-gradient(135deg,#667eea 0%,#764ba2 100%);
        border-radius: 14px;
        padding: 1rem 1.4rem;
        margin-bottom: 1rem;
        color: white;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .greeting-card .g-left { }
    .greeting-card .g-name { font-size: 1.25rem; font-weight: 700; color:white !important; }
    .greeting-card .g-sub  { font-size: .82rem; opacity: .8; margin-top:.1rem; color:white !important; }
    .greeting-card .g-right { text-align:right; }
    .greeting-card .g-date  { font-size: .82rem; opacity: .75; color:white !important; }
    .greeting-card .g-mes   { font-size: .92rem; font-weight:600; color:white !important; }
    </style>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  NAVEGACIÓN (bottom bar + saludo minimalista)
# ═══════════════════════════════════════════════════════════════════════════════

# Páginas que corresponden a cada ícono del bottom nav
_HOME_PAGES = {"home", "dashboard"}
_NAV_ITEMS = [
    ("🏠", "Inicio",       "home"),
    ("➕", "Nuevo",        "add"),
    ("📋", "Movimientos",  "list"),
    ("👥", "Grupos",       "groups"),
    ("⚙️", "Opciones",     "more"),
]

def _render_greeting():
    """Saludo de tamaño medio: ni el bloque enorme, ni solo una línea."""
    user = st.session_state.user_data
    trat = user.get("tratamiento", "")
    nombre = user.get("nombre", "")
    saludo = f"{trat} {nombre}".strip() if trat else nombre
    now    = datetime.now()
    dia_semana = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][now.weekday()]
    st.markdown(
        f"""<div class="greeting-card">
            <div class="g-left">
                <div class="g-name">👋 {saludo}</div>
                <div class="g-sub">Bienvenido/a a tu gestor financiero</div>
            </div>
            <div class="g-right">
                <div class="g-mes">{MONTHS_ES[now.month]} {now.year}</div>
                <div class="g-date">{dia_semana} {now.day}</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

def _render_bottom_nav():
    """
    Bottom nav funcional: botones Streamlit reales estilizados con CSS
    para parecer una barra de navegación inferior.
    """
    page   = st.session_state.page
    active = "home" if page in _HOME_PAGES else page
    if page in ("budgets", "categories", "profile", "more"):
        active = "more"

    cols = st.columns(len(_NAV_ITEMS))
    for col, (icon, label, key) in zip(cols, _NAV_ITEMS):
        is_active = active == key
        with col:
            if st.button(
                f"{icon}\n{label}",
                key=f"bnav_{key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.page = key
                st.rerun()

def _render_sidebar():
    """Compatibilidad: no hace nada, la nav es el bottom bar."""
    pass

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
                f"""<div style="background:var(--card-bg);border-radius:14px;padding:1.1rem 1rem;
                                text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.08);margin-bottom:.8rem;">
                        <div style="font-size:1.8rem;">{icon}</div>
                        <h4 style="color:var(--text-color);margin:.4rem 0 .2rem;font-size:.93rem;">{title}</h4>
                        <p style="color:var(--text-color);opacity:.7;font-size:.82rem;line-height:1.45;margin:0;">{desc}</p>
                    </div>""", unsafe_allow_html=True)


def page_login():
    st.markdown(_HIDE_SIDEBAR, unsafe_allow_html=True)
    _, col, _ = st.columns([0.5, 3, 0.5])
    with col:
        st.markdown("""<div style="text-align:center;padding:1.5rem 0 1rem;">
            <div style="font-size:3rem;">💰</div>
            <h2 style="color:#667eea;margin:.2rem 0 0;">Iniciar sesión</h2>
            <p style="color:var(--text-color);opacity:.6;">Bienvenido/a de vuelta</p></div>""", unsafe_allow_html=True)

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
        if st.button("🔑 ¿Olvidaste tu contraseña?", key="forgot_pw",
                     use_container_width=True, type="secondary"):
            st.session_state.auth_mode = "forgot"; st.rerun()
        if st.button("← Volver al inicio", key="login_back", use_container_width=True):
            st.session_state.auth_mode = "landing"; st.rerun()
        st.markdown("<p style='text-align:center;color:var(--text-color);opacity:.6;font-size:.88rem;margin-top:.8rem;'>¿No tienes cuenta?</p>",
                    unsafe_allow_html=True)
        if st.button("✨ Crear cuenta gratis", key="login_to_reg", use_container_width=True):
            st.session_state.auth_mode = "register"; st.rerun()


def page_forgot_password():
    """Flujo de recuperación de contraseña en 2 pasos: solicitar código → verificar y cambiar."""
    import random, string
    st.markdown(_HIDE_SIDEBAR, unsafe_allow_html=True)
    _, col, _ = st.columns([0.5, 3, 0.5])
    with col:
        st.markdown("""<div style="text-align:center;padding:1.5rem 0 1rem;">
            <div style="font-size:3rem;">🔑</div>
            <h2 style="color:#667eea;margin:.2rem 0 0;">Recuperar contraseña</h2>
            <p style="color:var(--text-color);opacity:.6;">Te enviaremos un código a tu correo</p>
            </div>""", unsafe_allow_html=True)

        step = "solicitar" if not st.session_state.get("reset_email_sent") else "verificar"

        # ── Paso 1: pedir correo ──────────────────────────────────────────────
        if step == "solicitar":
            r_email = st.text_input("📧 Correo registrado", key="fp_email",
                                     placeholder="juan@email.com")
            st.markdown("")
            if st.button("Enviar código →", use_container_width=True,
                         type="primary", key="btn_send_code"):
                if not r_email or "@" not in r_email:
                    st.error("Ingresa un correo válido.")
                else:
                    storage    = st.session_state.storage
                    users, sha = storage.get_users()
                    # Buscar usuario por email (case-insensitive)
                    found_user = None
                    for uname, udata in users.items():
                        if udata.get("email", "").lower() == r_email.lower():
                            found_user = uname
                            break
                    if not found_user:
                        # Respuesta genérica para no revelar si el email existe
                        st.session_state.reset_email_sent = True
                        st.session_state.reset_username   = None
                        st.rerun()
                    else:
                        # Generar código de 6 dígitos
                        code    = "".join(random.choices(string.digits, k=6))
                        expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
                        users[found_user]["reset_code"]    = _hash(code)
                        users[found_user]["reset_expires"] = expires
                        if storage.save_users(users, sha):
                            sent = _send_reset_email(r_email, users[found_user].get("nombre",""), code)
                            if sent:
                                st.session_state.reset_email_sent = True
                                st.session_state.reset_username   = found_user
                                st.rerun()
                            else:
                                st.error(
                                    "No se pudo enviar el correo. "
                                    "Verifica que los secrets de email estén configurados en Streamlit Cloud."
                                )
                        else:
                            st.error("Error al generar el código. Intenta de nuevo.")

        # ── Paso 2: verificar código y nueva contraseña ───────────────────────
        else:
            st.success("✅ Código enviado. Revisa tu bandeja de entrada (y spam).")
            st.info("Ingresa el código de 6 dígitos que recibiste.", icon="📬")
            fp_code  = st.text_input("🔢 Código de verificación", key="fp_code",
                                      placeholder="123456", max_chars=6)
            fp_pass1 = st.text_input("🔒 Nueva contraseña", type="password", key="fp_pass1",
                                      placeholder="Mínimo 6 caracteres")
            fp_pass2 = st.text_input("🔒 Confirmar contraseña", type="password", key="fp_pass2",
                                      placeholder="Repite la contraseña")
            st.markdown("")

            if st.button("Cambiar contraseña →", use_container_width=True,
                         type="primary", key="btn_change_pass"):
                errs = []
                if len(fp_code) != 6 or not fp_code.isdigit():
                    errs.append("El código debe tener 6 dígitos.")
                if len(fp_pass1) < 6:
                    errs.append("La contraseña debe tener al menos 6 caracteres.")
                if fp_pass1 != fp_pass2:
                    errs.append("Las contraseñas no coinciden.")

                if errs:
                    for e in errs: st.error(e)
                else:
                    storage    = st.session_state.storage
                    users, sha = storage.get_users()
                    reset_user = st.session_state.get("reset_username")

                    valid = False
                    if reset_user and reset_user in users:
                        udata   = users[reset_user]
                        expires = udata.get("reset_expires", "")
                        code_ok = udata.get("reset_code", "") == _hash(fp_code)
                        not_exp = expires and datetime.utcnow().isoformat() < expires
                        valid   = code_ok and not_exp

                    if valid:
                        users[reset_user]["password"] = _hash(fp_pass1)
                        # Limpiar código de reset
                        users[reset_user].pop("reset_code",    None)
                        users[reset_user].pop("reset_expires", None)
                        if storage.save_users(users, sha):
                            st.success("✅ ¡Contraseña cambiada! Ya puedes iniciar sesión.")
                            st.session_state.reset_email_sent = False
                            st.session_state.reset_username   = None
                            st.session_state.auth_mode = "login"
                            st.rerun()
                        else:
                            st.error("Error al guardar. Intenta de nuevo.")
                    else:
                        st.error("Código incorrecto o expirado. Solicita uno nuevo.")

            if st.button("↩️ Solicitar nuevo código", key="fp_resend",
                         use_container_width=True):
                st.session_state.reset_email_sent = False
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Volver al login", key="fp_back", use_container_width=True):
            st.session_state.reset_email_sent = False
            st.session_state.auth_mode = "login"; st.rerun()


def page_register():
    st.markdown(_HIDE_SIDEBAR, unsafe_allow_html=True)
    _, col, _ = st.columns([0.5, 3, 0.5])
    with col:
        st.markdown("""<div style="text-align:center;padding:1.5rem 0 1rem;">
            <div style="font-size:3rem;">✨</div>
            <h2 style="color:#667eea;margin:.2rem 0 0;">Crear cuenta</h2>
            <p style="color:var(--text-color);opacity:.6;">Tus datos son completamente privados</p></div>""", unsafe_allow_html=True)

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
        st.markdown("<p style='text-align:center;color:var(--text-color);opacity:.6;font-size:.88rem;margin-top:.8rem;'>¿Ya tienes cuenta?</p>",
                    unsafe_allow_html=True)
        if st.button("🔑 Iniciar sesión", key="reg_to_login", use_container_width=True):
            st.session_state.auth_mode = "login"; st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
#  PÁGINAS AUTENTICADAS
# ═══════════════════════════════════════════════════════════════════════════════

def page_home():
    """Inicio + Dashboard fusionado con gráficos y transacciones recientes."""
    _render_greeting()
    user    = st.session_state.user_data
    now     = datetime.now()
    storage = st.session_state.storage

    transactions, _ = storage.get_transactions()
    df_all  = pd.DataFrame(transactions) if transactions else pd.DataFrame()
    df_user = pd.DataFrame()
    if not df_all.empty:
        df_user = df_all[df_all["username"] == st.session_state.username].copy()
        df_user["date"] = pd.to_datetime(df_user["date"])

    df_month = (df_user[(df_user["date"].dt.year == now.year) &
                         (df_user["date"].dt.month == now.month)]
                if not df_user.empty else pd.DataFrame())

    # ── KPIs del mes actual ───────────────────────────────────────────────────
    ing = df_month[df_month["type"] == "Ingreso"   ]["amount"].sum() if not df_month.empty else 0
    gas = df_month[df_month["type"] == "Gasto"     ]["amount"].sum() if not df_month.empty else 0
    inv = df_month[df_month["type"] == "Inversión" ]["amount"].sum() if not df_month.empty else 0
    bal = ing - gas - inv
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💚 Ingresos",    f"${ing:,.0f}")
    c2.metric("🔴 Gastos",      f"${gas:,.0f}")
    c3.metric("🔵 Inversiones", f"${inv:,.0f}")
    c4.metric("🟡 Balance",     f"${bal:,.0f}",
              delta=f"{bal/ing*100:.1f}%" if ing else None)

    if df_user.empty:
        st.info("Sin transacciones aún.")
        if st.button("➕ Agregar primera transacción", type="primary"):
            st.session_state.page = "add"; st.rerun()
        return

    # ── Rolling N meses ───────────────────────────────────────────────────────
    n_months = st.slider("📅 Últimos meses", 3, 36, 12,
                          key="home_rolling", label_visibility="collapsed",
                          help="Número de meses a mostrar en los gráficos")

    months_range = []
    for i in range(n_months - 1, -1, -1):
        total_m = now.month - 1 - i
        y_d = now.year + total_m // 12
        m_d = total_m % 12 + 1
        months_range.append((y_d, m_d))
    mes_keys = [f"{y}-{m:02d}" for y, m in months_range]
    mes_labels = [f"{MONTHS_ES[m][:3]} {y}" for y, m in months_range]

    df_user["mes_key"] = df_user["date"].dt.to_period("M").astype(str)
    df_range = df_user[df_user["mes_key"].isin(mes_keys)].copy()

    # ── Gráficos: barras + torta ──────────────────────────────────────────────
    if not df_range.empty:
        gc1, gc2 = st.columns(2)

        with gc1:
            st.markdown("##### Evolución mensual")
            rows_m = []
            for (y, m), key, label in zip(months_range, mes_keys, mes_labels):
                mdf = df_range[df_range["mes_key"] == key]
                for tipo in DEFAULT_CATEGORIES:
                    rows_m.append({"Mes": label, "Tipo": tipo,
                                   "amount": mdf[mdf["type"] == tipo]["amount"].sum()})
            df_m = pd.DataFrame(rows_m)
            fig1 = px.bar(df_m, x="Mes", y="amount", color="Tipo", barmode="group",
                          color_discrete_map=TYPE_COLORS,
                          labels={"amount": "", "Mes": "", "Tipo": ""})
            fig1.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0),
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               legend=dict(orientation="h", y=1.25, font=dict(size=9)),
                               xaxis=dict(tickangle=-35, tickfont=dict(size=8)))
            st.plotly_chart(fig1, use_container_width=True,
                            config={"displayModeBar": False})

        with gc2:
            st.markdown("##### Gastos por categoría")
            gdf = df_range[df_range["type"] == "Gasto"]
            if not gdf.empty:
                user_cats = _user_categories(user)
                gdf = gdf.copy()
                gdf["category"] = gdf.apply(
                    lambda r: _safe_category(r.get("category",""), user_cats, r["type"]), axis=1)
                cat_g = gdf.groupby("category")["amount"].sum().reset_index()
                total_g = cat_g["amount"].sum()
                cat_g["label"] = cat_g.apply(
                    lambda r: r["category"] if r["amount"]/total_g*100 >= 8 else "", axis=1)
                fig2 = go.Figure(go.Pie(
                    labels=cat_g["category"], values=cat_g["amount"],
                    text=cat_g["label"], textinfo="text+percent",
                    textposition="inside", hole=0.35,
                    marker=dict(colors=px.colors.qualitative.Pastel,
                                line=dict(color="white", width=1.5)),
                    hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
                ))
                fig2.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0),
                                   paper_bgcolor="rgba(0,0,0,0)",
                                   showlegend=False)
                st.plotly_chart(fig2, use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.info("Sin gastos en el período.")

    # ── Últimas transacciones ─────────────────────────────────────────────────
    st.markdown("**Movimientos recientes**")
    user_cats = _user_categories(user)
    for _, row in df_user.sort_values("date", ascending=False).head(6).iterrows():
        color    = TYPE_COLORS.get(row["type"], "#888")
        desc     = row.get("description", "") or ""
        fecha    = pd.Timestamp(row["date"]).strftime("%d/%m")
        category = _safe_category(row.get("category",""), user_cats, row["type"])
        st.markdown(
            f"""<div class="tx-card" style="border-left:3px solid {color};padding:.5rem .8rem;">
                <div style="font-size:.9rem;">
                    <strong>{category}</strong>
                    {"<br><span style='font-size:.78rem;opacity:.6;'>" + desc + "</span>" if desc else ""}
                </div>
                <div style="text-align:right;white-space:nowrap;">
                    <strong style="color:{color};">${row['amount']:,.0f}</strong>
                    <br><span style="font-size:.75rem;opacity:.5;">{fecha}</span>
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

    # ── Estado para edición ────────────────────────────────────────────────────
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    if "delete_confirm_id" not in st.session_state:
        st.session_state.delete_confirm_id = None

    storage = st.session_state.storage
    transactions, sha = storage.get_transactions()
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

    # ── Filtros ────────────────────────────────────────────────────────────────
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

    # ── Lista de transacciones con botones ────────────────────────────────────
    for _, row in filtered.iterrows():
        tx_id    = row["id"]
        color    = TYPE_COLORS.get(row["type"], "#888")
        fecha    = pd.Timestamp(row["date"]).strftime("%d/%m/%Y")
        desc     = row.get("description", "") or ""
        category = row["category"]
        is_editing  = st.session_state.editing_id == tx_id
        is_deleting = st.session_state.delete_confirm_id == tx_id

        with st.container():
            # ── Modo edición ──────────────────────────────────────────────────
            if is_editing:
                st.markdown(
                    f"<div style='border-left:4px solid {color};background:var(--card-bg);"
                    f"border-radius:10px;padding:.8rem 1rem;margin:.3rem 0;"
                    f"box-shadow:0 2px 8px rgba(0,0,0,.1);'>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**✏️ Editando transacción** — {fecha}")

                ec1, ec2 = st.columns(2)
                with ec1:
                    e_type = st.selectbox("Tipo", list(DEFAULT_CATEGORIES.keys()),
                                           index=list(DEFAULT_CATEGORIES.keys()).index(row["type"]),
                                           key=f"e_type_{tx_id}")
                with ec2:
                    cats_e = user_cats.get(e_type, [SIN_ASIGNAR])
                    cat_idx = cats_e.index(category) if category in cats_e else 0
                    e_cat = st.selectbox("Categoría", cats_e, index=cat_idx,
                                          key=f"e_cat_{tx_id}")

                ec3, ec4 = st.columns(2)
                with ec3:
                    e_amount = st.number_input("Monto", min_value=0.0, step=1000.0,
                                                format="%.2f", value=float(row["amount"]),
                                                key=f"e_amount_{tx_id}")
                with ec4:
                    e_date = st.date_input("Fecha",
                                            value=pd.Timestamp(row["date"]).date(),
                                            key=f"e_date_{tx_id}")

                e_desc = st.text_input("Descripción", value=desc,
                                        key=f"e_desc_{tx_id}")

                btn1, btn2 = st.columns(2)
                with btn1:
                    if st.button("💾 Guardar cambios", type="primary",
                                  use_container_width=True, key=f"save_{tx_id}"):
                        all_tx, sha2 = storage.get_transactions()
                        for tx in all_tx:
                            if tx["id"] == tx_id:
                                tx["type"]        = e_type
                                tx["category"]    = e_cat or SIN_ASIGNAR
                                tx["amount"]      = float(e_amount)
                                tx["date"]        = e_date.isoformat()
                                tx["description"] = e_desc.strip()
                                break
                        if storage.save_transactions(all_tx, sha2):
                            st.session_state.editing_id = None
                            st.success("✅ Transacción actualizada.")
                            st.rerun()
                        else:
                            st.error("Error al guardar.")
                with btn2:
                    if st.button("✕ Cancelar", use_container_width=True,
                                  key=f"cancel_{tx_id}"):
                        st.session_state.editing_id = None
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

            # ── Modo confirmación borrado ──────────────────────────────────────
            elif is_deleting:
                st.markdown(
                    f"""<div style="border-left:4px solid #FF6B6B;background:var(--card-bg);
                        border-radius:10px;padding:.8rem 1rem;margin:.3rem 0;
                        box-shadow:0 2px 8px rgba(255,107,107,.2);">
                        <strong>🗑️ ¿Eliminar esta transacción?</strong><br>
                        <span style="color:var(--text-color);opacity:.7;font-size:.88rem;">
                        {category} · ${row['amount']:,.0f} · {fecha}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("🗑️ Sí, eliminar", type="primary",
                                  use_container_width=True, key=f"confirm_del_{tx_id}"):
                        all_tx, sha2 = storage.get_transactions()
                        all_tx = [tx for tx in all_tx if tx["id"] != tx_id]
                        if storage.save_transactions(all_tx, sha2):
                            st.session_state.delete_confirm_id = None
                            st.success("🗑️ Transacción eliminada.")
                            st.rerun()
                        else:
                            st.error("Error al eliminar.")
                with dc2:
                    if st.button("✕ Cancelar", use_container_width=True,
                                  key=f"cancel_del_{tx_id}"):
                        st.session_state.delete_confirm_id = None
                        st.rerun()

            # ── Vista normal ──────────────────────────────────────────────────
            else:
                col_info, col_monto, col_edit, col_del = st.columns([5, 2, 1, 1])
                with col_info:
                    st.markdown(
                        f"""<div style="padding:.45rem 0;">
                            <span style="border-left:4px solid {color};padding-left:.6rem;">
                            <strong>{category}</strong>
                            <span style="color:var(--text-color);opacity:.5;font-size:.8rem;margin-left:.5rem;">
                            {fecha} · {row['type']}</span></span>
                            {"<br><span style='color:var(--text-color);opacity:.6;font-size:.82rem;padding-left:1rem;'>" + desc + "</span>" if desc else ""}
                        </div>""",
                        unsafe_allow_html=True,
                    )
                with col_monto:
                    st.markdown(
                        f"<div style='padding:.45rem 0;text-align:right;"
                        f"font-weight:700;color:{color};font-size:1rem;'>"
                        f"${row['amount']:,.0f}</div>",
                        unsafe_allow_html=True,
                    )
                with col_edit:
                    if st.button("✏️", key=f"edit_{tx_id}", help="Editar",
                                  use_container_width=True):
                        st.session_state.editing_id      = tx_id
                        st.session_state.delete_confirm_id = None
                        st.rerun()
                with col_del:
                    if st.button("🗑️", key=f"del_{tx_id}", help="Eliminar",
                                  use_container_width=True):
                        st.session_state.delete_confirm_id = tx_id
                        st.session_state.editing_id        = None
                        st.rerun()

    st.markdown("---")
    st.download_button("⬇️ Descargar CSV",
                       data=filtered[["date","type","category","amount","description"]]
                           .assign(date=filtered["date"].dt.strftime("%d/%m/%Y"))
                           .to_csv(index=False).encode("utf-8"),
                       file_name=f"transacciones_{datetime.now():%Y%m%d}.csv",
                       mime="text/csv")



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

    # ── Rango fijo de N meses para todos los gráficos ────────────────────────
    now_dash  = datetime.now()
    n_months  = rolling_months if vista == "Rolling N meses" else 12

    # Lista ordenada de (year, month) para los últimos N meses
    months_range_dash = []
    for i in range(n_months - 1, -1, -1):
        total_m = now_dash.month - 1 - i
        y_d = now_dash.year + total_m // 12
        m_d = total_m % 12 + 1
        months_range_dash.append((y_d, m_d))

    mes_keys_dash   = [f"{y}-{m:02d}" for y, m in months_range_dash]
    mes_labels_dash = [f"{MONTHS_ES[m][:3]} {y}" for y, m in months_range_dash]

    # Construir tabla mensual: para cada mes y tipo, sumar real
    rows_dash = []
    for (y, m), key, label in zip(months_range_dash, mes_keys_dash, mes_labels_dash):
        mdf = df_user[(df_user["date"].dt.year == y) & (df_user["date"].dt.month == m)]
        for tipo in DEFAULT_CATEGORIES:
            rows_dash.append({
                "mes_key": key, "Mes": label, "Tipo": tipo,
                "amount": mdf[mdf["type"] == tipo]["amount"].sum(),
            })
    monthly_full = pd.DataFrame(rows_dash)

    # ── Fila 1: Evolución mensual  |  Top categorías Gasto ───────────────────
    r1c1, r1c2 = st.columns(2)

    with r1c1:
        st.markdown("#### 📈 Evolución mensual")
        fig1 = go.Figure()
        for tipo, color in TYPE_COLORS.items():
            tdf = monthly_full[monthly_full["Tipo"] == tipo]
            fig1.add_trace(go.Bar(
                name=tipo, x=tdf["Mes"], y=tdf["amount"],
                marker_color=color,
                hovertemplate=f"{tipo}: $%{{y:,.0f}}<extra></extra>",
            ))
        fig1.update_layout(
            barmode="group",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.12),
            margin=dict(l=0, r=0, t=10, b=0), height=340,
            xaxis=dict(tickangle=-35),
            yaxis_title="Monto",
            hovermode="x unified",
        )
        st.plotly_chart(fig1, use_container_width=True)

    with r1c2:
        st.markdown("#### 🥧 Top categorías de Gasto")
        # Usa solo los datos del rango N meses
        gdf_pie = df_user[
            df_user["date"].dt.to_period("M").astype(str).isin(mes_keys_dash) &
            (df_user["type"] == "Gasto")
        ]
        if not gdf_pie.empty:
            cat_pie = (gdf_pie.groupby("category")["amount"].sum()
                       .reset_index().sort_values("amount", ascending=False))
            total_g = cat_pie["amount"].sum()
            cat_pie["label"] = cat_pie.apply(
                lambda r: r["category"] if (r["amount"] / total_g * 100 >= 5) else "",
                axis=1,
            )
            fig2 = go.Figure(go.Pie(
                labels=cat_pie["category"],
                values=cat_pie["amount"],
                text=cat_pie["label"],
                textinfo="text+percent",
                textposition="inside",
                hole=0.38,
                marker=dict(colors=px.colors.qualitative.Pastel,
                            line=dict(color="white", width=1.5)),
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
            ))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0), height=340,
                legend=dict(orientation="v", x=1.01, y=0.5, font=dict(size=11)),
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin gastos en este período.")

    # ── Fila 2: Ahorro mensual  |  Fuentes de ingreso ─────────────────────────
    r2c1, r2c2 = st.columns(2)

    with r2c1:
        st.markdown("#### 💹 Ahorro mensual (Ingreso − Gasto − Inversión)")
        # Calcular ahorro neto por mes
        pivot_save = (monthly_full.pivot_table(
            index="mes_key", columns="Tipo", values="amount", aggfunc="sum", fill_value=0
        ).reindex(mes_keys_dash, fill_value=0))
        pivot_save["ahorro"] = (
            pivot_save.get("Ingreso", 0) -
            pivot_save.get("Gasto", 0) -
            pivot_save.get("Inversión", 0)
        )
        pivot_save["Mes"] = mes_labels_dash
        pivot_save = pivot_save.reset_index()

        bar_save_colors = [
            "rgba(81,207,102,0.85)" if v >= 0 else "rgba(255,107,107,0.85)"
            for v in pivot_save["ahorro"]
        ]
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            x=pivot_save["Mes"], y=pivot_save["ahorro"],
            marker_color=bar_save_colors,
            hovertemplate="Ahorro: $%{y:,.0f}<extra></extra>",
        ))
        # Línea de cero
        fig4.add_hline(y=0, line_color="rgba(100,100,100,0.4)", line_width=1.5)
        # Línea de ahorro acumulado
        pivot_save["acum"] = pivot_save["ahorro"].cumsum()
        fig4.add_trace(go.Scatter(
            x=pivot_save["Mes"], y=pivot_save["acum"],
            name="Acumulado",
            mode="lines+markers",
            line=dict(color="#667eea", width=2.5, dash="dot"),
            marker=dict(size=6),
            yaxis="y2",
            hovertemplate="Acumulado: $%{y:,.0f}<extra></extra>",
        ))
        fig4.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0), height=340,
            xaxis=dict(tickangle=-35),
            yaxis=dict(title="Ahorro del mes"),
            yaxis2=dict(title="Acumulado", overlaying="y", side="right",
                        showgrid=False),
            legend=dict(orientation="h", y=1.12),
            hovermode="x unified",
            showlegend=True,
        )
        st.plotly_chart(fig4, use_container_width=True)

    with r2c2:
        st.markdown("#### 💼 Fuentes de Ingreso")
        idf = df_user[
            df_user["date"].dt.to_period("M").astype(str).isin(mes_keys_dash) &
            (df_user["type"] == "Ingreso")
        ]
        if not idf.empty:
            fig6 = go.Figure(go.Pie(
                labels=idf.groupby("category")["amount"].sum().reset_index()["category"],
                values=idf.groupby("category")["amount"].sum().reset_index()["amount"],
                hole=0.35,
                marker=dict(colors=px.colors.qualitative.Pastel,
                            line=dict(color="white", width=1.5)),
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
            ))
            fig6.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0), height=340,
                legend=dict(orientation="v", x=1.01, y=0.5, font=dict(size=11)),
            )
            st.plotly_chart(fig6, use_container_width=True)
        else:
            st.info("Sin ingresos en este período.")

    # ── Gráfico Real vs Presupuesto (3 subgráficos, meses cerrados) ─────────────
    budgets = _get_budgets(st.session_state.user_data)
    has_any_budget = any(
        b.get("bases") or b.get("overrides") for b in budgets.values()
    )

    if has_any_budget:
        st.markdown("---")
        st.markdown("#### 🎯 Real vs Presupuesto")
        st.caption(
            "Barra sólida = valor real · Barra transparente = presupuesto. "
            "El cumplimiento solo se evalúa en **meses ya cerrados** (no el mes en curso)."
        )

        now_bud = datetime.now()

        # Rango de meses: últimos 12 o rolling N, ambos hacia atrás desde hoy
        n_months = rolling_months if vista == "Rolling N meses" else 12
        months_range = []
        for i in range(n_months - 1, -1, -1):
            total_months = now_bud.month - 1 - i
            y_off = now_bud.year + total_months // 12
            m_off = total_months % 12 + 1
            months_range.append((y_off, m_off))

        mes_labels = [f"{MONTHS_ES[m][:3]} {y}" for y, m in months_range]

        # Construir tabla: mes × tipo → real, presupuesto, cerrado
        rows_b = []
        for (y, m), label in zip(months_range, mes_labels):
            is_closed = (y < now_bud.year) or (y == now_bud.year and m < now_bud.month)
            month_df  = df_user[
                (df_user["date"].dt.year == y) & (df_user["date"].dt.month == m)
            ]
            for tipo in DEFAULT_CATEGORIES:
                real = month_df[month_df["type"] == tipo]["amount"].sum()
                pres = _budget_for_month(budgets, tipo, y, m)
                rows_b.append({
                    "mes_key": f"{y}-{m:02d}", "Mes": label,
                    "Tipo": tipo, "Real": real,
                    "Presupuesto": pres, "is_closed": is_closed,
                })

        bdf = pd.DataFrame(rows_b)

        # ── Un subgráfico por tipo ────────────────────────────────────────────
        ALPHA = {           # color sólido y transparente por tipo
            "Gasto":    ("rgba(255,107,107,1)",   "rgba(255,107,107,0.22)"),
            "Ingreso":  ("rgba(81,207,102,1)",    "rgba(81,207,102,0.22)"),
            "Inversión":("rgba(51,154,240,1)",    "rgba(51,154,240,0.22)"),
        }
        LABEL_MET = {
            "Gasto":     ("✅ Bajo presupuesto", "❌ Sobre presupuesto"),
            "Ingreso":   ("✅ Meta alcanzada",   "❌ Meta no alcanzada"),
            "Inversión": ("✅ Meta alcanzada",   "❌ Meta no alcanzada"),
        }

        total_closed = 0
        total_met    = 0

        for tipo in DEFAULT_CATEGORIES:
            tdf = bdf[bdf["Tipo"] == tipo].copy()
            if tdf["Presupuesto"].sum() == 0:
                continue   # sin presupuesto definido → saltar

            solid, ghost = ALPHA[tipo]
            lbl_ok, lbl_ko = LABEL_MET[tipo]

            fig_t = go.Figure()

            # ── Barra presupuesto (transparente, siempre visible) ─────────────
            fig_t.add_trace(go.Bar(
                name="Presupuesto",
                x=tdf["Mes"],
                y=tdf["Presupuesto"].where(tdf["Presupuesto"] > 0),
                marker_color=ghost,
                marker_line=dict(color=solid.replace(",1)", ",0.6)"), width=1.5),
                hovertemplate="Presupuesto: $%{y:,.0f}<extra></extra>",
            ))

            # ── Barra real: coloreada solo en meses cerrados ──────────────────
            real_colors = []
            for _, row in tdf.iterrows():
                if not row["is_closed"]:
                    real_colors.append("rgba(180,180,180,0.5)")   # mes en curso → gris
                elif row["Presupuesto"] <= 0:
                    real_colors.append(solid)                      # sin presupuesto → color tipo
                elif _budget_met(tipo, row["Real"], row["Presupuesto"]):
                    real_colors.append("rgba(81,207,102,0.9)")     # cumplido → verde
                else:
                    real_colors.append("rgba(255,107,107,0.9)")    # incumplido → rojo

            fig_t.add_trace(go.Bar(
                name="Real",
                x=tdf["Mes"],
                y=tdf["Real"],
                marker_color=real_colors,
                hovertemplate="Real: $%{y:,.0f}<extra></extra>",
            ))

            # Marcar mes en curso con anotación
            cur_label = f"{MONTHS_ES[now_bud.month][:3]} {now_bud.year}"
            if cur_label in tdf["Mes"].values:
                fig_t.add_annotation(
                    x=cur_label, y=0,
                    text="← en curso", showarrow=False,
                    font=dict(size=10, color="#aaa"),
                    yanchor="bottom", xanchor="left",
                )

            fig_t.update_layout(
                barmode="overlay",
                title=dict(text=f"<b>{tipo}</b>", font=dict(size=15), x=0),
                height=280,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=1.18),
                margin=dict(l=0, r=0, t=40, b=0),
                yaxis_title="Monto",
                hovermode="x unified",
            )
            st.plotly_chart(fig_t, use_container_width=True)

            # Contar cumplimiento solo en meses cerrados con presupuesto
            closed = tdf[tdf["is_closed"] & (tdf["Presupuesto"] > 0)]
            met_n  = closed.apply(
                lambda r: _budget_met(tipo, r["Real"], r["Presupuesto"]) is True, axis=1
            ).sum()
            total_closed += len(closed)
            total_met    += met_n

            if not closed.empty:
                pct_t = met_n / len(closed) * 100
                c_ok, c_ko = "#51CF66", "#FF6B6B"
                bc = c_ok if pct_t >= 80 else "#FFD43B" if pct_t >= 50 else c_ko
                st.caption(
                    f"{lbl_ok if pct_t >= 50 else lbl_ko}  ·  "
                    f"**{met_n}/{len(closed)}** meses cerrados cumplidos  "
                    f"({pct_t:.0f}%)"
                )

        # ── Semáforo global ───────────────────────────────────────────────────
        if total_closed > 0:
            pct_g = total_met / total_closed * 100
            bc    = "#51CF66" if pct_g >= 80 else "#FFD43B" if pct_g >= 50 else "#FF6B6B"
            emoji = "🟢" if pct_g >= 80 else "🟡" if pct_g >= 50 else "🔴"
            st.markdown(
                f"""<div style="background:var(--card-bg);border-radius:12px;padding:1rem 1.4rem;
                               box-shadow:0 2px 8px rgba(0,0,0,.07);margin-top:.4rem;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:.5rem;">
                        <span>{emoji} Cumplimiento global (meses cerrados):
                        <strong>{total_met}</strong> de <strong>{total_closed}</strong></span>
                        <span style="color:{bc};font-weight:700;">{pct_g:.0f}%</span>
                    </div>
                    <div class="budget-bar-bg">
                        <div class="budget-bar-fill"
                             style="width:{pct_g:.0f}%;background:{bc};"></div>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.info("Configura presupuestos en **🎯 Presupuestos** para ver este gráfico.")


# ═══════════════════════════════════════════════════════════════════════════════
#  PÁGINA – PRESUPUESTOS
# ═══════════════════════════════════════════════════════════════════════════════

def page_budgets():
    st.markdown("## 🎯 Presupuestos")
    st.markdown(
        "Define cuánto quieres **gastar, ganar e invertir** cada mes. "
        "Puedes establecer un **base mensual** y luego ajustar meses específicos "
        "cuando algo cambie (nuevo trabajo, vacaciones, inesperado, etc.)."
    )

    storage    = st.session_state.storage
    users, sha = storage.get_users()
    username   = st.session_state.username
    user       = users[username]
    budgets    = _get_budgets(user)
    now        = datetime.now()

    # ── Resumen del mes actual ─────────────────────────────────────────────────
    transactions, _ = storage.get_transactions()
    df_all  = pd.DataFrame(transactions) if transactions else pd.DataFrame()
    df_user = df_all[df_all["username"] == username].copy() if not df_all.empty else pd.DataFrame()

    if not df_user.empty:
        df_user["date"] = pd.to_datetime(df_user["date"])
        df_month = df_user[(df_user["date"].dt.year == now.year) &
                            (df_user["date"].dt.month == now.month)]
    else:
        df_month = pd.DataFrame()

    st.markdown(f"### 📅 Estado actual — {MONTHS_ES[now.month]} {now.year}")

    cols = st.columns(3)
    for col, tipo in zip(cols, DEFAULT_CATEGORIES):
        real = df_month[df_month["type"] == tipo]["amount"].sum() if not df_month.empty else 0
        pres = _budget_for_month(budgets, tipo, now.year, now.month)
        met  = _budget_met(tipo, real, pres)
        color = TYPE_COLORS[tipo]

        if pres > 0:
            pct  = min(real / pres * 100, 100)
            bar_color = ("#51CF66" if met else "#FF6B6B")
            resto = pres - real
            resto_label = (f"🟢 Disponible: ${resto:,.0f}" if tipo == "Gasto" and resto >= 0
                           else f"🔴 Excedido: ${-resto:,.0f}" if tipo == "Gasto"
                           else f"🟢 Cumplido ✓" if met else f"🔴 Faltan: ${resto:,.0f} para meta")
            icon = "✅" if met else "⚠️"
        else:
            pct = 0; bar_color = "#ccc"; resto_label = "Sin presupuesto definido"; icon = "➖"

        with col:
            st.markdown(
                f"""<div class="budget-card" style="border-top:4px solid {color};">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <strong style="color:{color};">{tipo}</strong>
                        <span style="font-size:1.3rem;">{icon}</span>
                    </div>
                    <div style="margin:.5rem 0;">
                        <span style="font-size:1.4rem;font-weight:700;">${real:,.0f}</span>
                        <span style="color:var(--text-color);opacity:.5;font-size:.88rem;"> / ${pres:,.0f}</span>
                    </div>
                    <div class="budget-bar-bg">
                        <div class="budget-bar-fill" style="width:{pct:.0f}%;background:{bar_color};"></div>
                    </div>
                    <div style="font-size:.82rem;color:var(--text-color);opacity:.7;margin-top:.4rem;">{resto_label}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Configuración por tipo ─────────────────────────────────────────────────
    st.markdown("### ⚙️ Configurar presupuestos")
    st.caption(
        "💡 **Cómo funciona:** Define un monto base mensual que aplica a todos los meses. "
        "Si en algún mes específico cambia tu situación, agrega un ajuste para ese mes."
    )

    changed = False
    tabs    = st.tabs(["🔴 Gasto", "💚 Ingreso", "🔵 Inversión"])

    for tab, tipo in zip(tabs, list(DEFAULT_CATEGORIES.keys())):
        with tab:
            b     = budgets[tipo]
            color = TYPE_COLORS[tipo]
            meta_label = "No gastar más de" if tipo == "Gasto" else "Lograr al menos"

            # ── Bases con vigencia ────────────────────────────────────────────
            st.markdown(f"#### 📋 Bases vigentes — {meta_label}:")
            st.caption(
                "Cada base aplica **desde** el mes indicado hasta que definas una nueva. "
                "Si cambias de trabajo, te jubilan o cambia tu situación financiera, "
                "agrega una nueva base con la fecha de inicio del cambio."
            )

            bases = list(b.get("bases", []))

            if bases:
                # Encabezado de tabla
                hc1, hc2, hc3 = st.columns([2, 3, 1])
                hc1.markdown("**Desde**")
                hc2.markdown("**Monto mensual**")
                hc3.markdown("")

                for idx, base_entry in enumerate(sorted(bases, key=lambda x: x["from"], reverse=True)):
                    fr_y, fr_m = int(base_entry["from"][:4]), int(base_entry["from"][5:7])
                    fr_label   = f"{MONTHS_ES[fr_m]} {fr_y}"
                    bc1, bc2, bc3 = st.columns([2, 3, 1])
                    # ¿Es la vigente ahora?
                    now_key = f"{now.year}-{now.month:02d}"
                    is_active = (base_entry["from"] <= now_key and
                                 all(e["from"] <= base_entry["from"] or e["from"] > now_key
                                     for e in bases if e is not base_entry))
                    label_extra = " 🟢 *vigente*" if is_active else ""
                    bc1.markdown(f"**{fr_label}**{label_extra}")
                    bc2.markdown(f"${base_entry['amount']:,.0f}  ·  *${base_entry['amount']*12:,.0f}/año*")
                    if bc3.button("✕", key=f"del_base_{tipo}_{idx}", help="Eliminar esta base"):
                        bases = [e for e in bases if e is not base_entry]
                        budgets[tipo]["bases"] = bases
                        changed = True
            else:
                st.info("Sin bases definidas. Agrega una abajo.", icon="ℹ️")

            # Agregar nueva base
            st.markdown("**➕ Agregar nueva base:**")
            nb1, nb2 = st.columns(2)
            with nb1:
                nb_year  = st.selectbox("Desde — Año",
                                         list(range(now.year - 2, now.year + 4)),
                                         index=2, key=f"nb_year_{tipo}")
                nb_month = st.selectbox("Desde — Mes", list(MONTHS_ES.values()),
                                         index=now.month - 1, key=f"nb_month_{tipo}")
            with nb2:
                nb_amount = st.number_input(
                    f"Monto mensual ({tipo})",
                    min_value=0.0, step=50000.0, format="%.0f",
                    key=f"nb_amount_{tipo}", placeholder="Ej: 2000000",
                )
                nb_note = st.text_input("Nota (opcional)", key=f"nb_note_{tipo}",
                                         placeholder="Ej: Nuevo trabajo, Reducción salario…")

            if st.button(f"Agregar base desde {MONTHS_ES[now.month if nb_month == list(MONTHS_ES.values())[now.month-1] else list(MONTHS_ES.values()).index(nb_month)+1]} {nb_year}",
                         key=f"add_base_{tipo}", type="primary"):
                m_num   = [k for k, v in MONTHS_ES.items() if v == nb_month][0]
                new_key = f"{nb_year}-{m_num:02d}"
                # Reemplaza si ya existe ese mes
                bases   = [e for e in bases if e["from"] != new_key]
                entry   = {"from": new_key, "amount": float(nb_amount)}
                if nb_note.strip():
                    entry["note"] = nb_note.strip()
                bases.append(entry)
                budgets[tipo]["bases"] = sorted(bases, key=lambda x: x["from"])
                changed = True

            # ── Ajustes por mes ───────────────────────────────────────────────
            st.markdown("#### 🗓️ Ajustes por mes específico")
            st.caption(
                "Usa esto cuando un mes particular es diferente al base: "
                "te despidieron, tuviste un ingreso extra, tomaste vacaciones, etc."
            )

            overrides = dict(b.get("overrides", {}))

            # Mostrar overrides existentes
            if overrides:
                for mes_key in sorted(overrides.keys(), reverse=True):
                    y_o, m_o = int(mes_key[:4]), int(mes_key[5:7])
                    mes_label = f"{MONTHS_ES[m_o]} {y_o}"
                    oc1, oc2, oc3 = st.columns([3, 2, 1])
                    oc1.markdown(f"**{mes_label}**")
                    oc2.markdown(f"${overrides[mes_key]:,.0f}")
                    if oc3.button("✕", key=f"del_ov_{tipo}_{mes_key}",
                                  help="Eliminar ajuste"):
                        del overrides[mes_key]
                        budgets[tipo]["overrides"] = overrides
                        changed = True
            else:
                st.info("No tienes ajustes de mes específico aún.", icon="ℹ️")

            # Agregar nuevo override
            st.markdown("**➕ Agregar ajuste:**")
            na1, na2, na3 = st.columns([2, 3, 1])
            with na1:
                ov_year  = st.selectbox("Año", list(range(now.year - 1, now.year + 3)),
                                         index=1, key=f"ov_year_{tipo}")
            with na2:
                ov_month = st.selectbox("Mes", list(MONTHS_ES.values()),
                                         index=now.month - 1, key=f"ov_month_{tipo}")
            with na3:
                st.markdown("<div style='margin-top:1.8rem;'></div>", unsafe_allow_html=True)

            ov_amount = st.number_input(
                f"Monto para ese mes ({tipo})",
                min_value=0.0, step=50000.0, format="%.0f",
                key=f"ov_amount_{tipo}",
                placeholder="Ej: 1500000",
            )
            if st.button(f"Agregar ajuste para {ov_month} {ov_year}",
                         key=f"add_ov_{tipo}", type="secondary"):
                m_num    = [k for k, v in MONTHS_ES.items() if v == ov_month][0]
                mes_key  = f"{ov_year}-{m_num:02d}"
                overrides[mes_key] = float(ov_amount)
                budgets[tipo]["overrides"] = overrides
                changed = True

    # ── Guardar cambios ────────────────────────────────────────────────────────
    if changed:
        user["budgets"] = budgets
        users[username] = user
        if storage.save_users(users, sha):
            st.session_state.user_data = user
            st.success("✅ Presupuestos guardados.")
            st.rerun()
        else:
            st.error("Error al guardar. Intenta de nuevo.")

    # ── Proyección anual ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📆 Proyección anual")
    st.caption(f"Presupuesto mes a mes para {now.year} según tu configuración actual.")

    proj_rows = []
    for m in range(1, 13):
        row = {"Mes": MONTHS_ES[m]}
        for tipo in DEFAULT_CATEGORIES:
            row[tipo] = _budget_for_month(budgets, tipo, now.year, m)
        proj_rows.append(row)

    proj_df = pd.DataFrame(proj_rows)
    has_proj = any(proj_df[t].sum() > 0 for t in DEFAULT_CATEGORIES)
    if has_proj:
        # Formato visual
        display_df = proj_df.copy()
        for t in DEFAULT_CATEGORIES:
            display_df[t] = display_df[t].apply(
                lambda x: f"${x:,.0f}" if x > 0 else "—")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Gráfico de línea
        fig_proj = go.Figure()
        for tipo, color in TYPE_COLORS.items():
            if proj_df[tipo].sum() > 0:
                # Estrella = mes con override puntual o donde cambia la base activa
                overrides = budgets[tipo].get("overrides", {})
                bases_keys = [b["from"] for b in budgets[tipo].get("bases", [])]
                symbols = []
                for m in range(1, 13):
                    key = f"{now.year}-{m:02d}"
                    if key in overrides or key in bases_keys:
                        symbols.append("star")
                    else:
                        symbols.append("circle")
                fig_proj.add_trace(go.Scatter(
                    x=proj_df["Mes"], y=proj_df[tipo], name=tipo,
                    mode="lines+markers", line=dict(color=color, width=2.5),
                    marker=dict(size=8, symbol=symbols),
                ))
        fig_proj.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h"), margin=dict(l=0, r=0, t=10, b=0),
            height=300, xaxis_title="Mes", yaxis_title="Monto presupuestado",
        )
        st.plotly_chart(fig_proj, use_container_width=True)
        st.caption("⭐ Los marcadores en estrella indican meses con ajuste específico.")
    else:
        st.info("Define un presupuesto base arriba para ver la proyección anual.")


def page_profile():
    st.markdown("## 👤 Mi Perfil")
    st.markdown("Actualiza tu información personal. El nombre de usuario no se puede cambiar.")

    storage    = st.session_state.storage
    users, sha = storage.get_users()
    username   = st.session_state.username
    user       = users[username]

    st.markdown(f"**Usuario:** `{username}` 🔒")
    st.markdown("---")

    # ── Datos personales ──────────────────────────────────────────────────────
    st.markdown("### 📝 Datos personales")

    c1, c2 = st.columns(2)
    with c1:
        p_nombre = st.text_input("Nombre(s)", value=user.get("nombre",""),
                                  key="p_nombre", placeholder="Juan Carlos")
    with c2:
        trats    = ["(ninguno)", "Señor", "Señora", "Dr.", "Dra."]
        cur_trat = user.get("tratamiento", "") or "(ninguno)"
        p_trat   = st.selectbox("¿Cómo le gusta que le digan?", trats,
                                 index=trats.index(cur_trat) if cur_trat in trats else 0,
                                 key="p_trat")

    p_email    = st.text_input("📧 Email", value=user.get("email",""),
                                key="p_email", placeholder="juan@email.com")
    currencies = ["COP 🇨🇴", "USD 🇺🇸", "EUR 🇪🇺", "MXN 🇲🇽", "ARS 🇦🇷", "BRL 🇧🇷"]
    cur_curr   = user.get("currency", "COP 🇨🇴")
    p_currency = st.selectbox("💱 Moneda", currencies,
                               index=currencies.index(cur_curr) if cur_curr in currencies else 0,
                               key="p_currency")

    if st.button("💾 Guardar datos personales", type="primary",
                 use_container_width=True, key="save_profile"):
        if not p_nombre.strip():
            st.error("El nombre no puede estar vacío.")
        else:
            user["nombre"]      = p_nombre.strip()
            user["tratamiento"] = "" if p_trat == "(ninguno)" else p_trat
            user["email"]       = p_email.strip()
            user["currency"]    = p_currency
            users[username]     = user
            if storage.save_users(users, sha):
                st.session_state.user_data = user
                st.success("✅ Datos actualizados.")
                st.rerun()
            else:
                st.error("Error al guardar.")

    st.markdown("---")

    # ── Cambiar contraseña ────────────────────────────────────────────────────
    st.markdown("### 🔒 Cambiar contraseña")

    with st.expander("Cambiar contraseña"):
        cp_actual = st.text_input("Contraseña actual", type="password",
                                   key="cp_actual", placeholder="••••••••")
        cp_new1   = st.text_input("Nueva contraseña", type="password",
                                   key="cp_new1", placeholder="Mínimo 6 caracteres")
        cp_new2   = st.text_input("Confirmar nueva contraseña", type="password",
                                   key="cp_new2", placeholder="Repite la nueva contraseña")

        if st.button("Cambiar contraseña", type="primary",
                     use_container_width=True, key="btn_change_pw"):
            errs = []
            if not cp_actual:
                errs.append("Ingresa tu contraseña actual.")
            elif user["password"] != _hash(cp_actual):
                errs.append("La contraseña actual no es correcta.")
            if len(cp_new1) < 6:
                errs.append("La nueva contraseña debe tener al menos 6 caracteres.")
            if cp_new1 != cp_new2:
                errs.append("Las contraseñas nuevas no coinciden.")

            if errs:
                for e in errs: st.error(e)
            else:
                # Re-fetch to get latest sha
                users2, sha2    = storage.get_users()
                users2[username]["password"] = _hash(cp_new1)
                if storage.save_users(users2, sha2):
                    st.session_state.user_data = users2[username]
                    st.success("✅ Contraseña cambiada correctamente.")
                    st.rerun()
                else:
                    st.error("Error al guardar.")


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


# ═══════════════════════════════════════════════════════════════════════════════
#  GRUPOS DE GASTOS COMPARTIDOS
# ═══════════════════════════════════════════════════════════════════════════════

# Groups module - will be appended to app.py

GROUPS_TYPES = ["🏠 Hogar", "✈️ Viaje", "🎉 Evento", "🍽️ Comidas", "💼 Trabajo", "📦 Otro"]

# ── Group helpers ─────────────────────────────────────────────────────────────

def _calc_balances(expenses, settlements, members):
    """
    Calcula el balance neto de cada miembro.
    positivo = le deben a él/ella
    negativo = él/ella debe
    """
    bal = {m: 0.0 for m in members}
    for exp in expenses:
        paid_by = exp.get("paid_by", "")
        if paid_by in bal:
            bal[paid_by] += exp.get("amount", 0)
        for uname, share in exp.get("participants", {}).items():
            if uname in bal:
                bal[uname] -= share
    for s in settlements:
        frm = s.get("from_user", "")
        to  = s.get("to_user", "")
        amt = s.get("amount", 0)
        if frm in bal: bal[frm] += amt   # pagó → reduce lo que debe
        if to  in bal: bal[to]  -= amt   # recibió → reduce lo que le deben
    return bal

def _simplify_debts(balances):
    """
    Algoritmo de simplificación de deudas.
    Retorna lista de {from, to, amount} con el mínimo de transacciones.
    """
    pos = sorted([(v, k) for k, v in balances.items() if v > 0.01], reverse=True)
    neg = sorted([(-v, k) for k, v in balances.items() if v < -0.01], reverse=True)
    txs = []
    i = j = 0
    while i < len(pos) and j < len(neg):
        credit, creditor = pos[i]
        debt,   debtor   = neg[j]
        amt = min(credit, debt)
        txs.append({"from": debtor, "to": creditor, "amount": round(amt, 2)})
        pos[i] = (credit - amt, creditor)
        neg[j] = (debt   - amt, debtor)
        if pos[i][0] < 0.01: i += 1
        if neg[j][0] < 0.01: j += 1
    return txs

def _direct_debts(balances, username):
    """
    Deudas directas: quién le debe a username y a quién le debe username.
    """
    owed_to_me = []   # me deben
    i_owe      = []   # debo
    for uname, bal in balances.items():
        if uname == username:
            continue
        my_bal = -bal   # desde mi perspectiva
        if my_bal > 0.01:
            owed_to_me.append((uname, my_bal))
        elif my_bal < -0.01:
            i_owe.append((uname, -my_bal))
    return owed_to_me, i_owe

def _handle_group_invite(storage):
    """Procesa ?group=ID&join=1 en la URL para añadir al usuario al grupo."""
    group_id  = st.query_params.get("group", "")
    join_flag = st.query_params.get("join",  "")
    if not group_id or join_flag != "1":
        return
    if not st.session_state.logged_in:
        st.session_state.pending_group_join = group_id
        return

    username  = st.session_state.username
    group, sha = storage.get_group(group_id)
    if not group:
        return
    if username not in group.get("members", []):
        group["members"].append(username)
        storage.save_group(group_id, group, sha)
        ugroups, usha = storage.get_user_groups(username)
        if group_id not in ugroups:
            ugroups.append(group_id)
            storage.save_user_groups(username, ugroups, usha)
        st.session_state.page = "group_detail"
        st.session_state.current_group_id = group_id
    # Limpiar solo los params de join, conservar el token de sesión (?s=)
    try:
        st.query_params.pop("group", None)
        st.query_params.pop("join",  None)
    except Exception:
        pass

def _get_app_url() -> str:
    """Retorna la URL base de la app leyendo el host del contexto de Streamlit."""
    try:
        return st.secrets["APP_URL"].rstrip("/")
    except Exception:
        pass
    try:
        # Streamlit ≥1.31 expone st.context.headers con el Host
        host = st.context.headers.get("host", "")
        if host:
            return f"https://{host}"
    except Exception:
        pass
    return ""

# ── PAGES ─────────────────────────────────────────────────────────────────────

def page_groups():
    """Lista de grupos del usuario + crear grupo."""
    storage  = st.session_state.storage
    username = st.session_state.username

    # Verificar si hay invitación pendiente post-login
    pending = st.session_state.pop("pending_group_join", None)
    if pending:
        group, sha = storage.get_group(pending)
        if group and username not in group.get("members", []):
            group["members"].append(username)
            storage.save_group(pending, group, sha)
            ugroups, usha = storage.get_user_groups(username)
            if pending not in ugroups:
                ugroups.append(pending)
                storage.save_user_groups(username, ugroups, usha)

    st.markdown("## 👥 Gastos en Grupo")

    tab_list, tab_new = st.tabs(["📋 Mis grupos", "➕ Crear grupo"])

    # ── Tab: Lista de grupos ──────────────────────────────────────────────────
    with tab_list:
        ugroups, _ = storage.get_user_groups(username)
        if not ugroups:
            st.info("Aún no perteneces a ningún grupo. ¡Crea uno o únete con un enlace!")
        else:
            for gid in ugroups:
                group, _ = storage.get_group(gid)
                if not group:
                    continue
                n_members  = len(group.get("members", []))
                expenses,_ = storage.get_group_expenses(gid)
                total_exp  = sum(e.get("amount", 0) for e in expenses)
                img_b64    = group.get("image_b64", "")
                gtype      = group.get("type", "📦 Otro")
                date_str   = ""
                if group.get("permanent"):
                    date_str = "Permanente"
                elif group.get("date_start"):
                    date_str = f"{group['date_start']} → {group.get('date_end', '...')}"

                col_img, col_info, col_btn = st.columns([1, 5, 2])
                with col_img:
                    if img_b64:
                        st.image(f"data:image/png;base64,{img_b64}", width=70)
                    else:
                        st.markdown(
                            f"<div style='width:70px;height:70px;border-radius:12px;"
                            f"background:linear-gradient(135deg,#667eea,#764ba2);"
                            f"display:flex;align-items:center;justify-content:center;"
                            f"font-size:2rem;'>{gtype[0]}</div>",
                            unsafe_allow_html=True,
                        )
                with col_info:
                    st.markdown(
                        f"**{group.get('name','Sin nombre')}** · {gtype}\n\n"
                        f"👥 {n_members} miembros · 💸 ${total_exp:,.0f} en gastos · 📅 {date_str}"
                    )
                with col_btn:
                    if st.button("Ver grupo →", key=f"view_{gid}", use_container_width=True, type="primary"):
                        st.session_state.page = "group_detail"
                        st.session_state.current_group_id = gid
                        st.rerun()
                st.markdown("---")

    # ── Tab: Crear grupo ──────────────────────────────────────────────────────
    with tab_new:
        st.markdown("### Nuevo grupo")
        g_name = st.text_input("📝 Nombre del grupo", placeholder="Viaje a Cartagena, Hogar 2025…")
        g_type = st.selectbox("📂 Tipo", GROUPS_TYPES)
        g_perm = st.checkbox("♾️ Grupo permanente (sin fecha de fin)", value=False)

        if not g_perm:
            gc1, gc2 = st.columns(2)
            with gc1:
                g_start = st.date_input("📅 Desde", value=date.today())
            with gc2:
                g_end   = st.date_input("📅 Hasta", value=date.today())
        else:
            g_start = g_end = None

        g_img_file = st.file_uploader("🖼️ Imagen del grupo (opcional)", type=["png","jpg","jpeg","webp"])
        g_img_b64  = ""
        if g_img_file:
            g_img_b64 = base64.b64encode(g_img_file.read()).decode("utf-8")
            st.image(g_img_file, width=150)

        st.markdown("**📧 Invitar miembros (correos separados por coma):**")
        g_emails = st.text_input("Correos", placeholder="juan@email.com, maria@email.com")

        if st.button("✅ Crear grupo", type="primary", use_container_width=True, key="btn_create_group"):
            if not g_name.strip():
                st.error("El nombre del grupo es requerido.")
            else:
                gid = f"grp_{uuid.uuid4().hex[:12]}"
                group_data = {
                    "id":         gid,
                    "name":       g_name.strip(),
                    "type":       g_type,
                    "owner":      username,
                    "members":    [username],
                    "permanent":  g_perm,
                    "date_start": g_start.isoformat() if g_start else "",
                    "date_end":   g_end.isoformat()   if g_end   else "",
                    "image_b64":  g_img_b64,
                    "smart_settle": False,
                    "created_at": datetime.utcnow().isoformat(),
                }
                storage.save_group(gid, group_data)
                storage.save_group_expenses(gid, [])
                storage.save_group_settlements(gid, [])
                ugroups, usha = storage.get_user_groups(username)
                ugroups.append(gid)
                storage.save_user_groups(username, ugroups, usha)

                # Generar link de invitación
                st.success(f"✅ Grupo **{g_name}** creado!")
                st.markdown("**🔗 Enlace de invitación:**")
                base_url    = _get_app_url()
                invite_link = f"{base_url}/?group={gid}&join=1" if base_url else ""
                if invite_link:
                    st.code(invite_link, language=None)
                else:
                    st.info("No se pudo generar el link automáticamente. Copia tu URL de la app y agrega al final:")
                    st.code(f"?group={gid}&join=1", language=None)
                st.caption("Los miembros deben tener cuenta en FinanceTracker para unirse al grupo.")

                # Enviar correos de invitación
                if g_emails.strip():
                    emails = [e.strip() for e in g_emails.split(",") if "@" in e.strip()]
                    for email in emails:
                        try:
                            import resend
                            resend.api_key = st.secrets["email"]["resend_api_key"]
                            resend.Emails.send({
                                "from":    "FinanceTracker <onboarding@resend.dev>",
                                "to":      [email],
                                "subject": f"[FinanceTracker] Te invitaron al grupo: {g_name}",
                                "html":    f"""
                                <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:2rem;">
                                    <div style="background:linear-gradient(135deg,#667eea,#764ba2);
                                                padding:1.5rem;border-radius:14px;text-align:center;color:white;">
                                        <div style="font-size:2.5rem;">👥</div>
                                        <h2 style="margin:.3rem 0;">FinanceTracker</h2>
                                    </div>
                                    <div style="padding:1.5rem 0;">
                                        <p><strong>{username}</strong> te invitó al grupo <strong>{g_name}</strong>.</p>
                                        <p>Haz clic para unirte:</p>
                                        <a href="{invite_link}" style="display:block;background:#667eea;
                                           color:white;text-align:center;padding:.9rem;border-radius:10px;
                                           text-decoration:none;font-weight:700;margin:1rem 0;">
                                           Unirme al grupo →
                                        </a>
                                        <p style="color:#888;font-size:.85rem;">
                                            Necesitas tener cuenta en FinanceTracker para unirte.
                                        </p>
                                    </div>
                                </div>""",
                            })
                        except Exception:
                            pass
                    st.info(f"📧 Invitaciones enviadas a {len(emails)} correo(s).")

                st.session_state.page = "group_detail"
                st.session_state.current_group_id = gid
                st.rerun()


def page_group_detail():
    """Vista detallada de un grupo: gastos, deudas, configuración."""
    storage  = st.session_state.storage
    username = st.session_state.username
    group_id = st.session_state.get("current_group_id", "")

    if not group_id:
        st.session_state.page = "groups"
        st.rerun()

    group, g_sha = storage.get_group(group_id)
    if not group:
        st.error("Grupo no encontrado.")
        if st.button("← Volver"): st.session_state.page = "groups"; st.rerun()
        return

    if username not in group.get("members", []):
        st.error("No eres miembro de este grupo.")
        return

    members = group.get("members", [])
    # NOTE: expenses and settlements are read FRESH inside each tab
    # to always reflect the latest data from all users.

    # ── Header del grupo ──────────────────────────────────────────────────────
    hc1, hc2 = st.columns([1, 6])
    with hc1:
        if group.get("image_b64"):
            st.image(f"data:image/png;base64,{group['image_b64']}", width=80)
        else:
            st.markdown(
                f"<div style='width:80px;height:80px;border-radius:14px;"
                f"background:linear-gradient(135deg,#667eea,#764ba2);"
                f"display:flex;align-items:center;justify-content:center;"
                f"font-size:2.5rem;'>{group.get('type','📦')[0]}</div>",
                unsafe_allow_html=True,
            )
    with hc2:
        st.markdown(f"## {group.get('name','Grupo')}")
        date_str = "Permanente" if group.get("permanent") else \
                   f"{group.get('date_start','')} → {group.get('date_end','')}"
        st.caption(f"{group.get('type','')} · {date_str} · {len(members)} miembros: {', '.join(members)}")

    if st.button("← Mis grupos", key="back_groups"):
        st.session_state.page = "groups"; st.rerun()

    st.markdown("---")

    tab_exp, tab_debts, tab_settle, tab_config = st.tabs(
        ["💸 Gastos", "📊 Deudas", "💳 Liquidar", "⚙️ Configuración"]
    )

    # ════ TAB: GASTOS ════════════════════════════════════════════════════════
    with tab_exp:
        expenses, _ = storage.get_group_expenses(group_id)
        if st.button("➕ Agregar gasto", type="primary", key="btn_add_gexp"):
            st.session_state.group_adding_expense = True

        if st.session_state.get("group_adding_expense"):
            # Cargar nombres de todos los miembros
            all_users, _ = storage.get_users()
            name_of = {m: _get_display_name(all_users, m) for m in members}
            # paid_by default = usuario actual
            paid_by_default = members.index(username) if username in members else 0

            st.markdown("#### ➕ Nuevo gasto del grupo")
            fe1, fe2 = st.columns(2)
            with fe1:
                e_desc   = st.text_input("📝 Descripción", placeholder="Hotel, cena, gasolina…",
                                          key="gexp_desc")
                e_amount = st.number_input("💵 Monto total", min_value=0.0, step=1000.0,
                                            format="%.2f", key="gexp_amount")
                e_date   = st.date_input("📅 Fecha", value=date.today(), key="gexp_date")
            with fe2:
                e_paid_by = st.selectbox(
                    "👤 ¿Quién pagó?",
                    members,
                    index=paid_by_default,
                    format_func=lambda m: name_of.get(m, m),
                    key="gexp_paidby",
                )
                e_cat = st.selectbox("🏷️ Categoría", [
                    "🍽️ Comida", "🏨 Alojamiento", "🚗 Transporte",
                    "🎬 Entretenimiento", "🛍️ Compras", "💊 Salud",
                    "🎁 Regalos", "📋 Otro",
                ], key="gexp_cat")
                e_currency = st.selectbox(
                    "💱 Moneda",
                    ["COP 🇨🇴", "USD 🇺🇸", "EUR 🇪🇺", "MXN 🇲🇽",
                     "ARS 🇦🇷", "BRL 🇧🇷", "GBP 🇬🇧", "JPY 🇯🇵",
                     "CAD 🇨🇦", "AUD 🇦🇺", "CHF 🇨🇭"],
                    key="gexp_currency",
                )
                e_split = st.selectbox(
                    "⚖️ Dividir entre",
                    ["Partes iguales", "Por porcentaje", "Montos específicos"],
                    key="gexp_split",
                )

            # ── Participantes según modo de división ─────────────────────────
            st.markdown("**¿Quiénes participaron?**")
            participants = {}
            split_ok     = True

            if e_split == "Partes iguales":
                # Checkboxes: todos seleccionados por default
                selected = []
                cols_cb  = st.columns(min(len(members), 4))
                for i, m in enumerate(members):
                    with cols_cb[i % len(cols_cb)]:
                        checked = st.checkbox(name_of[m], value=True, key=f"cb_{m}")
                        if checked:
                            selected.append(m)
                if selected:
                    share = round(e_amount / len(selected), 2) if e_amount else 0
                    participants = {m: share for m in selected}
                    st.caption(f"Cada uno paga **${share:,.2f}** ({len(selected)} personas)")
                else:
                    st.warning("Selecciona al menos un participante.")
                    split_ok = False

            elif e_split == "Por porcentaje":
                st.caption("Los porcentajes deben sumar exactamente 100%")
                pcts = {}
                default_pct = round(100 / len(members), 1) if members else 0
                for m in members:
                    pc1, pc2 = st.columns([3, 2])
                    pc1.markdown(f"**{name_of[m]}**")
                    pcts[m] = pc2.number_input(
                        "  %", 0.0, 100.0, value=default_pct,
                        step=0.1, format="%.1f", key=f"pct_{m}",
                        label_visibility="collapsed",
                    )
                total_pct = sum(pcts.values())
                diff_pct  = abs(total_pct - 100)
                if diff_pct > 0.1:
                    st.error(f"Suma actual: **{total_pct:.1f}%** — faltan **{100-total_pct:.1f}%** para llegar a 100%")
                    split_ok = False
                else:
                    st.success(f"✅ Suma: {total_pct:.1f}%")
                    participants = {m: round(e_amount * p / 100, 2) for m, p in pcts.items() if p > 0}

            else:  # Montos específicos
                st.caption("Los montos deben sumar exactamente el total del gasto")
                amts = {}
                default_amt = float(round(e_amount / len(members), 2)) if members and e_amount else 0.0
                for m in members:
                    ac1, ac2 = st.columns([3, 2])
                    ac1.markdown(f"**{name_of[m]}**")
                    amts[m] = ac2.number_input(
                        "  $", min_value=0.0, value=default_amt,
                        step=1000.0, format="%.2f", key=f"amt_{m}",
                        label_visibility="collapsed",
                    )
                total_amts = sum(amts.values())
                diff_amts  = abs(total_amts - e_amount)
                if e_amount > 0 and diff_amts > 1:
                    st.error(f"Suma actual: **${total_amts:,.2f}** — diferencia: **${diff_amts:,.2f}**")
                    split_ok = False
                else:
                    if e_amount > 0:
                        st.success(f"✅ Suma: ${total_amts:,.2f}")
                    participants = {m: round(v, 2) for m, v in amts.items() if v > 0}

            st.markdown("")
            col_save, col_cancel = st.columns(2)
            if col_save.button("💾 Guardar gasto", type="primary",
                                use_container_width=True, key="gexp_save"):
                errs = []
                if not e_desc.strip():           errs.append("La descripción es requerida.")
                if e_amount <= 0:                errs.append("El monto debe ser mayor que 0.")
                if not participants:             errs.append("Selecciona al menos un participante.")
                if not split_ok:                 errs.append("Corrige la división antes de guardar.")
                if errs:
                    for e in errs: st.error(e)
                else:
                    expenses_data, e_sha = storage.get_group_expenses(group_id)
                    expenses_data.append({
                        "id":           str(uuid.uuid4()),
                        "description":  e_desc.strip(),
                        "amount":       float(e_amount),
                        "paid_by":      e_paid_by,
                        "date":         e_date.isoformat(),
                        "category":     e_cat,
                        "currency":     e_currency,
                        "split_type":   e_split,
                        "participants": participants,
                        "created_by":   username,
                        "created_at":   datetime.utcnow().isoformat(),
                    })
                    if storage.save_group_expenses(group_id, expenses_data, e_sha):
                        st.session_state.group_adding_expense = False
                        st.success("✅ Gasto guardado.")
                        st.rerun()
                    else:
                        st.error("Error al guardar.")
            if col_cancel.button("✕ Cancelar", use_container_width=True, key="gexp_cancel"):
                st.session_state.group_adding_expense = False
                st.rerun()

        # Listar gastos
        if not expenses:
            st.info("Sin gastos aún. ¡Agrega el primero!")
        else:
            all_users_exp, _ = storage.get_users()
            nm = {m: _get_display_name(all_users_exp, m) for m in members}
            for exp in sorted(expenses, key=lambda x: x.get("date",""), reverse=True):
                parts_str = " · ".join(
                    f"{nm.get(m,m)}: ${v:,.0f}"
                    for m, v in exp.get("participants", {}).items()
                )
                payer    = nm.get(exp.get("paid_by",""), exp.get("paid_by",""))
                curr_sym = exp.get("currency", "").split()[0] if exp.get("currency") else "$"
                ec1, ec2 = st.columns([6, 1])
                with ec1:
                    st.markdown(
                        f"**{exp.get('category','')} {exp.get('description','')}** — "
                        f"{curr_sym}{exp.get('amount',0):,.0f} · pagó **{payer}** · {exp.get('date','')}"
                        f"\n\n<span style='font-size:.83rem;opacity:.7;'>"
                        f"{exp.get('split_type','')} → {parts_str}</span>",
                        unsafe_allow_html=True,
                    )
                with ec2:
                    if group.get("owner") == username or exp.get("created_by") == username:
                        if st.button("🗑️", key=f"del_exp_{exp['id']}", help="Eliminar"):
                            expenses_data, e_sha = storage.get_group_expenses(group_id)
                            expenses_data = [e for e in expenses_data if e["id"] != exp["id"]]
                            storage.save_group_expenses(group_id, expenses_data, e_sha)
                            st.rerun()
                st.markdown("<hr style='margin:.3rem 0;opacity:.15;'>", unsafe_allow_html=True)

    # ════ TAB: DEUDAS ════════════════════════════════════════════════════════
    with tab_debts:
        expenses,_    = storage.get_group_expenses(group_id)
        settlements,_ = storage.get_group_settlements(group_id)
        balances = _calc_balances(expenses, settlements, members)
        smart    = group.get("smart_settle", False)

        st.markdown(f"#### {'🔀 Deudas simplificadas' if smart else '💬 Deudas directas'}")

        if smart:
            txs = _simplify_debts(balances)
            if not txs:
                st.success("✅ ¡Todo está saldado!")
            else:
                for tx in txs:
                    arrow = "→"
                    is_me = tx["from"] == username or tx["to"] == username
                    color = "#667eea" if is_me else "var(--text-color)"
                    st.markdown(
                        f"<div style='padding:.6rem 1rem;border-radius:10px;"
                        f"background:var(--card-bg);margin:.3rem 0;"
                        f"border-left:4px solid {color};'>"
                        f"<strong style='color:{color};'>{tx['from']}</strong> debe pagarle "
                        f"<strong>${tx['amount']:,.0f}</strong> a "
                        f"<strong style='color:{color};'>{tx['to']}</strong>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
        else:
            owed_to_me, i_owe = _direct_debts(balances, username)
            if not owed_to_me and not i_owe:
                st.success("✅ ¡Todo está saldado!")
            else:
                if owed_to_me:
                    st.markdown("**Te deben:**")
                    for uname, amt in owed_to_me:
                        st.markdown(
                            f"<div style='padding:.6rem 1rem;border-radius:10px;"
                            f"background:var(--card-bg);margin:.3rem 0;"
                            f"border-left:4px solid #51CF66;'>"
                            f"🟢 <strong>{uname}</strong> te debe <strong>${amt:,.0f}</strong>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                if i_owe:
                    st.markdown("**Debes:**")
                    for uname, amt in i_owe:
                        st.markdown(
                            f"<div style='padding:.6rem 1rem;border-radius:10px;"
                            f"background:var(--card-bg);margin:.3rem 0;"
                            f"border-left:4px solid #FF6B6B;'>"
                            f"🔴 Le debes <strong>${amt:,.0f}</strong> a <strong>{uname}</strong>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

        # Balance por persona
        st.markdown("---")
        st.markdown("**Balance neto de cada miembro:**")
        b_cols = st.columns(len(members))
        for col, m in zip(b_cols, members):
            val = balances.get(m, 0)
            icon = "💚" if val > 0.01 else ("🔴" if val < -0.01 else "✅")
            col.metric(f"{icon} {m}", f"${val:,.0f}",
                       delta="a favor" if val > 0 else ("saldado" if abs(val) < 0.01 else "debe"))

    # ════ TAB: LIQUIDAR ══════════════════════════════════════════════════════
    with tab_settle:
        # Read fresh data
        expenses_s,_    = storage.get_group_expenses(group_id)
        settlements_s,_ = storage.get_group_settlements(group_id)
        balances_s      = _calc_balances(expenses_s, settlements_s, members)

        st.markdown("#### 💳 Registrar un pago")

        # Tipo primero
        s_type = st.selectbox("Tipo de pago", ["Pago de deuda", "Adelanto"],
                               key="settle_type")
        s_date = st.date_input("Fecha", value=date.today(), key="settle_date")

        sc1, sc2 = st.columns(2)
        with sc1:
            s_from = st.selectbox("Quien paga", members,
                                   index=members.index(username) if username in members else 0,
                                   key="settle_from")
        with sc2:
            others = [m for m in members if m != s_from]
            s_to   = st.selectbox("A quién", others, key="settle_to") if others else None

        # Para Pago de deuda: sugerir el monto que se debe
        if s_type == "Pago de deuda" and s_to:
            # Cuánto debe s_from a s_to
            my_bal = balances_s.get(s_from, 0)
            other_bal = balances_s.get(s_to, 0)
            suggested = 0.0
            if my_bal < 0:   # s_from debe plata
                # Buscar cuánto le debe a s_to específicamente
                # (en modo directo es simplificado, usamos el balance neto)
                suggested = max(0, min(-my_bal, other_bal))
            s_amt = st.number_input("Monto", min_value=0.0, step=1000.0,
                                     format="%.2f", value=float(suggested),
                                     key="settle_amt",
                                     help="Monto sugerido según el balance actual")
        else:
            # Adelanto: monto libre
            s_amt = st.number_input("Monto del adelanto", min_value=0.0,
                                     step=1000.0, format="%.2f",
                                     key="settle_amt_adv")

        if st.button("💾 Registrar pago", type="primary",
                     use_container_width=True, key="btn_settle"):
            if not s_to:
                st.error("Necesitas al menos 2 miembros para registrar un pago.")
            elif s_amt <= 0:
                st.error("El monto debe ser mayor que 0.")
            else:
                sdata, s_sha = storage.get_group_settlements(group_id)
                sdata.append({
                    "id":         str(uuid.uuid4()),
                    "from_user":  s_from,
                    "to_user":    s_to,
                    "amount":     float(s_amt),
                    "date":       s_date.isoformat(),
                    "type":       s_type,
                    "created_by": username,
                    "created_at": datetime.utcnow().isoformat(),
                })
                if storage.save_group_settlements(group_id, sdata, s_sha):
                    st.success(f"✅ {s_type}: {s_from} → {s_to} · ${s_amt:,.0f}")
                    st.rerun()
                else:
                    st.error("Error al guardar.")

        # Historial de pagos
        if settlements_s:
            st.markdown("---")
            st.markdown("**Historial de pagos:**")
            for s in sorted(settlements_s, key=lambda x: x.get("date",""), reverse=True):
                icon = "💸" if s.get("type") == "Pago de deuda" else "⏩"
                st.markdown(
                    f"<div style='padding:.5rem .9rem;border-radius:9px;"
                    f"background:var(--card-bg);margin:.25rem 0;font-size:.88rem;'>"
                    f"{icon} <strong>{s['from_user']}</strong> → <strong>{s['to_user']}</strong> "
                    f"· ${s.get('amount',0):,.0f} · {s.get('date','')} · {s.get('type','')}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ════ TAB: CONFIGURACIÓN ════════════════════════════════════════════════
    with tab_config:
        # Refresh button — fuerza nueva lectura de datos para todos
        rc1, rc2 = st.columns([6, 1])
        rc1.markdown("#### ⚙️ Configuración del grupo")
        if rc2.button("🔄", help="Actualizar datos del grupo", key="cfg_refresh"):
            st.rerun()

        # Link de invitación
        st.markdown("**🔗 Enlace de invitación:**")
        base_url = _get_app_url()
        if base_url:
            invite_link = f"{base_url}/?group={group_id}&join=1"
            st.code(invite_link, language=None)
        else:
            st.markdown("Copia tu URL de la app y agrega al final:")
            st.code(f"?group={group_id}&join=1", language=None)
        st.caption("Cualquier persona con este link y cuenta puede unirse al grupo.")

        # Smart settle toggle
        st.markdown("---")
        smart_current = group.get("smart_settle", False)
        new_smart = st.toggle(
            "🔀 Activar simplificación de deudas",
            value=smart_current,
            help="Minimiza el número de pagos necesarios para saldar todas las deudas del grupo.",
        )
        if new_smart != smart_current:
            group["smart_settle"] = new_smart
            storage.save_group(group_id, group, g_sha)
            st.success("✅ Configuración guardada.")
            st.rerun()
        if new_smart:
            st.caption("🔀 Activado: el sistema redistribuye deudas para minimizar transacciones.")
        else:
            st.caption("💬 Desactivado: cada quien ve cuánto le debe a quién directamente.")

        # ── Miembros actuales ─────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**👥 Miembros del grupo:**")
        is_owner = group.get("owner") == username
        for m in list(members):
            mc1, mc2 = st.columns([6, 1])
            role = "👑 Creador" if m == group.get("owner") else "👤 Miembro"
            mc1.markdown(f"{role} · **{m}**")
            # Owner puede sacar a otros; no se puede sacar a sí mismo si es owner
            if is_owner and m != username:
                if mc2.button("✕", key=f"kick_{m}", help=f"Sacar a {m} del grupo"):
                    fresh_g, fresh_sha = storage.get_group(group_id)
                    fresh_g["members"] = [x for x in fresh_g.get("members",[]) if x != m]
                    storage.save_group(group_id, fresh_g, fresh_sha)
                    ugrps, usha = storage.get_user_groups(m)
                    ugrps = [g for g in ugrps if g != group_id]
                    storage.save_user_groups(m, ugrps, usha)
                    st.success(f"✅ {m} fue removido del grupo.")
                    st.rerun()

        # ── Salir del grupo (no-owner) ─────────────────────────────────────────
        if not is_owner:
            st.markdown("---")
            with st.expander("🚪 Salir del grupo"):
                st.warning("Dejarás de ver los gastos y deudas de este grupo.")
                if st.button("Salir del grupo", type="secondary", key="cfg_leave"):
                    fresh_g, fresh_sha = storage.get_group(group_id)
                    fresh_g["members"] = [x for x in fresh_g.get("members",[]) if x != username]
                    storage.save_group(group_id, fresh_g, fresh_sha)
                    ugrps, usha = storage.get_user_groups(username)
                    ugrps = [g for g in ugrps if g != group_id]
                    storage.save_user_groups(username, ugrps, usha)
                    st.session_state.page = "groups"
                    st.rerun()

        # ── Solo owner: editar nombre/imagen y eliminar ────────────────────────
        if is_owner:
            st.markdown("---")
            st.markdown("**✏️ Editar grupo:**")
            new_name = st.text_input("Nombre", value=group.get("name",""), key="cfg_name")
            new_type = st.selectbox("Tipo", GROUPS_TYPES,
                                     index=GROUPS_TYPES.index(group.get("type", GROUPS_TYPES[0]))
                                     if group.get("type") in GROUPS_TYPES else 0, key="cfg_type")
            new_img_file = st.file_uploader("Nueva imagen (opcional)",
                                             type=["png","jpg","jpeg","webp"], key="cfg_img")
            if st.button("💾 Guardar cambios", key="cfg_save", type="primary"):
                group["name"] = new_name.strip()
                group["type"] = new_type
                if new_img_file:
                    group["image_b64"] = base64.b64encode(new_img_file.read()).decode("utf-8")
                storage.save_group(group_id, group, g_sha)
                st.success("✅ Grupo actualizado.")
                st.rerun()

            st.markdown("---")
            with st.expander("⚠️ Eliminar grupo"):
                st.warning("Esta acción es irreversible y eliminará todos los gastos del grupo.")
                if st.button("🗑️ Eliminar grupo", type="secondary", key="cfg_delete"):
                    for u in group.get("members", []):
                        ugrps, usha = storage.get_user_groups(u)
                        ugrps = [g for g in ugrps if g != group_id]
                        storage.save_user_groups(u, ugrps, usha)
                    st.session_state.page = "groups"
                    st.rerun()


def page_more():
    """Página de opciones: Presupuestos, Categorías, Perfil, Logout."""
    _render_greeting()
    st.markdown("### ⚙️ Opciones")

    options = [
        ("🎯", "Presupuestos",    "budgets",    "Gestiona tus metas de gasto e ingreso"),
        ("🏷️", "Mis categorías",  "categories", "Personaliza tus categorías"),
        ("👤", "Mi perfil",       "profile",    "Nombre, tratamiento, correo y contraseña"),
    ]
    for icon, label, key, desc in options:
        col1, col2 = st.columns([8, 1])
        with col1:
            st.markdown(
                f"""<div class="tx-card" style="cursor:pointer;padding:.7rem 1rem;">
                    <div>
                        <strong>{icon} {label}</strong>
                        <br><span style="font-size:.82rem;opacity:.6;">{desc}</span>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
        with col2:
            if st.button("›", key=f"more_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()

    st.markdown("---")
    if st.button("🚪 Cerrar sesión", type="secondary", use_container_width=True,
                 key="more_logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


def _process_group_join(storage, username):
    """
    Une al usuario a un grupo si hay un join pendiente en session_state
    (guardado antes del login desde los query_params).
    Retorna True si se procesó algún join.
    """
    group_id = st.session_state.pop("pending_group_join", None) or ""
    if not group_id:
        return False

    group, sha = storage.get_group(group_id)
    if not group:
        st.warning("El enlace de invitación no es válido o el grupo fue eliminado.")
        return False

    if username not in group.get("members", []):
        group["members"].append(username)
        storage.save_group(group_id, group, sha)
        ugroups, usha = storage.get_user_groups(username)
        if group_id not in ugroups:
            ugroups.append(group_id)
            storage.save_user_groups(username, ugroups, usha)

    st.session_state.current_group_id = group_id
    st.session_state.page = "group_detail"
    return True


def main():
    _init_session()
    _inject_css()
    _inject_pwa_meta()

    # Inicializar estados para grupos
    if "group_adding_expense" not in st.session_state:
        st.session_state.group_adding_expense = False
    if "current_group_id" not in st.session_state:
        st.session_state.current_group_id = ""

    if st.session_state.storage is None:
        try:
            st.session_state.storage = GitHubStorage()
        except Exception as exc:
            st.error(f"⚠️ Error de configuración: {exc}\n\n"
                     "Verifica los Secrets en Streamlit Cloud.")
            st.stop()

    storage = st.session_state.storage

    # ── Capturar invitación ANTES del login (persiste en session_state) ───────
    g_param = st.query_params.get("group", "")
    j_param = st.query_params.get("join",  "")
    if g_param and j_param == "1":
        st.session_state.pending_group_join = g_param
        # Limpiar params para que no confundan el session token
        st.query_params.pop("group", None)
        st.query_params.pop("join",  None)

    # ── Si no está logueado: mostrar pantalla de auth ─────────────────────────
    if not st.session_state.logged_in:
        # Invitación pendiente → ir directo al login, no al landing
        if st.session_state.get("pending_group_join"):
            if st.session_state.get("auth_mode", "landing") == "landing":
                st.session_state.auth_mode = "login"
        {"login": page_login, "register": page_register,
         "forgot": page_forgot_password}.get(
            st.session_state.get("auth_mode", "landing"), page_landing)()
        return

    # ── Logueado: procesar join pendiente y redirigir al grupo ───────────────
    if _process_group_join(storage, st.session_state.username):
        st.rerun()
        return

    _render_sidebar()   # no-op, kept for compatibility
    # Route — dashboard redirige a home (están fusionados)
    if st.session_state.page == "dashboard":
        st.session_state.page = "home"
    {"home": page_home, "add": page_add, "list": page_list,
     "categories": page_categories, "budgets": page_budgets,
     "profile": page_profile, "more": page_more,
     "groups": page_groups, "group_detail": page_group_detail,
     }.get(st.session_state.page, page_home)()
    _render_bottom_nav()

if __name__ == "__main__":
    main()
