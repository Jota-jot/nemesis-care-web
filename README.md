# Némesis — núcleo auditable y RADAR inicial

Estado: el núcleo local registra tareas, evidencias, pronósticos y movimientos económicos. Se ha añadido un primer adaptador RADAR que consulta resultados web y guarda las pistas en SQLite. **Todavía no es un agente autónomo completo**: no lee las páginas enlazadas, no contrasta afirmaciones entre fuentes y no coordina subagentes.

## Alcance implementado
- Persistencia SQLite para tareas, evidencias, pronósticos y libro económico.
- Evidencias tipadas como hecho, inferencia, hipótesis o contradicción.
- Matriz binaria de pronósticos: probabilidad previa, horizonte, justificación y regla de resolución; núcleo inmutable y resolución única con Brier y Log Loss.
- Separación de ingresos cobrados, ingresos contratados pendientes y proyecciones.
- Separación de gastos pagados, comprometidos y proyectados.
- Reserva y presupuesto configurables; no autoriza compras ni contratos.
- Informe JSON con estado, métricas y caja disponible.
- RADAR inicial: búsqueda web sin API key, persistencia de títulos/enlaces/resúmenes como **hipótesis de baja confianza**, asociadas a una tarea y con advertencia de verificación.

## Requisitos
Python 3.11 o posterior. Solo biblioteca estándar; no requiere API key ni suscripción. El adaptador usa la página HTML pública de DuckDuckGo y puede fallar si el proveedor cambia su estructura o limita el acceso.

## Inicio rápido
Desde la raíz del repositorio:

```bash
python engine/nemesis_mvp.py init
python engine/radar.py "ayudas y subvenciones para servicios de cuidados a domicilio en España" --limit 8
python engine/nemesis_mvp.py report
```

RADAR devuelve JSON con cada resultado y su estado `lead_not_verified`. Guarda cada pista en la tabla `evidence`, con enlace, título, fecha de registro, confianza inicial 0.25 y una advertencia explícita. No debe citarse una pista como hecho hasta abrir la fuente y comprobar autoría, fecha, contenido y, cuando sea posible, evidencia primaria.

Para el resto del núcleo:
```bash
python engine/nemesis_mvp.py task-add "Investigar oportunidad comercial" --objective "Encontrar una oportunidad verificable" --priority 5
python engine/nemesis_mvp.py evidence-add "La convocatoria está publicada" --type fact --confidence 0.95 --url "https://example.org/convocatoria" --source-title "Convocatoria oficial"
python engine/nemesis_mvp.py forecast-add "¿Se publicará la convocatoria antes de 2027-01-01?" --horizon 2027-01-01 --p-yes 0.65 --rationale "Evidencia y supuestos documentados" --resolution-rule "Publicación oficial fechada antes del horizonte"
python engine/nemesis_mvp.py setting reserve_eur 250
python engine/nemesis_mvp.py ledger-add income collected 120 --category "servicio" --description "Factura cobrada"
python engine/nemesis_mvp.py report
```

Los ejemplos contables son ilustrativos; no introduzcas datos ficticios como si fueran contabilidad real.

## Reglas económicas y de evidencia
- Caja cobrada no equivale a facturación pendiente ni a oportunidades.
- Los gastos comprometidos reducen la disponibilidad aunque todavía no se hayan pagado.
- La reserva se descuenta antes de considerar excedente reinvertible.
- Las proyecciones no se suman a la caja disponible.
- No hay compras, contratos, publicaciones ni envíos automáticos.
- Los resultados del buscador son pistas, no hechos verificados. La búsqueda inicial aún no demuestra independencia, actualidad ni veracidad de las fuentes.

## Predicción y evaluación
Brier binario = (p − y)². Log Loss = −[y ln(p) + (1−y) ln(1−p)], con recorte numérico de seguridad. Los pronósticos no se pueden reescribir una vez registrados. Antes de afirmar ventaja predictiva hay que comparar con una línea base y muestras suficientes.

## Siguiente frontera técnica
1. Recuperar contenido y metadatos de las páginas fuente, con límites de tamaño/tiempo y registro de fecha.
2. Detección de afirmaciones coincidentes y contradictorias entre fuentes independientes.
3. Informe de inteligencia que separe hallazgos, evidencia, incertidumbre, oportunidades y acciones recomendadas.
4. Orquestación y reanudación de tareas; solo después evaluar especialistas/subagentes.
5. Pruebas automatizadas/CI, seguridad, copias de respaldo y retención.
6. Compatibilidad con el artefacto histórico de la matriz V8.3 cuando se recupere el archivo fuente.

El motor vive bajo `engine/`; no reemplaza la web estática principal del repositorio.
