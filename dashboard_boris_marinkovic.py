import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
import re

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Radar de Marca | Boris Marinkovic",
    page_icon="🎭",
    layout="wide"
)

# ==========================================
# DICCIONARIO DE SENTIMIENTO PERSONALIZADO (Enriquecido OSINT)
# ==========================================
DICCIONARIO_SENTIMIENTO = {
    # --- BASE POSITIVO ---
    "excelente": 5, "brillante": 5, "destaca": 4, "logro": 4, "triunfo": 4,
    "apoyo": 3, "acuerdo": 3, "solución": 3, "verdad": 3, "justicia": 3,
    "bueno": 2, "favor": 2, "avanza": 2, "defensa": 2,

    # --- BASE NEGATIVO ---
    "corrupto": -5, "delito": -5, "escándalo": -5, "fraude": -5,
    "crisis": -4, "fracaso": -4, "acusación": -4, "polémica": -4,
    "malo": -2, "contra": -2, "crítica": -3, "rechazo": -3, "error": -3,
    "investigación": -2, "duda": -2,

    # --- DIMENSIÓN 1: MÉDICO / CIRUJANO E INSTITUCIONAL ---
    "medicina": 4, "médico": 4, "cirujano": 4, "cirugía": 3,
    "salud": 3, "paciente": 2, "clínica": 2, "tratamiento": 2,
    "hospital del salvador": 3, "universidad de chile": 2, 
    "hepatobiliar": 3, "imperial college": 4, "director": 3,
    "mala praxis": -5, "demanda": -4,

    # --- DIMENSIÓN 2: ARTE CUIR / ECOSISTEMA ---
    "arte": 4, "artist": 4, "cuir": 3, "queer": 3,
    "exposición": 3, "galería": 3, "creación": 3, "obra": 3,
    "performance": 3, "diversidad": 3, "inclusión": 3, "cultura": 2,
    "lgbtq": 3, "lgbtiqanb": 3, "disidencia": 3, "identidad": 2,
    "transfeminista": 3, "transmasculino": 2, "memoria disidente": 3,
    "reconocimiento": 4, "premio": 4, "talento": 4,
    "innovador": 4, "vanguardia": 3, "referente": 3,
    "coleccionista": 3, "ch.aco": 4, "fundación antenna": 4, 
    "premio adquisición": 4, "antenna": 2,
    "discriminación": -4, "odio": -5, "censura": -3,

    # --- DIMENSIÓN 3: FUNDACIÓN MECENAS ---
    "fundación mecenas": 5, "mecenas": 4, "fundación": 3,
    "presidente": 3, "fundador": 4,
    "sin fines de lucro": 3, "comunidad": 3, "bienestar": 3,
    "voluntariado": 2, "donación": 2, "convocatoria": 2,
    "transformación social": 3, "sociocultural": 2,
    "artistas": 3, "red de artes": 3, "artes y oficios": 3,
    "controversia": -3, "denuncia": -4,
}

def analizar_sentimiento_avanzado(texto):
    """
    Analiza el sentimiento de un texto usando el diccionario personalizado.
    Retorna (categoría: str, puntaje_promedio: float).
    """
    texto = texto.lower()
    puntaje_total = 0
    palabras_encontradas = 0

    for palabra, peso in DICCIONARIO_SENTIMIENTO.items():
        if palabra in texto:
            puntaje_total += peso
            palabras_encontradas += 1

    promedio = puntaje_total / palabras_encontradas if palabras_encontradas > 0 else 0

    if promedio > 0.5:   return "Positivo", promedio
    elif promedio < -0.5: return "Negativo", promedio
    else:                 return "Neutral",  promedio

# ==========================================
# HANDLES Y QUERIES MULTIPLES (ESTRATEGIA EXHAUSTIVA)
# Para evitar que Google News ignore cadenas muy largas, dividimos las búsquedas.
# ==========================================
REGEX_CUENTAS = "borismarinkovic|boris_marinkovic|fundacionmecenas|fundacion_mecenas|mecenas"

QUERIES_PRENSA = [
    '"Boris Marinkovic"',
    '"Boris Marinković"',
    '"Fundación Mecenas"',
    '"Boris Marinkovic" (arte OR artista OR cuir OR exposición)',
    '"Boris Marinkovic" (médico OR cirujano OR hospital)'
]

QUERY_REDES_SOCIALES = '"Boris Marinkovic" OR "Fundación Mecenas" OR "borismarinkovic" OR "fundacionmecenas"'

@st.cache_data(ttl=3600)
def buscar_menciones(query_avanzada, filtro_red_social=None):
    """
    Consulta Google News RSS. Filtra falsos positivos, clasifica fuente y sentimiento.
    """
    query = query_avanzada
    if filtro_red_social:
        query += f" site:{filtro_red_social}"

    url = (
        f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}"
        f"&hl=es-419&gl=CL&ceid=CL:es-419"
    )

    try:
        respuesta = requests.get(url, timeout=10)
        sopa = BeautifulSoup(respuesta.content, "xml")
        datos = []

        for noticia in sopa.find_all("item"):
            titulo = noticia.title.text if noticia.title else ""
            link   = noticia.link.text  if noticia.link  else ""
            
            texto_completo = (titulo + " " + link).lower()

            # 🛑 FILTRO ANTI-CLONES 2.0 (Incluye al tirador deportivo de Bolivia)
            clones = [
                "gutierrez", "gutiérrez", "san bernardo", # Médico homónimo
                "bolivia", "santa cruz", "diez.bo", "cochabamba", # Lugares de Bolivia
                "tiro deportivo", "récord", "deportista", "campeonato" # El atleta homónimo
            ]
            if any(omit in texto_completo for omit in clones):
                continue

            try:
                fecha_dt = datetime.strptime(
                    noticia.pubDate.text, "%a, %d %b %Y %H:%M:%S %Z"
                )
            except Exception:
                continue

            # 🕰️ AMPLIACIÓN HISTÓRICA: Buscamos desde 2018 para tener trayectoria completa
            if fecha_dt.year < 2018:
                continue

            categoria, puntaje = analizar_sentimiento_avanzado(titulo)
            fuente = "Prensa"
            cuenta = "Medio de Prensa"

            # Etiquetado de fuente por contexto del link/título
            if "fundacionmecenas" in texto_completo or "fundación mecenas" in titulo.lower():
                fuente = "Fundación Mecenas"
                cuenta = "@fundacionmecenas"
            elif "twitter.com" in texto_completo or "x.com" in texto_completo or " en x:" in titulo.lower():
                fuente = "X (Twitter)"
                cuenta = titulo.split(" en X:")[0].strip() if " en X:" in titulo else "Usuario X"
            elif "linkedin.com" in texto_completo or " | linkedin" in titulo.lower():
                fuente = "LinkedIn"
                cuenta = (
                    titulo.split(" | LinkedIn")[0].split("-")[-1].strip()
                    if " | LinkedIn" in titulo else "Usuario LinkedIn"
                )
            elif "facebook.com" in texto_completo or " - facebook" in titulo.lower():
                fuente = "Facebook"
                cuenta = (
                    "borismarinkovic"
                    if any(c in texto_completo for c in REGEX_CUENTAS.split("|"))
                    else "Usuario Facebook"
                )
            elif "instagram.com" in texto_completo or " - instagram" in titulo.lower():
                fuente = "Instagram"
                cuenta = (
                    "fundacionmecenas"
                    if "fundacionmecenas" in texto_completo
                    else (
                        "borismarinkovic"
                        if "borismarinkovic" in texto_completo
                        else "Usuario Instagram"
                    )
                )

            datos.append({
                "Fecha":            fecha_dt.date(),
                "Fuente":           fuente,
                "Cuenta / Autor":   cuenta,
                "Título / Mención": titulo,
                "Sentimiento":      categoria,
                "Puntaje":          puntaje,
                "Link":             link,
            })

        return pd.DataFrame(datos)

    except Exception as e:
        # En vez de mostrar error en pantalla y asustar al cliente, devolvemos un df vacío
        return pd.DataFrame()

# ==========================================
# INTERFAZ GRÁFICA DEL DASHBOARD
# ==========================================
def main():
    st.title("🎭 Radar de Marca Personal: Boris Marinkovic")
    st.markdown(
        "Monitoreo avanzado · Médico Cirujano U. de Chile · Artista · "
        "Presidente [Fundación Mecenas](https://www.fundacionmecenas.cl/) · "
        "Arte cuir y comunidad LGBTIQANB+ en Chile"
    )
    st.divider()

    if st.button("🔄 Actualizar Datos Ahora"):
        st.cache_data.clear()

    # --- Carga de datos desde múltiples fuentes (Estrategia Exhaustiva) ---
    with st.spinner("Rastreando huella digital y ejecutando búsqueda histórica exhaustiva..."):
        
        # 1. Ejecutar múltiples búsquedas de prensa para sortear límites de Google
        dfs_prensa = []
        for query in QUERIES_PRENSA:
            df_temp = buscar_menciones(query)
            if not df_temp.empty:
                dfs_prensa.append(df_temp)
                
        df_prensa = pd.concat(dfs_prensa).drop_duplicates(subset=["Link"]) if dfs_prensa else pd.DataFrame()

        # 2. Búsquedas específicas en Redes Sociales
        df_x        = buscar_menciones(QUERY_REDES_SOCIALES, "twitter.com")
        df_linkedin = buscar_menciones(QUERY_REDES_SOCIALES, "linkedin.com")
        df_ig       = buscar_menciones(QUERY_REDES_SOCIALES, "instagram.com")
        df_fb       = buscar_menciones(QUERY_REDES_SOCIALES, "facebook.com") # Añadido Facebook

        # 3. Unificar todo
        tablas_a_unir = [df_prensa, df_x, df_linkedin, df_ig, df_fb]
        tablas_a_unir = [df for df in tablas_a_unir if not df.empty]
        
        if tablas_a_unir:
            df_total = (
                pd.concat(tablas_a_unir)
                .drop_duplicates(subset=["Link"])
                .reset_index(drop=True)
                .sort_values(by="Fecha", ascending=False)
                .reset_index(drop=True)
            )
        else:
            df_total = pd.DataFrame()

    if df_total.empty:
        st.warning("No se encontraron menciones. Verifica tu conexión o intenta con otros términos de búsqueda.")
        return

    # ==========================================
    # KPIs Y VELOCÍMETRO DE REPUTACIÓN
    # ==========================================
    st.subheader("📊 Salud de Marca Digital")
    puntaje_general = df_total["Puntaje"].mean() * 20  # Escala -100 / +100
    
    # Manejo seguro de NaN si todas las noticias son Neutrales (Puntaje 0)
    if pd.isna(puntaje_general): puntaje_general = 0 

    col_gauge, col_kpis = st.columns([1, 2])

    with col_gauge:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(puntaje_general, 1),
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Índice de Reputación"},
            gauge={
                "axis": {"range": [-100, 100]},
                "bar": {"color": "#1a1a2e"},
                "steps": [
                    {"range": [-100, -20], "color": "#ff4b4b"},
                    {"range": [-20,   20], "color": "#ffa600"},
                    {"range": [  20, 100], "color": "#00cc96"},
                ],
                "threshold": {
                    "line": {"color": "black", "width": 3},
                    "thickness": 0.75,
                    "value": puntaje_general,
                },
            },
        ))
        fig_gauge.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_kpis:
        k1, k2, k3, k4 = st.columns(4)
        positivos = len(df_total[df_total["Sentimiento"] == "Positivo"])
        negativos = len(df_total[df_total["Sentimiento"] == "Negativo"])
        menciones_mecenas = len(df_total[
            df_total["Título / Mención"].str.contains("mecenas", case=False, na=False) |
            df_total["Fuente"].str.contains("Mecenas", na=False)
        ])

        k1.metric("Total Menciones",          len(df_total))
        k2.metric("Menciones en Redes",        len(df_total[df_total["Fuente"] != "Prensa"]))
        k3.metric("Positivas / Negativas",     f"{positivos} / {negativos}")
        k4.metric("Menciones Fdción. Mecenas", menciones_mecenas)

    st.divider()

    # ==========================================
    # PESTAÑAS DINÁMICAS
    # ==========================================
    df_social  = df_total[df_total["Fuente"].isin(["X (Twitter)", "LinkedIn", "Facebook", "Instagram"])]
    df_medios  = df_total[df_total["Fuente"] == "Prensa"]
    df_mecenas = df_total[
        df_total["Título / Mención"].str.contains("mecenas|Mecenas", na=False) |
        df_total["Fuente"].str.contains("Mecenas", na=False)
    ]

    nombres_pestanas = []
    if not df_social.empty:   nombres_pestanas.append("📱 Ecosistema Redes")
    if not df_mecenas.empty:  nombres_pestanas.append("🏛️ Fundación Mecenas")
    nombres_pestanas.extend([
        "📰 Medios y Prensa",
        "🗄️ Base de Datos Completa",
        "👣 Rastro Cuentas Oficiales",
    ])

    pestanas = st.tabs(nombres_pestanas)
    indice = 0

    # ------------------------------------------
    # PESTAÑA: ECOSISTEMA REDES SOCIALES
    # ------------------------------------------
    if not df_social.empty:
        with pestanas[indice]:
            st.markdown("#### Distribución por Red y Sentimiento")
            col1, col2 = st.columns(2)
            with col1:
                fig_social = px.histogram(
                    df_social, x="Fuente", color="Sentimiento",
                    color_discrete_map={"Positivo":"#00cc96","Neutral":"#7f7f7f","Negativo":"#ff4b4b"},
                    title="Sentimiento por Red Social", barmode="group",
                )
                st.plotly_chart(fig_social, use_container_width=True)
            with col2:
                # Filtro Anti-Ego: excluir cuentas propias del cliente
                df_otros = df_social[
                    ~df_social["Cuenta / Autor"].str.contains(REGEX_CUENTAS, case=False, na=False)
                ]
                top = df_otros["Cuenta / Autor"].value_counts().reset_index().head(5)
                top.columns = ["Cuenta", "Menciones"]
                fig_top = px.bar(
                    top, x="Menciones", y="Cuenta", orientation="h",
                    title="Top 5: Cuentas de Terceros",
                    color="Menciones", color_continuous_scale="Blues",
                )
                fig_top.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_top, use_container_width=True)

            st.markdown("#### Últimas menciones en redes")
            for _, row in df_social.head(5).iterrows():
                icono = "🟢" if row["Sentimiento"]=="Positivo" else ("🔴" if row["Sentimiento"]=="Negativo" else "⚪")
                st.info(f"{icono} **{row['Cuenta / Autor']}** en {row['Fuente']}: [{row['Título / Mención']}]({row['Link']})")
        indice += 1

    # ------------------------------------------
    # PESTAÑA: FUNDACIÓN MECENAS
    # ------------------------------------------
    if not df_mecenas.empty:
        with pestanas[indice]:
            st.markdown(
                "#### Cobertura de Boris Marinkovic en su rol de Presidente de Fundación Mecenas\n"
                "> Fundación sin fines de lucro fundada en agosto de 2024 · Arte cuir · LGBTIQANB+ · Chile"
            )
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                fig_m_sent = px.pie(
                    df_mecenas, names="Sentimiento", color="Sentimiento",
                    color_discrete_map={"Positivo":"#00cc96","Neutral":"#7f7f7f","Negativo":"#ff4b4b"},
                    title="Tono de las menciones de Fundación Mecenas",
                    hole=0.4,
                )
                st.plotly_chart(fig_m_sent, use_container_width=True)
            with col_m2:
                fig_m_fuente = px.histogram(
                    df_mecenas, x="Fuente", color="Sentimiento",
                    color_discrete_map={"Positivo":"#00cc96","Neutral":"#7f7f7f","Negativo":"#ff4b4b"},
                    title="Fuente de las menciones de Fundación Mecenas",
                )
                st.plotly_chart(fig_m_fuente, use_container_width=True)

            st.markdown("#### Publicaciones recientes vinculadas a Fundación Mecenas")
            for _, row in df_mecenas.head(10).iterrows():
                color = "#00cc96" if row["Sentimiento"]=="Positivo" else ("#ff4b4b" if row["Sentimiento"]=="Negativo" else "#7f7f7f")
                st.markdown(
                    f"<div style='padding:14px;border-left:6px solid {color};"
                    f"background:#f8f9fa;margin-bottom:12px;border-radius:0 6px 6px 0;'>"
                    f"<strong>{row['Fuente']}</strong> · "
                    f"<span style='color:{color};font-weight:bold'>{row['Sentimiento']}</span><br>"
                    f"<i>{row['Título / Mención']}</i><br>"
                    f"<small>📅 {row['Fecha']} · <a href='{row['Link']}' target='_blank'>🔗 Ver publicación</a></small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        indice += 1

    # ------------------------------------------
    # PESTAÑA: MEDIOS Y PRENSA
    # ------------------------------------------
    with pestanas[indice]:
        if not df_medios.empty:
            st.markdown("#### Línea de Tiempo · Cobertura en Prensa (Desde 2018)")
            fig_tl = px.scatter(
                df_medios, x="Fecha", y="Puntaje", color="Sentimiento",
                color_discrete_map={"Positivo":"#00cc96","Neutral":"#7f7f7f","Negativo":"#ff4b4b"},
                hover_data=["Título / Mención","Cuenta / Autor"],
                title="Evolución del tono mediático",
            )
            fig_tl.update_traces(marker=dict(size=10, opacity=0.8))
            fig_tl.add_hline(y=0, line_dash="dot", line_color="gray", annotation_text="Zona Neutral")
            st.plotly_chart(fig_tl, use_container_width=True)

            fig_pie = px.pie(
                df_medios, names="Sentimiento", color="Sentimiento",
                color_discrete_map={"Positivo":"#00cc96","Neutral":"#7f7f7f","Negativo":"#ff4b4b"},
                hole=0.4, title="Distribución de sentimiento en prensa",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

            st.markdown("#### Noticias recientes")
            for _, row in df_medios.head(8).iterrows():
                icono = "🟢" if row["Sentimiento"]=="Positivo" else ("🔴" if row["Sentimiento"]=="Negativo" else "⚪")
                st.markdown(f"{icono} [{row['Título / Mención']}]({row['Link']}) — *{row['Fecha']}*")
        else:
            st.info("No se encontraron menciones en prensa para el período analizado.")
    indice += 1

    # ------------------------------------------
    # PESTAÑA: BASE DE DATOS COMPLETA
    # ------------------------------------------
    with pestanas[indice]:
        st.markdown("#### Todas las menciones indexadas")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            fuentes_disp = ["Todas"] + sorted(df_total["Fuente"].unique().tolist())
            filtro_fuente = st.selectbox("Filtrar por Fuente", fuentes_disp)
        with col_f2:
            filtro_sent = st.selectbox("Filtrar por Sentimiento", ["Todos","Positivo","Neutral","Negativo"])
        with col_f3:
            busq_texto = st.text_input("Buscar en títulos", "")

        df_f = df_total.copy()
        if filtro_fuente != "Todas":  df_f = df_f[df_f["Fuente"] == filtro_fuente]
        if filtro_sent  != "Todos":   df_f = df_f[df_f["Sentimiento"] == filtro_sent]
        if busq_texto:                df_f = df_f[df_f["Título / Mención"].str.contains(busq_texto, case=False, na=False)]

        st.caption(f"Mostrando {len(df_f)} de {len(df_total)} registros")

        # Compatible con Pandas 2.x: df.style.map (NO applymap)
        st.dataframe(
            df_f.style.map(
                lambda x: (
                    "background-color: #ffcccc" if x == "Negativo"
                    else ("background-color: #ccffcc" if x == "Positivo" else "")
                ),
                subset=["Sentimiento"],
            ),
            use_container_width=True,
            height=420,
        )

        csv = df_f.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV filtrado", csv,
            "menciones_boris_marinkovic.csv", "text/csv",
        )
    indice += 1

    # ------------------------------------------
    # PESTAÑA: RASTRO CUENTAS OFICIALES (Anti-Ego)
    # Monitora: @borismarinkovic + @fundacionmecenas
    # ------------------------------------------
    with pestanas[indice]:
        st.markdown("#### Interacciones de terceros hacia las cuentas oficiales")
        st.caption(
            "Filtro Anti-Ego activo · Cuentas monitoreadas: "
            "@borismarinkovic (Instagram personal) · @fundacionmecenas (Instagram fundación)"
        )

        filtro_cuentas = (
            df_total["Título / Mención"].str.contains(REGEX_CUENTAS, case=False, na=False) |
            df_total["Link"].str.contains(REGEX_CUENTAS, case=False, na=False)
        )
        # Anti-Ego: excluir publicaciones donde el autor ES el propio cliente
        filtro_no_cliente = ~df_total["Cuenta / Autor"].str.contains(REGEX_CUENTAS, case=False, na=False)
        df_oficial = df_total[filtro_cuentas & filtro_no_cliente]

        if not df_oficial.empty:
            st.metric("Interacciones de terceros detectadas", len(df_oficial))
            for _, row in df_oficial.head(10).iterrows():
                color = "#00cc96" if row["Sentimiento"]=="Positivo" else ("#ff4b4b" if row["Sentimiento"]=="Negativo" else "#7f7f7f")
                st.markdown(
                    f"<div style='padding:15px;border-left:6px solid {color};"
                    f"background:#f8f9fa;margin-bottom:15px;border-radius:0 6px 6px 0;'>"
                    f"<strong>{row['Fuente']}</strong> · "
                    f"<span style='color:{color};font-weight:bold'>{row['Sentimiento']}</span><br>"
                    f"<i>{row['Título / Mención']}</i><br>"
                    f"<small>📅 {row['Fecha']} · <a href='{row['Link']}' target='_blank'>🔗 Ver publicación</a></small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No se detectaron interacciones recientes de terceros hacia las cuentas oficiales.")

    # Pie de página
    st.divider()
    st.caption(
        f"🕐 Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
        "Fuente: Google News RSS · "
        "Cuentas monitoreadas: @borismarinkovic · @fundacionmecenas · "
        "Variantes y contexto: Boris Marinkovic (Desde 2018) / Arte Cuir / Fundación Mecenas / U. de Chile"
    )

if __name__ == "__main__":
    main()
