
import os
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

st.set_page_config(page_title="Películas populares - TMDb", layout="wide")

COLOR_AZUL = "#1C4C9A"
COLOR_GRIS = "#B9C3D1"

st.title("Tablero de películas populares")
st.write("Fuente: The Movie Database (TMDb API) - discover/movie, ordenadas por popularidad, en español (es-MX).")


def obtener_token():
    try:
        token = st.secrets["tmdb_token"]
        if token:
            return str(token).strip()
    except Exception:
        pass
    token = os.environ.get("TMDB_TOKEN", "")
    if token:
        return token.strip()
    if os.path.exists("token.txt"):
        with open("token.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

API_KEY = obtener_token()

if not API_KEY or len(API_KEY) < 10:
    st.error("Falta tu token de TMDb.")
    st.write("1. Crea la carpeta .streamlit junto a este archivo.")
    st.write('2. Dentro, crea secrets.toml con: tmdb_token = "TU_TOKEN"')
    st.write("3. O deja tu token.txt de la práctica junto a este archivo, solo en tu computadora.")
    st.write("No subas secrets.toml ni token.txt a GitHub.")
    st.stop()

#  Cargar datos desde TMDb, con caché 
@st.cache_data(ttl=3600)
def cargar_peliculas(api_key, paginas):
    peliculas = []
    for pagina in range(1, paginas + 1):
        url = "https://api.themoviedb.org/3/discover/movie"
        params = {
            "api_key": api_key,
            "language": "es-MX",
            "sort_by": "popularity.desc",
            "page": pagina,
        }
        respuesta = requests.get(url, params=params, timeout=15)
        if respuesta.status_code == 401:
            raise ValueError("Error 401: el token de TMDb no es válido.")
        if respuesta.status_code == 429:
            raise ValueError("Error 429: se excedió el límite de peticiones de TMDb.")
        if respuesta.status_code != 200:
            raise ValueError(f"Error HTTP {respuesta.status_code} al consultar TMDb.")
        datos = respuesta.json()
        peliculas.extend(datos.get("results", []))
    return peliculas

#  Controles en la barra lateral 
st.sidebar.header("Controles")
paginas = st.sidebar.slider("Páginas a consultar (20 películas por página)", 1, 15, 5)
usar_cache_local = st.sidebar.checkbox("Usar respuesta.json local si existe", value=False)

peliculas_raw = None
if usar_cache_local and os.path.exists("respuesta.json"):
    with open("respuesta.json", "r", encoding="utf-8") as f:
        peliculas_raw = json.load(f)
    st.sidebar.success(f"Usando respuesta.json local: {len(peliculas_raw)} películas.")
else:
    try:
        with st.spinner(f"Consultando TMDb... {paginas} página(s)"):
            peliculas_raw = cargar_peliculas(API_KEY, paginas)
    except Exception as e:
        st.error(str(e))
        st.stop()

if not peliculas_raw:
    st.warning("TMDb no devolvió películas. Revisa tu token y tu conexión.")
    st.stop()

#  Limpieza, igual que en PracticaAPI_1.py 
df = pd.DataFrame(peliculas_raw)
columnas = ["title", "vote_average", "vote_count", "popularity", "release_date", "original_language"]
df = df[columnas]
df["vote_average"] = pd.to_numeric(df["vote_average"], errors="coerce")
df["vote_count"] = pd.to_numeric(df["vote_count"], errors="coerce")
df["popularity"] = pd.to_numeric(df["popularity"], errors="coerce")
df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
df_limpio = df.dropna(subset=["release_date", "vote_average", "vote_count", "popularity"]).copy()
df_limpio["release_year"] = df_limpio["release_date"].dt.year.astype(int)

st.sidebar.write(f"Registros cargados: {len(df)}")
st.sidebar.write(f"Registros limpios: {len(df_limpio)}")

# Filtros
anios = sorted(df_limpio["release_year"].unique())
anio_min, anio_max = st.sidebar.slider("Año de estreno", int(min(anios)), int(max(anios)), (int(min(anios)), int(max(anios))))
idiomas_disponibles = sorted(df_limpio["original_language"].unique())
idiomas = st.sidebar.multiselect("Idioma original", idiomas_disponibles, default=idiomas_disponibles)
votos_min = st.sidebar.slider("Mínimo de votos", 0, int(df_limpio["vote_count"].max()), 0)

df_f = df_limpio[
    (df_limpio["release_year"] >= anio_min)
    & (df_limpio["release_year"] <= anio_max)
    & (df_limpio["original_language"].isin(idiomas))
    & (df_limpio["vote_count"] >= votos_min)
].copy()

if df_f.empty:
    st.warning("Con esos filtros no queda ninguna película. Baja el mínimo de votos o amplía los años.")
    st.stop()

#  Indicadores 
col1, col2, col3, col4 = st.columns(4)
col1.metric("Películas en el tablero", len(df_f))
col2.metric("Calificación promedio", f"{df_f['vote_average'].mean():.2f} / 10")
col3.metric("Película más popular", str(df_f.sort_values("popularity", ascending=False).iloc[0]["title"]))
col4.metric("Idioma más frecuente", str(df_f["original_language"].value_counts().index[0]))

#  Gráfica 1: Distribución 
st.subheader("1. Distribución: ¿cómo se reparten las calificaciones?")
st.write("La mayoría de películas populares concentran sus notas entre 6.0 y 7.5 puntos.")
fig1, ax1 = plt.subplots(figsize=(9, 5))
sns.histplot(df_f["vote_average"], kde=True, color=COLOR_AZUL, bins=15, edgecolor="white", ax=ax1)
ax1.set_xlabel("Calificación promedio (0 a 10)")
ax1.set_ylabel("Número de películas")
ax1.grid(axis="y", linestyle="--", alpha=0.5)
st.pyplot(fig1)

#  Gráfica 2: Comparación 
st.subheader("2. Comparación: ¿qué idioma original domina?")
top_idiomas = df_f["original_language"].value_counts().head(5)
colores = [COLOR_AZUL if idx == top_idiomas.index[0] else COLOR_GRIS for idx in top_idiomas.index]
fig2, ax2 = plt.subplots(figsize=(9, 5))
sns.barplot(x=top_idiomas.index, y=top_idiomas.values, hue=top_idiomas.index, palette=colores, legend=False, ax=ax2)
ax2.set_xlabel("Código de idioma original (ISO 639-1)")
ax2.set_ylabel("Cantidad de películas")
ax2.grid(axis="y", linestyle="--", alpha=0.5)
st.pyplot(fig2)
st.write(f"El inglés ({top_idiomas.index[0] if top_idiomas.index[0] == 'en' else 'en'}) suele dominar el catálogo, con más del 75% en la práctica original de 300 películas.")

#  Gráfica 3: Relación 
st.subheader("3. Relación: votos vs. calificación")
st.write("Las películas con más de 10,000 votos tienden a una calificación superior a 6.5.")
fig3, ax3 = plt.subplots(figsize=(9, 5))
ax3.scatter(df_f["vote_count"], df_f["vote_average"], color=COLOR_AZUL, alpha=0.6)
ax3.set_xlabel("Cantidad total de votos")
ax3.set_ylabel("Calificación promedio (0 a 10)")
ax3.grid(True, linestyle="--", alpha=0.5)
st.pyplot(fig3)

#  Gráfica 4: Evolución 
st.subheader("4. Evolución: popularidad promedio por año de estreno")
evolucion = df_f.groupby("release_year")["popularity"].mean().reset_index()
evolucion = evolucion[evolucion["release_year"] >= 2010]
fig4, ax4 = plt.subplots(figsize=(9, 5))
ax4.plot(evolucion["release_year"], evolucion["popularity"], marker="o", color=COLOR_AZUL, linewidth=2.5)
ax4.set_xlabel("Año de estreno")
ax4.set_ylabel("Índice de popularidad promedio")
ax4.grid(True, linestyle="--", alpha=0.5)
st.pyplot(fig4)

#  Tabla: Top 10 
st.subheader("Top 10 por popularidad")
top10 = df_f.sort_values("popularity", ascending=False).head(10)[
    ["title", "release_year", "vote_average", "vote_count", "popularity", "original_language"]
].copy()
top10.columns = ["Título", "Año", "Calificación", "Votos", "Popularidad", "Idioma"]
st.dataframe(top10, use_container_width=True)

st.caption("Fuente: TMDb API, endpoint discover/movie, sort_by=popularity.desc, language=es-MX.")
