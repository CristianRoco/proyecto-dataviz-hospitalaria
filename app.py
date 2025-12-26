import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# IDENTIDAD DEL PROYECTO 
# =========================
APP_NAME = "Gestión Hospitalaria y Producción de Servicios – DataViz (datos.gob.cl)"
COURSE = "Solemne II – DataViz Python (Unidad 3, Semana 13)"
TEAM = "Grupo: Camila Acuña – Juan Bravo – Katerine Chiguay - Cristian Roco"

st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption(f"{COURSE} | {TEAM}")

# Narrativa 
st.info(
    "📌 **Enfoque del proyecto:** Gestión hospitalaria y producción de servicios. "
    "La aplicación utiliza datos públicos desde **datos.gob.cl** (API CKAN REST), "
    "para explorar **volúmenes de producción**, distribución de indicadores, "
    "variabilidad y concentración por categorías (ej: servicio, establecimiento, región, año)."
)

with st.expander("Objetivo y preguntas guía", expanded=True):
    st.markdown(
        """
**Objetivo general:** Analizar datos públicos relacionados con **gestión hospitalaria y producción de servicios de salud**
utilizando **Python (requests + pandas + matplotlib + streamlit)**, a partir de consultas **GET** a una API REST pública (CKAN).

**Preguntas guía:**
- ¿Qué indicador numérico presenta mayor variabilidad o concentración?
- ¿Qué categorías (hospital/servicio/región/año) concentran los mayores valores (Top 15)?
- ¿Existen valores extremos (outliers) que puedan afectar la interpretación?
- ¿Cómo cambia la distribución del indicador al filtrar rangos?
        """
    )

# =========================
# ENDPOINTS CKAN (datos.gob.cl)
# =========================
BASE = "https://datos.gob.cl/api/3/action"
PACKAGE_SEARCH = f"{BASE}/package_search"
PACKAGE_SHOW = f"{BASE}/package_show"
DATASTORE_SEARCH = f"{BASE}/datastore_search"


# =========================
# HELPERS
# =========================
@st.cache_data(show_spinner=False)
def get_json(url, params=None, timeout=30):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

@st.cache_data(show_spinner=False)
def buscar_datasets(query, rows=20):
    data = get_json(PACKAGE_SEARCH, params={"q": query, "rows": rows})
    return data["result"]["results"]

@st.cache_data(show_spinner=False)
def obtener_dataset(dataset_id):
    data = get_json(PACKAGE_SHOW, params={"id": dataset_id})
    return data["result"]

@st.cache_data(show_spinner=False)
def cargar_recurso_datastore(resource_id, limit=5000):
    data = get_json(DATASTORE_SEARCH, params={"id": resource_id, "limit": limit})
    records = data["result"]["records"]
    return pd.DataFrame(records)

def cargar_recurso(resource, limit=5000):
    # DataStore (preferido)
    if resource.get("datastore_active"):
        return cargar_recurso_datastore(resource["id"], limit=limit)

    # CSV (alternativa)
    if (resource.get("format") or "").upper() == "CSV" and resource.get("url"):
        return pd.read_csv(resource["url"])

    return None

def numeric_cols(df: pd.DataFrame):
    return df.select_dtypes(include="number").columns.tolist()

def low_cardinality_cols(df: pd.DataFrame, max_unique=60):
    """Candidatas a categorías para análisis (pocas categorías)."""
    cols = []
    for c in df.columns:
        try:
            nun = df[c].nunique(dropna=True)
            if 2 <= nun <= max_unique:
                cols.append(c)
        except Exception:
            pass
    return cols


# =========================
# SIDEBAR: CONFIGURACIÓN (ENFOQUE HOSPITALARIO)
# =========================
st.sidebar.header("1) Búsqueda dirigida (gestión hospitalaria)")

# Búsqueda por defecto más alineada al tema 
query = st.sidebar.text_input(
    "Palabras clave (recomendadas: hospital, egresos, prestaciones, camas, urgencia, producción)",
    "hospital prestaciones producción"
)

rows = st.sidebar.slider("Cantidad de resultados", 5, 30, 20)
limit_rows = st.sidebar.slider("Máx filas a cargar (rendimiento)", 500, 10000, 5000, step=500)

if st.sidebar.button("Buscar datasets"):
    try:
        st.session_state["datasets"] = buscar_datasets(query, rows=rows)
        st.success("Búsqueda realizada.")
    except Exception as e:
        st.error(f"Error buscando datasets: {e}")

if "datasets" not in st.session_state:
    st.warning("Primero presiona **Buscar datasets** en el panel izquierdo.")
    st.stop()

datasets = st.session_state["datasets"]
if not datasets:
    st.error("No se encontraron datasets. Prueba otras palabras clave (ej: 'egresos hospitalarios', 'camas', 'urgencia').")
    st.stop()

# =========================
# 2) SELECCIÓN DE DATASET
# =========================
st.subheader("2) Selecciona un Dataset")
options = {f"{d.get('title','(sin título)')}": d["id"] for d in datasets}
ds_title = st.selectbox("Resultados", list(options.keys()))
ds_id = options[ds_title]

dataset = obtener_dataset(ds_id)
notes = dataset.get("notes") or ""

st.write("**Descripción (resumen):**")
st.write(notes[:900] + ("..." if len(notes) > 900 else ""))
st.write("**Fuente:** datos.gob.cl (API CKAN REST)")

resources = dataset.get("resources", [])
if not resources:
    st.warning("Este dataset no tiene recursos disponibles.")
    st.stop()

# =========================
# 3) SELECCIÓN DE RECURSO
# =========================
st.subheader("3) Selecciona un Recurso (tabla)")
res_options = {}
for r in resources:
    name = r.get("name") or r.get("id")
    fmt = (r.get("format") or "").upper()
    ds_flag = "DataStore ✅" if r.get("datastore_active") else "DataStore ❌"
    res_options[f"{name} | {fmt} | {ds_flag}"] = r

res_label = st.selectbox("Recursos", list(res_options.keys()))
resource = res_options[res_label]

# =========================
# 4) CARGA DE DATOS
# =========================
with st.spinner("Cargando datos del recurso..."):
    df = cargar_recurso(resource, limit=limit_rows)

if df is None or df.empty:
    st.error("No se pudo cargar este recurso. Prueba otro (ideal: DataStore ✅ o CSV).")
    st.stop()

# =========================
# 5) PERFIL RÁPIDO (KPIs + calidad de datos)
# =========================
st.subheader("4) Perfil rápido del dataset (gestión)")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Filas", f"{df.shape[0]:,}")
c2.metric("Columnas", f"{df.shape[1]:,}")
c3.metric("Nulos totales", f"{int(df.isna().sum().sum()):,}")
c4.metric("Columnas numéricas", f"{len(numeric_cols(df)):,}")
c5.metric("Categorías potenciales", f"{len(low_cardinality_cols(df)):,}")

st.markdown("**Vista previa (primeras 25 filas):**")
st.dataframe(df.head(25), use_container_width=True)

# =========================
# 6) ANÁLISIS INTERACTIVO (KPIs de gestión + filtros)
# =========================
st.subheader("5) Análisis interactivo (producción y gestión)")
num = numeric_cols(df)
if not num:
    st.warning("No hay columnas numéricas detectadas en este recurso. Prueba otro recurso del mismo dataset.")
    st.stop()

col = st.selectbox("Indicador numérico (producción, cantidad, total, etc.)", num)

# convertir a numérico por si viene como texto
df[col] = pd.to_numeric(df[col], errors="coerce")
serie = df[col].dropna()

if serie.empty:
    st.warning("La columna seleccionada no tiene valores numéricos válidos.")
    st.stop()

# filtro por rango (interacción)
minv, maxv = float(serie.min()), float(serie.max())
rango = st.slider("Filtro por rango del indicador", min_value=minv, max_value=maxv, value=(minv, maxv))
df_f = df[(df[col] >= rango[0]) & (df[col] <= rango[1])].copy()
s = df_f[col].dropna()

# KPIs de gestión (orientados a producción)
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Registros (filtrado)", f"{len(s):,}")
k2.metric("Suma (producción total)", f"{s.sum():,.2f}")
k3.metric("Promedio", f"{s.mean():,.2f}")
k4.metric("Mediana", f"{s.median():,.2f}")
k5.metric("P90", f"{s.quantile(0.90):,.2f}")
k6.metric("Máximo", f"{s.max():,.2f}")

st.write("**Estadísticas descriptivas (describe):**")
st.dataframe(s.describe().to_frame().T, use_container_width=True)

# =========================
# VISUALIZACIONES
# =========================
st.subheader("6) Visualizaciones")

# Histograma
st.markdown("### Histograma del indicador")
bins = st.slider("Bins (cantidad de barras)", 5, 80, 30)
fig1 = plt.figure()
plt.hist(s, bins=bins)
plt.title(f"Distribución de {col} (filtrado)")
plt.xlabel(col)
plt.ylabel("Frecuencia")
st.pyplot(fig1)

# Top por categoría
st.markdown("### Top 15 por categoría (ej: establecimiento/servicio/región/año)")
cat_candidates = [c for c in low_cardinality_cols(df_f) if c != col]
if cat_candidates:
    cat = st.selectbox("Columna categórica (pocas categorías)", cat_candidates)
    modo = st.radio("Resumen por categoría", ["Suma", "Promedio", "Conteo"], horizontal=True)

    tmp = df_f[[cat, col]].copy()
    tmp[cat] = tmp[cat].astype(str)

    if modo == "Suma":
        grp = tmp.groupby(cat)[col].sum().sort_values(ascending=False).head(15)
        ylabel = "Suma (producción)"
    elif modo == "Promedio":
        grp = tmp.groupby(cat)[col].mean().sort_values(ascending=False).head(15)
        ylabel = "Promedio"
    else:
        grp = tmp.groupby(cat)[col].count().sort_values(ascending=False).head(15)
        ylabel = "Conteo (registros)"

    fig2 = plt.figure()
    plt.bar(grp.index, grp.values)
    plt.title(f"Top 15 – {ylabel} de {col} por {cat}")
    plt.xlabel(cat)
    plt.ylabel(ylabel)
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig2)
else:
    st.info("No se detectaron columnas categóricas con pocas categorías para generar Top 15.")

# =========================
# CONCLUSIÓN AUTOMÁTICA 
# =========================
st.subheader("7) Conclusión automática")
asim = "positiva (cola a la derecha)" if s.mean() > s.median() else "negativa (cola a la izquierda)" if s.mean() < s.median() else "aprox. simétrica"

st.write(
    f"- Para el indicador **{col}**, la **producción total (suma)** en el rango filtrado es **{s.sum():,.2f}**.\n"
    f"- El promedio es **{s.mean():,.2f}** y la mediana es **{s.median():,.2f}**, lo que sugiere una distribución **{asim}**.\n"
    f"- El percentil 90 (P90) es **{s.quantile(0.90):,.2f}**, útil para identificar categorías/valores altos que concentran producción."
)

# Descarga CSV filtrado
st.download_button(
    "Descargar CSV (datos filtrados)",
    data=df_f.to_csv(index=False).encode("utf-8"),
    file_name="gestion_hospitalaria_datos_filtrados.csv",
    mime="text/csv"
)

st.caption("Fuente: datos.gob.cl (API CKAN REST). App desarrollada con Python + Pandas + Matplotlib + Streamlit.")
