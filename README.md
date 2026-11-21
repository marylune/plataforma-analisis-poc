# Plataforma de análisis comercial: demostración técnica

Evidencia técnica del proyecto de **Gestión de Infraestructura** (UPB). Implementa con
infraestructura como código el componente de procesamiento de archivos de la plataforma y
muestra cómo se gestiona durante su ciclo de vida:

**definición → versionamiento → cambio → implementación → validación → promoción → reversión → operación → recuperación**

- **Proyecto 3 – Plan de Implementación y Operación:** cambio de memoria (v1.4.1) y su reversión (v1.4.2).
- **Proyecto 4 – Proyecto integrador:** observabilidad como código (v1.5.0: tablero del servicio y
  alarma del objetivo de tiempo de procesamiento), simulacro de incidente y prueba de recuperación de datos.

```
Archivo CSV ──► S3 (versionado) ──► EventBridge ──► SQS ──► Lambda (alias "live") ──► DynamoDB
                                                     │
                                                     └──► Cola de errores (tras 2 intentos)
```

| Carpeta | Contenido |
|---|---|
| `infra/` | Plantilla de AWS SAM (`template.yaml`) y parámetros de cada ambiente (`samconfig.toml`) |
| `src/procesamiento/` | Código de la función de procesamiento |
| `politicas/` | Reglas de CloudFormation Guard (política como código) |
| `scripts/` | Validación de los criterios de aceptación, prueba de recuperación de datos y limpieza |
| `bootstrap/` | Rol que permite a GitHub Actions desplegar sin claves guardadas (se crea una sola vez) |
| `.github/` | Pipeline, responsables de revisión y plantillas de solicitud de cambio |
| `docs/` | Guías paso a paso de la demostración y de las evidencias de operación |

**Ramas:** `cambio/<número>-<descripción>` → `main` (despliega a QA) → `produccion` (despliega a producción y publica la versión).

**Operación:** cada ambiente tiene un tablero de CloudWatch (`plataforma-<ambiente>-servicio`) con
los indicadores del servicio y tres alarmas: tiempo de procesamiento, errores de la función y
mensajes en la cola de errores.

> Simplificaciones frente al plan: los tres ambientes están en una sola cuenta de AWS
> (el plan separa producción en otra cuenta), la región es US East (Ohio) porque la cuenta
> usa el plan gratuito de AWS (el plan usa São Paulo) y el repositorio es público para poder
> usar ramas protegidas sin costo (el plan usa un repositorio privado con GitHub Team). Si la
> cuenta no permite OIDC, GitHub usa la clave de un usuario de IAM guardada como secreto
> (`bootstrap/usuario-github.yaml`) en lugar del rol (`bootstrap/rol-github.yaml`). La memoria
> de la función es de 256 MB (y 512 MB tras el cambio) porque las cuentas nuevas tienen una cuota
> de 512 MB en Lambda; el plan usa 1.024 y 2.048 MB. La proporción del cambio (el doble) es la misma.
