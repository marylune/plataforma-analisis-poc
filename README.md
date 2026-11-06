# Plataforma de análisis comercial: demostración técnica

Demostración técnica del **Proyecto 3 – Plan de Implementación y Operación** (Gestión de
Infraestructura, UPB). Implementa con infraestructura como código el componente de
procesamiento de archivos de la plataforma y muestra cómo se gestiona un cambio sobre él:

**definición → versionamiento → cambio → implementación → validación → promoción → reversión**

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
| `scripts/` | Validación de los criterios de aceptación y limpieza |
| `bootstrap/` | Rol que permite a GitHub Actions desplegar sin claves guardadas (se crea una sola vez) |
| `.github/` | Pipeline, responsables de revisión y plantillas de solicitud de cambio |
| `docs/` | Guía paso a paso de la demostración |

**Ramas:** `cambio/<número>-<descripción>` → `main` (despliega a QA) → `produccion` (despliega a producción y publica la versión).

La guía completa está en [`docs/GUIA-DEMOSTRACION.md`](docs/GUIA-DEMOSTRACION.md).

> Simplificaciones frente al plan: los tres ambientes están en una sola cuenta de AWS
> (el plan separa producción en otra cuenta), la región es US East (Ohio) porque la cuenta
> usa el plan gratuito de AWS (el plan usa São Paulo) y el repositorio es público para poder
> usar ramas protegidas sin costo (el plan usa un repositorio privado con GitHub Team). Si la
> cuenta no permite OIDC, GitHub usa la clave de un usuario de IAM guardada como secreto
> (`bootstrap/usuario-github.yaml`) en lugar del rol (`bootstrap/rol-github.yaml`). La memoria
> de la función es de 256 MB (y 512 MB tras el cambio) porque las cuentas nuevas tienen una cuota
> de 512 MB en Lambda; el plan usa 1.024 y 2.048 MB. La proporción del cambio (el doble) es la misma.
