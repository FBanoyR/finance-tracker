# 💰 FinanceTracker

Aplicación de gestión de finanzas personales construida con **Python + Streamlit**.  
Multi-usuario, sin base de datos — los datos se almacenan como JSON en un repositorio GitHub privado.

## ✨ Funcionalidades

- 🔐 Registro y login con nombre, tratamiento (Señor/Señora/Dr./Dra.) y contraseña segura
- 🏠 Saludo personalizado + resumen del mes en curso
- ➕ Registro de Gastos, Ingresos e Inversiones con categorías personalizables
- 📋 Tabla de transacciones filtrable y exportable a CSV
- 📊 Dashboard interactivo con filtros por año/mes y rolling N meses
- 🏷️ Categorías personalizadas por usuario con fallback "Sin asignar"
- 📱 Diseño responsive para móvil y escritorio

## 🗂️ Estructura

```
finance-tracker/          ← este repo (público)
├── app.py                ← toda la aplicación en un solo archivo
└── requirements.txt
```

Los datos viven en un segundo repo privado:
```
finance-tracker-data/     ← repo privado
└── data/
    ├── users.json
    └── transactions.json
```

## 🚀 Despliegue en Streamlit Cloud

1. Sube este repo a GitHub (puede ser público)
2. Crea un segundo repo **privado** para los datos con los archivos `data/users.json` (`{}`) y `data/transactions.json` (`[]`)
3. Genera un [Personal Access Token](https://github.com/settings/tokens) con permiso **Contents: read & write** sobre el repo de datos
4. En [share.streamlit.io](https://share.streamlit.io) despliega este repo con `app.py` como archivo principal
5. En **Settings → Secrets** pega:

```toml
[github]
token  = "ghp_TU_TOKEN_AQUI"
repo   = "tu-usuario/finance-tracker-data"
branch = "main"
```

## 🛠️ Desarrollo local

```bash
pip install -r requirements.txt

# Crea el archivo de secrets
mkdir .streamlit
echo '[github]\ntoken = "ghp_..."\nrepo = "usuario/finance-tracker-data"\nbranch = "main"' > .streamlit/secrets.toml

streamlit run app.py
```
