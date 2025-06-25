'''
Índice de Vulnerabilidad Asociado al Contexto Urbano de Málaga
--------------------------------------------------------------
Descripción: Este script calcula un índice compuesto por variables: zonas verdes, transporte público,
servicios y equipamientos básicos, y confort acústico, para cada parcela del municipio de Málaga.

Autor: Lorenzo Romero Luque
Fecha: 10/06/2025
'''

import geopandas as gpd
import pandas as pd

#-----------------------
# CARGA DE DATOS
#-----------------------

# Cargar el shapefile de parcelas recortadas (unicamente parcelas residenciales)
parcelas = gpd.read_file("parcela_recortada/parcelas_recortadas.shp")

# Cargar capas con las siguientes variables a considerar en el índice:
# Zonas Verdes
zonas_verde = gpd.read_file("zonas_verdes/zonas_verdes.shp")
# Transporte Público
metro = gpd.read_file("transporte_publico/parada_metro.shp")
bus = gpd.read_file("transporte_publico/parada_bus.shp")
# Servicios y Equipamientos Básicos
c_salud = gpd.read_file("servicios_equipamientos/centro_salud.shp")
c_educacion = gpd.read_file("servicios_equipamientos/centros_educativos.shp")
int_deportivas = gpd.read_file("servicios_equipamientos/instalaciones_deportivas.shp")
# Confort Acústico
ruido_trafico = gpd.read_file("confort_acustico/trafico_vehiculos.shp")

#-----------------------
# HOMOGENEIZAR PROYECCIONES
#-----------------------

layers = [zonas_verde, metro, bus, c_salud, c_educacion, int_deportivas, ruido_trafico]
for capa in layers:
    capa.to_crs(parcelas.crs, inplace=True)

#-----------------------
# FUNCIONES DE DISTANCIA Y CUARTILES
#-----------------------

# Función para calcular la distancia mínima desde cada parcela a la capa dada
# y clasificarla en cuartiles (1=cercanía, 4=lejanía)
def calcular_cuartil(parcelas, capa, nombre, dist_col=None, cuart_col=None):
    dist = parcelas.geometry.apply(lambda geom: capa.distance(geom).min())
    dist_col = dist_col or f"dist_{nombre}"   # Normbre de la columna de distancia
    cuart_col = cuart_col or f"cuart_{nombre}"   # Normbre de la columna de cuartil
    parcelas[dist_col] = dist
    parcelas[cuart_col] = pd.qcut(dist, q=4, labels=[1, 2, 3, 4])
    return parcelas

# ---------------------
# CALCULAR CUARTILES PARA VARIABLES
# ---------------------

# Calcular cuartiles para cada variable, excepto ruido_trafico
parcelas = calcular_cuartil(parcelas, zonas_verde, "zver")
parcelas = calcular_cuartil(parcelas, metro, "metro", cuart_col="cuart_metr")
parcelas = calcular_cuartil(parcelas, bus, "bus")
parcelas = calcular_cuartil(parcelas, c_salud, "salud", cuart_col="cuart_salu")
parcelas = calcular_cuartil(parcelas, c_educacion, "edu")
parcelas = calcular_cuartil(parcelas, int_deportivas, "deport", dist_col="dist_depor", cuart_col="cuart_depo")

# ---------------------
# SUMA DE ÍNDICES POR GRUPO
# ---------------------
parcelas["sum_zver"] = parcelas["cuart_zver"].astype(int)
parcelas["sum_trans"] = parcelas["cuart_metr"].astype(int) + parcelas["cuart_bus"].astype(int)
parcelas["sum_serv"] = parcelas["cuart_salu"].astype(int) + parcelas["cuart_edu"].astype(int) + parcelas["cuart_depo"].astype(int)

# ---------------------
# NORMALIZACIÓN A RANGO FIJO (1–4)
# ---------------------

def normalizar_rango_fijo(df, columna, salida, min_ref, max_ref):
    df[salida] = 1 + 3 * (df[columna] - min_ref) / (max_ref - min_ref)
    df[salida] = df[salida].clip(1, 4).round(0).astype(int)
    return df

# Rango esperado para transporte: 2–8 (2 cuartiles, bus + metro)
# Rango esperado para servicios: 3–12 (3 cuartiles, centro educativo + centro de salud + intalaciones deportivas)
parcelas = normalizar_rango_fijo(parcelas, "sum_trans", "sum_tran_n", min_ref=2, max_ref=8)
parcelas = normalizar_rango_fijo(parcelas, "sum_serv", "sum_serv_n", min_ref=3, max_ref=12)

# ---------------------
# VARIABLE DE CONFORT ACÚSTICO (RUIDO)
# ---------------------

# Calcular el punto representativo de cada parcela
parcelas['centroid'] = parcelas.geometry.representative_point()
centroides = gpd.GeoDataFrame(parcelas[['centroid']], geometry='centroid', crs=parcelas.crs)

# Hacer unión espacial para obtener nivel de decibelios en cada parcela
joined_veh = gpd.sjoin(centroides, ruido_trafico[['geometry', 'DB_HI']], how='left', predicate='within')
parcelas['DB_VEH'] = joined_veh['DB_HI'].values

# Clasificar por intervalos de decibelios (manual, basado en bibliografía)
parcelas['ru_veh'] = pd.cut(
    parcelas['DB_VEH'],
    bins=[0, 45, 55, 65, 100],
    labels=[1, 2, 3, 4],
    include_lowest=True
).astype('float')

# ---------------------
# CÁLCULO DEL ÍNDICE FINAL
# ---------------------

# Calcular índice final (sumando todas las variables)
parcelas['indice_contexto_total'] = (
    parcelas['sum_zver'].astype(int) +
    parcelas['sum_tran_n'].astype(int) +
    parcelas['sum_serv_n'].astype(int) +
    parcelas['ru_veh'].fillna(0).astype(int) # Si hay parcelas sin datos de ruido, se considera 0
)

# ---------------------
# EXPORTACIÓN DEL RESULTADO
# ---------------------

# Eliminar columna temporal de centroides y guardar shapefile final
parcelas.drop(columns=['centroid']).to_file("resultado/indice_contexto_final.shp")

print("Índice de Vulnerabilidad Asociada al Contexto Urbano generado con éxito.")