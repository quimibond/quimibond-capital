# Notas sobre la API DENUE de INEGI

Documentación oficial: https://www.inegi.org.mx/servicios/api_denue.html

**Base URL:** `https://www.inegi.org.mx/app/api/denue/v1/consulta/`

Todos los endpoints son `GET`, sin body, sin headers especiales. El token se pasa
como último segmento de la URL.

---

## Endpoints disponibles (firma vigente abril 2026)

### 1. Buscar — búsqueda geográfica por radio
```
/Buscar/{condicion}/{lat},{lng}/{radio_metros}/{token}
```
- `condicion`: keyword o lista coma-separada. Usar `todos` para sin filtro.
- `radio_metros`: máximo 5000.
- **Ojo:** ya **no** acepta `entidad` ni paginación numérica como en versiones viejas. Si te encuentras con `Buscar/textil/09/1/1/{token}` (firma antigua) el endpoint devolverá HTML 200 "página no encontrada" y el JSON parser fallará con `Expecting value`.

### 2. BuscarEntidad — búsqueda por keyword + estado
```
/BuscarEntidad/{condicion}/{entidad}/{inicio}/{fin}/{token}
```
- `entidad`: clave de 2 dígitos (`01`–`32`) o `00` para nacional.
- Devuelve 19 campos por establecimiento.
- Útil como **ping** del token.

### 3. Nombre — búsqueda por nombre/razón social
```
/Nombre/{texto}/{entidad}/{inicio}/{fin}/{token}
```

### 4. Ficha — detalle por CLEE
```
/Ficha/{id}/{token}
```

### 5. BuscarAreaAct — geo + actividad económica (sin estrato)
```
/BuscarAreaAct/{entidad}/{municipio}/{localidad}/{ageb}/{manzana}/
              {sector}/{subsector}/{rama}/{clase}/{nombre}/
              {inicio}/{fin}/{id}/{token}
```
14 segmentos. Devuelve 29 campos.

### 6. **BuscarAreaActEstr — el que usamos**
```
/BuscarAreaActEstr/{entidad}/{municipio}/{localidad}/{ageb}/{manzana}/
                  {sector}/{subsector}/{rama}/{clase}/{nombre}/
                  {inicio}/{fin}/{id}/{estrato}/{token}
```
**15 segmentos.** Pasar `0` en cualquier filtro = "todos".
Devuelve hasta 34 campos por establecimiento.

Para Quimibond:
- `entidad` = clave estado (`15` = EdoMex, etc.)
- `rama` = NAICS de 4 dígitos (`3149`, `3133`, `3169`, …)
- `estrato` = `5`, `6` o `7` (mediana / mediana-grande / grande)
- Resto de filtros = `0`
- `inicio/fin` = `1/1000` para una sola página

### 7. Cuantificar — solo conteos (NO devuelve data)
```
/Cuantificar/{actividad_economica}/{area_geografica}/{estrato}/{token}
```
- `actividad_economica`: código SCIAN de 2-6 dígitos (sector, subsector, rama, subrama, clase) o `0` para todos. Acepta lista coma-separada.
- `area_geografica`: 2/5/9 dígitos (estado/municipio/localidad) o `0` para nacional.
- Respuesta:
  ```json
  [{"AE": "3149", "AG": "15", "Total": "8"}]
  ```
- **Uso recomendado:** dimensionar el universo y/o pre-filtrar combinaciones antes de descargar data masiva.

---

## Campos del response de `BuscarAreaActEstr`

Capitalización exacta como devuelve el endpoint hoy:

| Campo | Tipo | Notas |
|-------|------|-------|
| `CLEE` | string | Identificador único nacional |
| `Id` | string | ID interno DENUE |
| `Nombre` | string | Nombre comercial / del establecimiento |
| `Razon_social` | string | Razón social legal (puede venir vacío) |
| `Clase_actividad` | string | Descripción texto de la clase SCIAN |
| `Estrato` | string | **Texto descriptivo** ej. "51 a 100 personas", no código |
| `Tipo_vialidad`, `Calle`, `Num_Exterior`, `Num_Interior` | string | Domicilio |
| `Colonia`, `CP` | string | Domicilio |
| `Ubicacion` | string | Concatenado: `"LOCALIDAD, Municipio, ESTADO"` (con espacios sobrantes) |
| `Telefono` | string | Puede venir vacío |
| `Correo_e` | string | Puede venir vacío |
| `Sitio_internet` | string | Puede venir vacío |
| `Tipo` | string | "Fijo" / otros |
| `Longitud`, `Latitud` | string | Coordenadas como string |
| `tipo_corredor_industrial`, `nom_corredor_industrial` | string | Si está en parque industrial |
| `numero_local` | string | Local dentro del parque/centro |
| `AGEB`, `Manzana` | string | Códigos censales |
| `CLASE_ACTIVIDAD_ID` | string | SCIAN 6 dígitos |
| `SECTOR_ACTIVIDAD_ID` | string | SCIAN 2 dígitos |
| `SUBSECTOR_ACTIVIDAD_ID` | string | SCIAN 3 dígitos |
| `RAMA_ACTIVIDAD_ID` | string | SCIAN 4 dígitos ← **lo que filtramos como NAICS** |
| `SUBRAMA_ACTIVIDAD_ID` | string | SCIAN 5 dígitos |
| `EDIFICIO`, `EDIFICIO_PISO` | string | Si aplica |
| `Tipo_Asentamiento` | string | "COLONIA", etc. |
| `Fecha_Alta` | string | Formato `"YYYY-MM"` |
| `AreaGeo` | string | Clave geográfica completa |

**No devuelve RFC.** Hay que cruzar con SAT u otro origen para obtenerlo.

---

## Comportamientos NO documentados (verificados empíricamente, abril 2026)

### `502 Bad Gateway` significa "sin resultados"

Cuando una combinación de filtros no tiene establecimientos, DENUE responde
**HTTP 502 de forma persistente y consistente**, NO un array vacío.

- Ejemplo verificado: `BuscarAreaActEstr/13/0/0/0/0/0/0/3149/0/0/1/1000/0/5/{token}`
  (Hidalgo + NAICS 3149 + estrato 51-100) → 502 en 3 intentos consecutivos.
- Misma combo con `estrato=1` (0-5 personas): HTTP 200 con datos.
- Con un token inválido: también 502.
- Con un sector inexistente (NAICS 9999): también 502.

**Implicación:** no reintentar al 502; tratarlo como `[]`. El cliente actual
hace exactamente eso.

### Sin rate limit observable

10 requests en serie sin sleep: todos 200 en ~0.4s c/u. Sleep entre requests
es opcional/cortesía (el pipeline usa 0.5s). En la práctica, ~3-5 req/s es
seguro.

### `Buscar` cambió firma sin aviso

Antes: `/Buscar/{condicion}/{entidad}/{inicio}/{fin}/{token}`
Ahora: `/Buscar/{condicion}/{lat},{lng}/{radio}/{token}`

Si el código falla con `Expecting value: line 1 column 1 (char 0)`, casi seguro
estás llamando un endpoint con firma vieja: el server responde HTML 200
"página no encontrada" en vez de 404, y el parser de JSON revienta.

### No hay diferenciación 502/401

Token inválido devuelve 502 también. El check `if status == 401` en
`denue_client.py` nunca dispara en la práctica.

---

## Limitaciones de paginación

- Cada query devuelve hasta los registros pedidos en `inicio/fin`.
- Para combos que estimas <1000, pedir `1/1000` te trae todo en una llamada.
- Si en algún momento una combinación supera 1000 (improbable con estrato 5+
  y NAICS específico), pagina con varias llamadas: `1/1000`, `1001/2000`, etc.

---

## Dimensionamiento del universo Quimibond (verificado abril 2026)

Con los filtros configurados (`config.py`):
- 6 NAICS objetivo × 10 estados × 3 estratos = **180 combinaciones**
- 103 combinaciones tienen data (57%)
- 77 combinaciones devuelven 502 (sin resultados)
- **366 establecimientos brutos** en total
- Tras dedup esperamos ~150-250 empresas únicas → cae en el rango 100-800
  que define la validación.

Para verlo rápido sin descargar:
```bash
for naics in 3131 3132 3133 3141 3149 3169; do
  for ent in 09 13 15 21 29 05 11 14 19 22; do
    for est in 5 6 7; do
      curl -sS "https://www.inegi.org.mx/app/api/denue/v1/consulta/Cuantificar/$naics/$ent/$est/$TOKEN"
    done
  done
done
```

---

## Si la API cambia otra vez

Los endpoints gubernamentales mexicanos mutan sin aviso. Diagnóstico rápido:

1. **`Expecting value` parseando JSON** → la URL devuelve HTML. Probablemente
   firma del endpoint cambió. Compara contra
   https://www.inegi.org.mx/servicios/api_denue.html
2. **502 en combos que sabes que tienen data** → puede ser caída temporal del
   servicio. Reintenta en 5-10 min. Si persiste, revisa el status del INEGI.
3. **Campos faltantes en el response** → el endpoint puede haber cambiado
   capitalización (ej. `nombre` vs `Nombre`). Ajusta `cleaning.py` con
   fallbacks.
4. **Token rechazado** → genera uno nuevo en
   https://www.inegi.org.mx/app/api/denue/v1/tokenVerify.aspx
