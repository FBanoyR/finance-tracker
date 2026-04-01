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
            <div style="background:#f0f2f6;border-radius:12px;padding:1.2rem;
                        text-align:center;margin:1rem 0;">
                <span style="font-size:2.2rem;font-weight:700;letter-spacing:.4rem;
                             color:#667eea;">{code}</span>
            </div>
            <p style="color:#888;font-size:.88rem;">
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
    .budget-card {
        background:white; border-radius:14px; padding:1.2rem 1.4rem;
        box-shadow:0 2px 10px rgba(0,0,0,.07); margin-bottom:.8rem;
    }
    .budget-bar-bg {
        background:#f0f2f6; border-radius:8px; height:12px; margin:.5rem 0;
        overflow:hidden;
    }
    .budget-bar-fill {
        height:100%; border-radius:8px; transition:width .4s;
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
            "🎯 Presupuestos":      "budgets",
            "🏷️ Mis categorías":    "categories",
            "👤 Mi perfil":         "profile",
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
        if st.button("🔑 ¿Olvidaste tu contraseña?", key="forgot_pw",
                     use_container_width=True, type="secondary"):
            st.session_state.auth_mode = "forgot"; st.rerun()
        if st.button("← Volver al inicio", key="login_back", use_container_width=True):
            st.session_state.auth_mode = "landing"; st.rerun()
        st.markdown("<p style='text-align:center;color:#888;font-size:.88rem;margin-top:.8rem;'>¿No tienes cuenta?</p>",
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
            <p style="color:#888;">Te enviaremos un código a tu correo</p>
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
                    f"<div style='border-left:4px solid {color};background:white;"
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
                    f"""<div style="border-left:4px solid #FF6B6B;background:#fff5f5;
                        border-radius:10px;padding:.8rem 1rem;margin:.3rem 0;
                        box-shadow:0 2px 8px rgba(255,107,107,.2);">
                        <strong>🗑️ ¿Eliminar esta transacción?</strong><br>
                        <span style="color:#666;font-size:.88rem;">
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
                            <span style="color:#aaa;font-size:.8rem;margin-left:.5rem;">
                            {fecha} · {row['type']}</span></span>
                            {"<br><span style='color:#888;font-size:.82rem;padding-left:1rem;'>" + desc + "</span>" if desc else ""}
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
                f"""<div style="background:white;border-radius:12px;padding:1rem 1.4rem;
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
                        <span style="color:#aaa;font-size:.88rem;"> / ${pres:,.0f}</span>
                    </div>
                    <div class="budget-bar-bg">
                        <div class="budget-bar-fill" style="width:{pct:.0f}%;background:{bar_color};"></div>
                    </div>
                    <div style="font-size:.82rem;color:#666;margin-top:.4rem;">{resto_label}</div>
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
        {"login": page_login, "register": page_register,
         "forgot": page_forgot_password}.get(
            st.session_state.get("auth_mode", "landing"), page_landing)()
        return

    _render_sidebar()
    {"home": page_home, "add": page_add, "list": page_list,
     "dashboard": page_dashboard, "categories": page_categories,
     "budgets": page_budgets, "profile": page_profile,
     }.get(st.session_state.page, page_home)()

if __name__ == "__main__":
    main()
