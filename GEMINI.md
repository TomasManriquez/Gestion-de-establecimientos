# Reglas de Ingeniería y Calidad — Proyecto SLEP Llanquihue

## 1. Verificación Basada en Evidencia Observable
Antes de afirmar o declarar que una tarea o fase fue "completada con éxito", el agente DEBE:
- Presentar el output real y verificable del comando de ejecución (tests unitarios/integración, build estático, linting).
- No asumir que un código de salida sin salida visual (stdout/stderr vacíos) es garantía de correcto funcionamiento.
- Si una prueba no puede ejecutarse directamente en el entorno del agente, solicitar explícitamente al usuario la verificación con el comando exacto y esperar su retroalimentación antes de dar el paso por concluido.

## 2. Síntesis y Análisis de Infraestructura de Despliegue
Al explorar el proyecto, si existen archivos de despliegue (`Dockerfile`, `docker-compose*.yml`, pipelines CI/CD, Nginx, etc.):
- El agente debe incorporar desde la fase inicial de análisis y planificación una sección de "Impacto en el Entorno de Despliegue".
- Evaluar si los cambios de configuración (variables de entorno, aliases de importación, nuevas dependencias en `package.json`, puertos) requieren rebuild de imágenes, ajustes en volúmenes o sincronización con los contenedores.
- No postergar este análisis ni depender de que el usuario lo evidencie.

## 3. Estrategia de Rollback para Componentes Críticos
Antes de refactorizar o migrar componentes que constituyen puntos críticos de falla ("single point of entry" como `Login`, middlewares de autenticación, o guardias de rutas protegidas):
- Definir un plan explícito de reversión (punto de restauración de git, rama feature aislada o feature flag si aplica).
- Verificar que las pruebas automatizadas del flujo de autenticación existan y pasen antes y después de la migración.
