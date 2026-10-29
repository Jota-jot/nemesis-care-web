# Némesis — MVP de núcleo auditable

Estado: primera implementación local del núcleo. No es todavía un agente autónomo desplegado ni un radar web en ejecución.

## Alcance implementado
- Persistencia SQLite para tareas, evidencias, pronósticos y libro económico.
- Registro de evidencias tipadas como hecho, inferencia, hipótesis o contradicción.
- Matriz binaria de pronósticos: probabilidad previa, horizonte, justificación y regla de resolución; núcleo del pronóstico inmutable; resolución única con Brier y Log Loss.
- Separación estricta de ingresos cobrados, ingresos contratados pendientes y proyecciones.
- Separación de gastos pagados, comprometidos y proyectados.
- Reserva y presupuesto configurables. El sistema no autoriza compras ni contratos por sí mismo.
- Informe JSON con estado, métricas y caja disponible tras gastos pagados, compromisos y reserva.

## Requisitos
Python 3.11 o posterior. Solo biblioteca estándar; no requiere API key ni suscripción.

## Inicio rápido
```bash
python engine/nemesis_mvp.py init
python engine/nemesis_mvp.py task-add "Investigar oportunidad comercial" --objective "Encontrar una oportunidad verificable" --priority 5
python engine/nemesis_mvp.py evidence-add "La convocatoria está publicada" --type fact --confidence 0.95 --url "https://example.org/convocatoria" --source-title "Convocatoria oficial"
python engine/nemesis_mvp.py forecast-add "¿Se publicará la convocatoria antes de 2027-01-01?" --horizon 2027-01-01 --p-yes 0.65 --rationale "Evidencia y supuestos documentados" --resolution-rule "Publicación oficial fechada antes del horizonte"
python engine/nemesis_mvp.py forecast-resolve 1 --outcome yes --source "URL oficial que acredita el resultado"
python engine/nemesis_mvp.py setting reserve_eur 250
python engine/nemesis_mvp.py setting monthly_budget_eur 50
python engine/nemesis_mvp.py ledger-add income collected 120 --category "servicio" --description "Factura cobrada"
python engine/nemesis_mvp.py ledger-add expense paid 12 --category "API" --description "Coste real de herramienta"
python engine/nemesis_mvp.py report
```

Los ejemplos usan una base local `data/nemesis.db`. No se debe usar información ficticia como contabilidad real.

## Reglas económicas
- Caja cobrada no equivale a facturación pendiente ni a oportunidades.
- Los gastos comprometidos reducen la disponibilidad aunque todavía no se hayan pagado.
- La reserva se descuenta antes de considerar excedente reinvertible.
- Las proyecciones se muestran aparte y nunca se suman a la caja disponible.
- No hay compras, contratos, publicaciones ni envíos automáticos.
- El presupuesto mensual queda registrado como límite de control; todavía no hay un ejecutor de gastos y por eso no debe interpretarse como autorización de gasto.

## Predicción y evaluación
Brier binario = (p − y)². Log Loss = −[y ln(p) + (1−y) ln(1−p)], con recorte numérico de seguridad. Las resoluciones no pueden editarse una vez registradas. La evaluación agregada es descriptiva; antes de afirmar ventaja predictiva hay que comparar con una línea base, usar suficientes casos resueltos y evaluar calibración por intervalos.

## Pendiente para cerrar el MVP operativo
1. Conectar RADAR (búsqueda web/YouTube) y registrar automáticamente fuentes con fecha.
2. Orquestación real de agentes/subagentes y reanudación de tareas.
3. Pruebas automatizadas y CI.
4. Importador/compatibilidad con el artefacto histórico de matriz V8.3, una vez recuperado en formato fuente.
5. Revisión de seguridad, copias de respaldo y política de retención.
6. Integración con proveedores solo tras comprobar coste, permisos y límites.

Este repositorio es la web de Némesis; el motor se añade bajo `engine/` sin reemplazar la web estática existente.
