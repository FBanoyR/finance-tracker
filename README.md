# 💰 FinanceTracker

Aplicación de gestión de finanzas personales construida con **Python + Streamlit**.  
Multi-usuario, sin base de datos — los datos se almacenan como JSON en un repositorio GitHub.

---

## ✨ Funcionalidades

| Sección | Descripción |
|---|---|
| 🔐 Auth | Registro con nombre, tratamiento (Señor/Señora/Dr./Dra.) y contraseña segura |
| 🏠 Inicio | Saludo personalizado + resumen del mes en curso |
| ➕ Nueva transacción | Formulario con tipo (Gasto / Ingreso / Inversión), categoría dinámica, monto, fecha y descripción |
| 📋 Mis transacciones | Tabla filtrable por tipo, año, mes y palabra clave; exporta CSV |
| 📊 Dashboard | Gráficas interactivas Plotly, filtros por año/mes o rolling N meses, KPIs de balance y tasa de ahorro |

---

## 🚀 Despliegue paso a paso

### 1 · Prerrequisitos

- Cuenta en [GitHub](https://github.com)
- Cuenta en [Streamlit Community Cloud](https://streamlit.io/cloud) (gratuita)

---

### 2 · Repositorio de código (este repo)

```bash
# Clona / fork este repositorio y súbelo a tu GitHub
git clone https://github.com/TU_USUARIO/finance-tracker.git
cd finance-tracker
git remote set-url origin https://github.com/TU_USUARIO/finance-tracker.git
git push -u origin main
```

---

### 3 · Repositorio de datos

Crea un **segundo repositorio vacío** en GitHub, por ejemplo `finance-tracker-data`.  
Este repo almacenará `data/users.json` y `data/transactions.json`.  
Puede ser privado ✅ (recomendado).

---

### 4 · Personal Access Token de GitHub

1. Ve a **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens** (o classic tokens).
2. Crea un token con permiso **Contents: Read and Write** sobre el repo de datos.
3. Cópialo — solo se muestra una vez.

---

### 5 · Secrets en Streamlit Cloud

En Streamlit Cloud, al desplegar la app, ve a **"Advanced settings → Secrets"** y pega:

```toml
GITHUB_TOKEN  = "ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
GITHUB_REPO   = "tu-usuario/finance-tracker-data"
GITHUB_BRANCH = "main"
```

> Si corres en local, copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y rellena los valores.

---

### 6 · Desplegar en Streamlit Cloud

1. Entra a [share.streamlit.io](https://share.streamlit.io)
2. **New app → From existing repo**
3. Selecciona tu repo de código
4. Main file: `app.py`
5. Pega los secrets del paso anterior
6. Deploy 🎉

---

## 🛠 Desarrollo local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Copiar secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# → Edita secrets.toml con tu token y repo

# Correr
streamlit run app.py
```

---

## 📁 Estructura del proyecto

```
finance-tracker/
├── app.py                        # App principal (auth + todas las páginas)
├── storage.py                    # Capa de persistencia vía GitHub API
├── requirements.txt
├── .gitignore
└── .streamlit/
    ├── config.toml               # Tema de colores
    └── secrets.toml.example      # Plantilla de secrets (no subir secrets.toml real)
```

Los datos viven en el repo de datos:
```
finance-tracker-data/
└── data/
    ├── users.json          # Usuarios y contraseñas (hash SHA-256)
    └── transactions.json   # Todas las transacciones
```

---

## ⚠️ Notas importantes

- **Concurrencia**: GitHub no es una base de datos. Si dos personas guardan exactamente al mismo tiempo puede haber un conflicto. Para uso personal/familiar (pocas personas) funciona perfectamente.
- **Seguridad**: las contraseñas se almacenan como hash SHA-256 con salt. Nunca en texto plano.
- **Privacidad**: usa un repositorio de datos **privado** para proteger tu información financiera.
- **Rate limits**: la API de GitHub permite ~5 000 peticiones/hora con token autenticado, más que suficiente para este uso.

---

## 🎨 Capturas de pantalla

| Login | Home | Dashboard |
|---|---|---|
| Tabs Login / Registro | Saludo + métricas del mes | Gráficas interactivas Plotly |

---

## 📄 Licencia

MIT — libre para uso personal y comercial.
