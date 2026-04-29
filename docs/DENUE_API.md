# Notas sobre la API DENUE de INEGI

## Endpoints clave

Documentación oficial: https://www.inegi.org.mx/servicios/api_denue.html

### 1. Buscar (búsqueda libre)
```
GET /Buscar/{condicion}/{ae}/{registro_inicial}/{registro_final}/{token}
```
- `condicion`: keyword libre (ej. "textil")
- `ae`: clave de área (ej. "09" para CDMX, "0" para nacional)

### 2. BuscarEntidad
```
GET /BuscarEntidad/{condicion}/{ae}/{entidad}/{registro_inicial}/{registro_final}/{token}
```

### 3. BuscarAreaActEstr (el que usamos)
```
GET /BuscarAreaActEstr/{entidad}/{municipio}/{localidad}/{ageb}/{manzana}/
    {sector_scian}/{registro_inicial}/{registro_final}/{estrato}/{token}
```
Pasa 0 en municipio/localidad/ageb/manzana para "todos".

### 4. Ficha (detalle de un establecimiento)
```
GET /Ficha/{clee}/{token}
```

## Campos típicos del response

DENUE no tiene un schema 100% consistente entre endpoints. Los más comunes:

| Campo | Descripción |
|-------|-------------|
| `CLEE` o `id` | Identificador único del establecimiento |
| `nombre` o `Nombre` | Nombre comercial |
| `razon_social` o `Razon_social` | Razón social legal |
| `nombre_act` o `Clase_actividad` | Descripción de la actividad económica |
| `per_ocu` o `Estrato` | Rango de personal ocupado |
| `tipo_vialidad`, `nom_vial`, `numero_ext`, `colonia` | Domicilio fragmentado |
| `municipio` o `Municipio` | Municipio |
| `entidad` o `Entidad` | Entidad federativa |
| `telefono` | Teléfono |
| `correo_e` o `correo_electronico` | Email |
| `sitio_internet` o `www` | Web |
| `latitud`, `longitud` | Coordenadas |
| `fecha_alta` o `Fecha_alta` | Fecha de alta en DENUE |

## Limitaciones conocidas

- **Paginación:** máximo ~5000 registros por query. Si una combinación NAICS×estado×estrato supera ese tope, hay que paginar.
- **Rate limiting:** no documentado oficialmente, pero ~2 requests/segundo es seguro.
- **Datos faltantes:** muchos establecimientos tienen email/web vacíos. Es normal.
- **Estrato:** es un rango, no el número exacto de empleados. Los puntos medios que usamos son estimaciones para priorización.
- **Campo "razón social":** muchos establecimientos solo tienen nombre comercial.

## Si la API cambia

El gobierno mexicano actualiza estos endpoints sin notificar. Si el script empieza a fallar:

1. Visita https://www.inegi.org.mx/servicios/api_denue.html
2. Compara endpoints actuales vs. los que usa `denue_client.py`
3. Ajusta URLs y/o nombres de campos en `cleaning.py` (transformar)
4. Si el formato del response cambió, actualiza la lógica de `_get` en el cliente
