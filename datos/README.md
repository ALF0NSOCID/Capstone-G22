# Catálogo de datos

Las carpetas físicas se conservan en sus rutas originales para que los comandos,
el código Fortran y los scripts del caso Chile sigan funcionando. Este catálogo
las reúne sin duplicar instancias ni depender de enlaces simbólicos de otro sistema.

| Familia | Ruta física | Documentación / uso |
| --- | --- | --- |
| Mulgen/Canad | `../Canad/` | Parámetros `.par` en `Data/`, fuentes Fortran en `Mulgen/` |
| SNDlib | `../sndlib/` | XML estáticos; el lector los adapta al modelo de congestión |
| Chile | `../red_chile/` | [Fuentes, supuestos y regeneración](../red_chile/README.md) |
| Waxman | Generación al ejecutar | Parámetros e instancia exacta dentro de la carpeta de cada corrida |

- Mulgen solicita productos; el lector registra los efectivos después de filtrar
  los que no tienen camino. Reportar ambos números.
- Los XML SNDlib se convierten con convenciones de capacidad y direccionalidad;
  no se resuelve el problema original de diseño SNDlib completo.
- Chile es una red inspirada en infraestructura pública, con demandas estimadas
  y capacidades supuestas; no una reconstrucción operacional de todo el país.
- Las instancias Waxman del nuevo protocolo tienen backbone 60 % / 15 %. La
  exploración anterior de 80 % / 25 % conserva sus resultados por separado.
