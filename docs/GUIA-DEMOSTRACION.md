# Guía paso a paso de la demostración técnica

Esta guía lleva al equipo desde cero hasta tener todas las evidencias de la **parte B** y el
material para el **video de la sustentación (parte C)**. Cada paso indica quién lo hace y qué
capturas (📸) o grabaciones (🎥) hay que guardar.

- **Tiempo total aproximado:** 3 a 4 horas, repartidas en dos o tres sesiones.
- **Costo:** USD 0 con una cuenta nueva en el **plan gratuito** de AWS (fase 1). GitHub Actions
  no cobra en repositorios públicos. Lambda, SQS, DynamoDB, CloudFormation, CloudWatch y X-Ray
  tienen niveles siempre gratuitos que la demostración no supera, y lo poco que usa S3 se
  descuenta de los créditos de bienvenida, no de la tarjeta. Aun así, se crea una alerta de
  gasto (fase 1) y al final se borra todo (fase 10).
- **Roles en la demostración** (para que los tres participen y quede evidencia de colaboración):

| Integrante | Papel en la demostración |
|---|---|
| Mary | Autora de los cambios en el código (IaC) y responsable de montar el repositorio |
| Camilo | Responsable de infraestructura: revisa y aprueba en `main` y en `produccion` |
| Mateo | Responsable del servicio y de la validación: registra la solicitud de cambio, aprueba en `produccion` y revisa los resultados de las pruebas |

> **Consejo para las capturas:** guárdenlas en una carpeta compartida con nombres que
> indiquen la fase, por ejemplo `F6-03-conjunto-de-cambios-qa.png`. Antes de pegarlas en el
> documento, tapen el número de la cuenta de AWS y los correos.

---

## Fase 0. Requisitos

1. Una cuenta de AWS (la crea o presta **un** integrante; se recomienda Mary). Si es nueva,
   se necesita una tarjeta para el registro.
2. Una cuenta de GitHub para cada integrante.
3. Git instalado en el computador de Mary (https://git-scm.com). No se necesita instalar la CLI
   de AWS ni la de SAM: todo lo que usa AWS lo ejecuta GitHub Actions.

---

## Fase 1. Cuenta de AWS con el plan gratuito y control de costos (Mary)

1.1. Cree una cuenta **nueva** de AWS (https://aws.amazon.com/free) con un correo que nunca se
haya usado en AWS. Durante el registro, elija el **plan gratuito (Free plan)**, no el plan de pago.
Con el plan gratuito, AWS no cobra nada a la tarjeta: el uso se descuenta de los créditos de
bienvenida (USD 100) y la cuenta se cierra sola cuando se acaban o a los 6 meses, salvo que
alguien la pase al plan de pago.

- AWS pide una tarjeta para verificar la identidad y hace un cobro temporal de USD 1 que reembolsa en unos días.
- **No** pase la cuenta al plan de pago y **no** la una a AWS Organizations, porque eso la convierte en una cuenta de pago.

1.2. Inicie sesión en la consola y, arriba a la derecha, seleccione la región **US East (Ohio) –
us-east-2**. Las cuentas en el plan gratuito pueden tener disponibles solo algunas regiones; por
eso la demostración usa Ohio y no São Paulo, que es la región del plan (sección 1). Es una
simplificación que debe mencionarse en la descripción de la demostración.

1.3. Vaya a **Billing and Cost Management → Budgets → Create budget**, elija la plantilla
**Monthly cost budget**, ponga un monto de **USD 1** y su correo. Con el plan gratuito no habrá
cobros, pero la alerta avisa si la demostración consume créditos más de lo esperado. Crear un
presupuesto es además una de las actividades que suman USD 20 de créditos adicionales.

📸 `F1-01-presupuesto.png`: el presupuesto creado (evidencia del control de costos de la sección 5.5).
📸 `F1-02-plan-gratuito.png`: en **Billing and Cost Management → Free Tier**, el plan gratuito y los créditos disponibles.

---

## Fase 2. Repositorio en GitHub (Mary)

2.1. En GitHub, cree un repositorio **público** llamado `plataforma-analisis-poc`, **sin**
README ni `.gitignore` (vacío). Es público por dos razones: las ramas protegidas son gratuitas
en repositorios públicos y la profesora puede abrirlo con el enlace.

2.2. En **Settings → Collaborators → Add people**, invite a Camilo y a Mateo con permiso de
escritura. Ellos deben aceptar la invitación desde su correo.

2.3. Todavía **no** suba el código: primero hay que crear el rol de AWS (fase 3). Si se sube
antes, el pipeline intenta desplegar y falla porque no tiene permisos.

---

## Fase 3. Permitir que GitHub despliegue en AWS (Mary)

GitHub Actions no usará claves de acceso guardadas. En su lugar, AWS confía en GitHub mediante
OpenID Connect y le permite asumir un rol limitado al repositorio del equipo.

3.1. En la consola de AWS, vaya a **CloudFormation → Create stack → With new resources (standard)**.

3.2. Elija **Upload a template file** y suba `bootstrap/rol-github.yaml` tal como está, sin
modificarlo. Pulse **Next**.

3.3. La consola muestra la pantalla **Specify stack details**, con un formulario donde se escriben
el nombre de la pila y los valores de los parámetros (no se editan en el archivo):
   - **Stack name:** `plataforma-bootstrap`.
   - `PropietarioGitHub`: su usuario de GitHub, exactamente como aparece en la URL del repositorio
     (en `https://github.com/marylunasalcedohoyos/plataforma-analisis-poc` sería `marylunasalcedohoyos`).
   - `RepositorioGitHub`: ya viene con `plataforma-analisis-poc`; déjelo así.
   - `CrearProveedorOIDC`: ya viene con `si`; déjelo así. Cámbielo a `no` solo si la creación falla
     porque el proveedor ya existe en la cuenta.

   📸 `B-bootstrap-parametros.png`: el formulario con los tres parámetros diligenciados.

   En la pantalla siguiente (**Configure stack options**) no cambie nada y pulse **Next**.

3.4. Avance hasta el final, marque la casilla **I acknowledge that AWS CloudFormation might
create IAM resources with custom names** y cree la pila.

3.5. Cuando el estado sea `CREATE_COMPLETE`, abra la pestaña **Outputs** y copie el valor de
`ArnRolDespliegue`.

   Si el estado queda en `CREATE_FAILED` o `ROLLBACK_COMPLETE`: abra la pestaña **Events**, busque
   la primera fila en rojo y lea la columna **Status reason** (ahí está la causa). Luego elimine la
   pila con **Delete** (una pila fallida no se puede reutilizar) y créela de nuevo desde el paso 3.1.

3.6. En GitHub, en el repositorio, vaya a **Settings → Secrets and variables → Actions →
Variables → New repository variable** y cree dos variables:
   - `AWS_ROLE_ARN` = el valor copiado en el paso 3.5.
   - `AWS_REGION` = `us-east-2`.

📸 `F3-01-pila-bootstrap.png`: pila `plataforma-bootstrap` en `CREATE_COMPLETE`.
📸 `F3-02-variables-github.png`: las dos variables creadas. Es una evidencia de que los secretos
no están en el código: el repositorio solo guarda el identificador del rol.

### Opción B: si la cuenta no permite OIDC

Las cuentas creadas con la nueva experiencia de registro de AWS (plan gratuito, organizadas en
"proyectos") tienen políticas administradas por AWS que impiden crear el proveedor OIDC: la pila
falla con *"not authorized to perform: iam:CreateOpenIDConnectProvider … explicit deny in a
service control policy"*. En ese caso, GitHub usa la clave de acceso de un usuario de IAM con los
mismos permisos que el rol. Los flujos de trabajo ya aceptan las dos formas.

B.1. Si existe la pila `plataforma-bootstrap` fallida, elimínela con **Delete**.

B.2. **CloudFormation → Create stack → With new resources (standard) → Upload a template file**,
suba `bootstrap/usuario-github.yaml` (no tiene parámetros). Nombre de la pila:
`plataforma-bootstrap`. Al final marque la casilla de recursos de IAM y cree la pila.

B.3. Cuando esté en `CREATE_COMPLETE`, vaya a **IAM → Users → plataforma-github-despliegue →
Security credentials → Create access key**. Elija **Application running outside AWS**, pulse
**Next** y **Create access key**. Deje abierta esa pantalla: la clave secreta solo se muestra una vez.

B.4. En GitHub, **Settings → Secrets and variables → Actions**:
   - Pestaña **Secrets → New repository secret**: cree `AWS_ACCESS_KEY_ID` y
     `AWS_SECRET_ACCESS_KEY` con los dos valores de la pantalla anterior. Escríbalos solo ahí:
     no en el código, ni en el documento, ni en un chat.
   - Pestaña **Variables → New repository variable**: cree solo `AWS_REGION` = `us-east-2`.
     **No** cree `AWS_ROLE_ARN`: si existe, los flujos intentan asumir el rol.

📸 `F3-01-pila-bootstrap.png`: la pila en `CREATE_COMPLETE`.
📸 `F3-02-secretos-github.png`: la lista de secretos (GitHub muestra solo los nombres, nunca los
valores). Es la evidencia de que las credenciales no están en el código.

Para el documento: es una simplificación frente al plan, que usa OIDC sin credenciales de larga
duración. La compensación es que la clave se guarda cifrada en GitHub, el usuario no tiene acceso
a la consola y la clave se elimina en la fase 10 al terminar la demostración.

---

## Fase 4. Subir el código y crear QA (Mary)

4.1. Abra `.github/CODEOWNERS` y reemplace `@usuario-camilo` y `@usuario-mateo` por los usuarios
reales de GitHub de Camilo y Mateo.

4.2. En una terminal, dentro de la carpeta del proyecto (la que contiene este archivo):

```bash
git init -b main
git add .
git commit -m "chore: estructura inicial de la plataforma (v1.4.0)"
git remote add origin https://github.com/<su-usuario>/plataforma-analisis-poc.git
git push -u origin main
```

4.3. En GitHub, abra la pestaña **Actions**. Se ejecuta el flujo **Desplegar**: construye la
función, crea la pila `plataforma-qa` y corre la **Validación en QA**, que carga 10 archivos de
10 MB y mide el tiempo de procesamiento. La primera vez tarda entre 8 y 12 minutos.

4.4. Cuando termine, abra la ejecución y baje hasta el **resumen (Summary)**. Ahí están el
registro del despliegue (versión, commit, quién lo ejecutó, fecha y versión activa de la
función) y la tabla de validación.

📸 `F4-01-actions-qa.png`: la ejecución en verde con sus trabajos.
📸 `F4-02-resumen-despliegue-qa.png`: el resumen del despliegue.
📸 `F4-03-validacion-qa-1024.png`: **importante**, es la **línea base** del escenario de cambio
(memoria de 1.024 MB, promedio y percentil 95 del procesamiento). Anoten los valores.
📸 `F4-04-recursos-qa.png`: en AWS, **CloudFormation → plataforma-qa → Resources**, con todos
los recursos creados desde el código.
📸 `F4-05-alias-qa.png`: en **Lambda → plataforma-qa-procesamiento → Aliases → live**, la versión
a la que apunta el alias y su descripción ("v1.4.0 - 1024 MB").

> Si el despliegue falla, abra el paso que salió en rojo y copie el error: casi siempre es
> el nombre de usuario en la pila `plataforma-bootstrap` o las variables del paso 3.6.

---

## Fase 5. Crear producción (Mary)

5.1. En GitHub, vaya a **Branches** (o al selector de ramas) y cree la rama `produccion` a partir de `main`.

5.2. Esto ejecuta **Desplegar** para producción: crea la pila `plataforma-prod` y el trabajo
**Publicar versión** crea la etiqueta y la versión `v1.4.0` en **Releases**.

📸 `F5-01-actions-prod.png`: la ejecución de producción.
📸 `F5-02-release-v1.4.0.png`: la versión `v1.4.0` publicada.

Con esto queda el **estado inicial** del escenario de la sección 9.1: producción opera con la versión `v1.4.0`.

---

## Fase 6. Proteger las ramas (Mary)

En **Settings → Branches → Add classic branch protection rule** (o **Rulesets**), cree dos reglas:

**Regla para `main`**
- ✅ Require a pull request before merging → **Required approvals: 1**
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require review from Code Owners
- ✅ Require status checks to pass → agregue **Validar plantilla** y **Conjunto de cambios**.
  Si no aparecen en la lista, escriba el nombre exacto; aparecen después de la primera solicitud de integración.
- ✅ Do not allow bypassing the above settings
- ⛔ Allow force pushes y Allow deletions: **desactivados**

**Regla para `produccion`**
- Igual que `main`, pero con **Required approvals: 2**, y en los controles obligatorios agregue
  también **Verificar validación en QA**.

Además, en **Settings → General → Pull Requests**, deje activas **Allow squash merging** (para
`main`) y **Allow merge commits** (para `produccion`).

📸 `F6-01-proteccion-main.png` y 📸 `F6-02-proteccion-produccion.png`: las reglas configuradas.
Esto es evidencia directa de la sección 7.2.

---

## Fase 7. Escenario de cambio #63 (los tres; es el centro de la demostración)

Esta fase reproduce la sección 9 del plan. 🎥 **Graben esta fase completa en pantalla**, aunque
luego la editen: es el material principal del video.

### 7.1. Solicitud (Mateo)

En **Issues → New issue → Solicitud de cambio**, complete la plantilla:
- **Qué:** aumentar la memoria de la función de procesamiento de 1.024 MB a 2.048 MB en QA y producción.
- **Por qué:** el tiempo de procesamiento de la línea base (captura F4-03) y la campaña comercial que puede duplicar las cargas.
- **Componentes:** función de procesamiento.
- **Criterios de éxito:** percentil 95 del procesamiento menor que el de la línea base y menor a 60 s, sin mensajes en la cola de errores.

Anoten el número que GitHub le asigna; en el plan se usó **#63**. Si el número es otro, úsenlo
en todos los pasos y actualicen la sección 9.

📸 `F7-01-solicitud.png`: la solicitud creada.

### 7.2. Análisis (Camilo)

Camilo comenta en la solicitud el análisis de impacto, dependencias y riesgos (puede copiar el
resumen de la sección 9.3) y la clasifica como **cambio normal**.

📸 `F7-02-analisis.png`: el comentario de análisis.

### 7.3. Modificación (Mary)

```bash
git checkout main && git pull
git checkout -b cambio/63-memoria-procesamiento
```

Edite `infra/samconfig.toml`: en las secciones `[qa.deploy.parameters]` y `[prod.deploy.parameters]`
cambie `MemoriaProcesamiento=1024` por `MemoriaProcesamiento=2048`. Edite también `VERSION`:
cambie `1.4.0` por `1.4.1`, porque es un ajuste de configuración y corresponde a PARCHE (sección 7.2).

```bash
git add infra/samconfig.toml VERSION
git commit -m "perf(procesamiento): aumentar la memoria de la función de procesamiento a 2.048 MB (#63)"
git push -u origin cambio/63-memoria-procesamiento
```

📸 `F7-03-diferencia.png`: en GitHub, la comparación del commit (las dos líneas de memoria y la versión).

**Prueba en desarrollo:** en **Actions → Desplegar → Run workflow**, elija la rama
`cambio/63-memoria-procesamiento` y ejecute. Se crea la pila `plataforma-dev` y el trabajo
**Prueba en desarrollo** procesa 3 archivos para comprobar que la función sigue funcionando.

📸 `F7-04-prueba-dev.png`: el resumen de la prueba en desarrollo.

### 7.4. Revisión e integración en `main` (Mary abre, Camilo aprueba)

Abra la solicitud de integración (**Pull request**) de la rama hacia `main`. Complete la
plantilla y escriba `Resuelve #63`. Se ejecutan los controles automáticos:
- **Validar plantilla**: `sam validate --lint` y las reglas de CloudFormation Guard (todas en PASS).
- **Conjunto de cambios**: muestra qué se modificará en QA.

En el resumen del conjunto de cambios deben aparecer:
- **Modify** de `FuncionProcesamiento`;
- **Add** de una nueva `FuncionProcesamientoVersion…`;
- **Modify** del alias `FuncionProcesamientoAliaslive`;
- **Remove** de la versión anterior, que SAM conserva en la cuenta, así que sigue disponible para revertir.

No debe aparecer ningún **Replace** de la tabla, el bucket o las colas.

📸 `F7-05-pr-controles.png`: la solicitud con los controles en verde.
📸 `F7-06-guard.png`: el resumen de CloudFormation Guard.
📸 `F7-07-conjunto-cambios-qa.png`: el conjunto de cambios (es una de las evidencias más importantes).

Camilo revisa y aprueba (**Review changes → Approve**) con un comentario que confirme que el
conjunto de cambios corresponde con la solicitud. Luego se integra con **Squash and merge**,
dejando el mensaje del commit con el `(#63)`.

📸 `F7-08-aprobacion-main.png`: la aprobación de Camilo.

### 7.5. Implementación y validación en QA (automático; Mateo revisa)

La integración ejecuta **Desplegar** en QA y la **Validación en QA** con la nueva memoria.

📸 `F7-09-validacion-qa-2048.png`: el resumen de validación con **2048 MB**. Compárenlo con
F4-03: el percentil 95 debe bajar.
📸 `F7-10-alias-qa-nuevo.png`: en Lambda, el alias `live` de QA apunta a una versión nueva con
descripción "v1.4.1 - 2048 MB".
📸 `F7-11-cloudwatch-duracion.png`: en **CloudWatch → Metrics → Lambda → By Function Name →
plataforma-qa-procesamiento → Duration**, la gráfica de las dos pruebas. Se ve la caída del tiempo.

Mateo comenta en la solicitud #63 los resultados (antes y después) y adjunta el informe. El
informe se descarga desde la ejecución, en **Artifacts → informe-qa**.

📸 `F7-12-resultados-en-solicitud.png`: el comentario de Mateo.

### 7.6. Promoción a producción (Mary abre, Camilo y Mateo aprueban)

Abra una solicitud de integración de `main` hacia `produccion`. Además de los controles
anteriores, se ejecuta **Verificar validación en QA**, que solo pasa si el mismo commit superó
la validación en QA. Revise el **Conjunto de cambios** de producción.

Camilo y Mateo aprueban. Se integra con **Create a merge commit**.

📸 `F7-13-pr-produccion.png`: la solicitud con los tres controles y las dos aprobaciones.

🎥 **Despliegue gradual:** mientras corre **Desplegar** en producción, abra en AWS **CodeDeploy →
Deployments** y abra el despliegue en curso. Se ve cómo el 10 % del tráfico pasa a la nueva
versión y, después de 5 minutos, el resto.

📸 `F7-14-codedeploy-canary.png`: el despliegue gradual en curso o terminado.
📸 `F7-15-release-v1.4.1.png`: la versión `v1.4.1` en **Releases**, con la referencia al cambio.

### 7.7. Cierre (Mateo)

Mateo cierra la solicitud #63 con un comentario: versión `v1.4.1` en producción, resultados de
la validación y confirmación de que se cumplen los criterios de éxito.

📸 `F7-16-cierre.png`: la solicitud cerrada, con toda la conversación.

---

## Fase 8. Reversión (Mary y Camilo)

Corresponde a la sección 9.7: se decide **revertir** el cambio, por ejemplo porque el costo superó lo previsto.

8.1. En la solicitud de integración del cambio #63 que se integró en `main`, use el botón
**Revert**. GitHub crea una rama y una solicitud de reversión.

8.2. En esa rama, edite `VERSION` y ponga `1.4.2`. La reversión dejaría `1.4.0`, y esa versión
ya existe; el pipeline no permite repetir versiones.

8.3. Siga el mismo camino: controles automáticos (el conjunto de cambios muestra la memoria
volviendo a 1.024 MB), aprobación de Camilo, integración en `main`, validación en QA, promoción
a `produccion` y versión `v1.4.2`.

📸 `F8-01-pr-reversion.png`: la solicitud de reversión.
📸 `F8-02-conjunto-cambios-reversion.png`: el conjunto de cambios con la memoria de vuelta a 1.024 MB.
📸 `F8-03-alias-revertido.png`: el alias de producción apuntando a una versión con "1024 MB".
📸 `F8-04-releases.png`: la lista de versiones `v1.4.0`, `v1.4.1` y `v1.4.2`. Es la historia completa.

**Opcional (más vistoso): reversión automática.** Durante el despliegue gradual en producción
de la fase 7.6 o la 8.3, cargue en el bucket `plataforma-prod-archivos-…`, dentro de una carpeta
`invalidos/`, cualquier archivo. La función falla a propósito, se activa la alarma de errores y
CodeDeploy devuelve el tráfico a la versión anterior sin intervención. Luego CloudFormation deshace
el cambio y el pipeline termina en rojo. Para completar el cambio, espere a que la alarma vuelva
a OK y ejecute de nuevo el flujo.

🎥 Graben CodeDeploy mostrando el estado **Stopped/Rolled back**.
📸 `F8-05-rollback-automatico.png`: la captura correspondiente.

---

## Fase 9. Reproducibilidad, drift y recuperación (los tres)

### 9.1. Consistencia entre ejecuciones (sección 8.1)

En **Actions**, abra la última ejecución de **Desplegar** en `main` y use **Re-run all jobs**. Al
volver a desplegar la misma versión, el registro dice **No changes to deploy**.

📸 `F9-01-sin-cambios.png`: la línea "No changes to deploy" en el registro.

### 9.2. Reconstruir un ambiente desde el código (sección 8.2)

En **Actions → Desplegar → Run workflow**, elija la rama `main`. Se actualiza `plataforma-dev`
con exactamente la misma versión que QA.

📸 `F9-02-dev-reconstruido.png`: comparación de los recursos de `plataforma-dev` y
`plataforma-qa` en CloudFormation. Son los mismos recursos con distinto nombre de ambiente.

### 9.3. Detección de drift (secciones 2.4 y 8.3)

1. En la consola de AWS, abra **Lambda → plataforma-dev-procesamiento → Configuration → General
   configuration → Edit** y cambie la memoria a mano (por ejemplo, a 1536 MB). Este es el cambio
   no controlado que el plan quiere evitar.
2. En GitHub, ejecute **Actions → Detección de drift → Run workflow**.
3. El flujo encuentra la diferencia y abre automáticamente una solicitud "Drift detectado…" que
   muestra el valor esperado (1024) y el real (1536).
4. Corrija: devuelva la memoria a 1024 MB en la consola, ejecute de nuevo la detección y compruebe
   que `plataforma-dev` aparece como `IN_SYNC`. Cierre la solicitud con un comentario.

📸 `F9-03-cambio-manual.png`, 📸 `F9-04-drift-detectado.png` (la solicitud creada sola) y
📸 `F9-05-in-sync.png`.
🎥 Esta secuencia también funciona muy bien en el video.

### 9.4. Mensajes fallidos (sección 5.4)

En **Actions → Prueba de la cola de errores → Run workflow** (ambiente `qa`). Carga un archivo
válido y uno inválido, y confirma que el inválido llega a la cola de errores después de los dos
intentos. Tarda entre 6 y 12 minutos.

📸 `F9-06-cola-errores.png`: el resumen de la prueba. Opcional: en **SQS →
plataforma-qa-cola-errores → Send and receive messages → Poll for messages**, el mensaje fallido.

---

## Fase 10. Limpieza (Mary, al terminar la entrega)

1. En la consola de AWS, abra **CloudShell** (ícono de terminal arriba a la derecha), en la región Ohio (us-east-2).
2. **Actions → Upload file** y suba `scripts/limpiar.sh`.
3. Ejecute `bash limpiar.sh`. Vacía los buckets, quita la protección de la tabla de producción
   y elimina las tres pilas.
4. Por último, en **CloudFormation**, elimine la pila `plataforma-bootstrap`. Si usó la opción B
   de la fase 3, antes elimine la clave de acceso en **IAM → Users → plataforma-github-despliegue →
   Security credentials** (si no, la pila no puede borrar el usuario) y borre los dos secretos en GitHub.

> No borren el repositorio de GitHub: es la evidencia de la parte B.

---

## Qué evidencia va en cada subtítulo de la parte B del documento

| Subtítulo del documento | Capturas |
|---|---|
| Descripción de la demostración técnica | Diagrama del README y un párrafo del alcance |
| Enlace del repositorio | URL del repositorio público |
| Componentes seleccionados | F4-04 (recursos en CloudFormation) |
| Definición IaC y versiones | Fragmento de `template.yaml` y `samconfig.toml`, F6-01, F6-02 y F8-04 |
| Cambios realizados y resultados de ejecución | F7-01, F7-03, F7-05, F7-07, F7-08, F7-13, F7-14 y F7-15 |
| Validaciones | F4-03 comparada con F7-09, F7-11, F7-06, F9-01, F9-05 y F9-06 |
| Evidencia de reversión | F8-01 a F8-04 (y F8-05 si hicieron la reversión automática) |

## Solución de problemas frecuentes

| Problema | Causa probable y solución |
|---|---|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | El usuario o el repositorio de la pila `plataforma-bootstrap` no coincide con el de GitHub (mayúsculas incluidas). Actualice la pila con el valor correcto. |
| `Could not assume role` o variables vacías | Falta `AWS_ROLE_ARN` o `AWS_REGION` en **Settings → Secrets and variables → Actions → Variables**. |
| `iam:CreateOpenIDConnectProvider … explicit deny in a service control policy` | La cuenta no permite OIDC. Use la opción B de la fase 3. |
| `Credentials could not be loaded` con la opción B | Faltan los secretos `AWS_ACCESS_KEY_ID` o `AWS_SECRET_ACCESS_KEY`, o tienen espacios de más. |
| CloudShell: *Your account verification is in progress* | La cuenta nueva aún se está verificando (hasta dos días). Espere y vuelva a intentar. |
| La validación en QA falla por tiempo | Revise en CloudWatch los registros de la función. Si el tiempo supera 60 s con 1.024 MB, baje `PasadasProcesamiento` (por ejemplo, a 250) en los tres ambientes de `samconfig.toml`, con un cambio por el proceso normal. |
| `Rate exceeded` o errores de concurrencia en Lambda | Las cuentas nuevas pueden tener una cuota de concurrencia baja. Pida un aumento en **Service Quotas → AWS Lambda → Concurrent executions**. |
| "La versión vX ya existe" | Falta actualizar `VERSION` en el cambio. |
| Error de CodeDeploy al desplegar (servicio no disponible en el plan gratuito) | Elimine en `infra/template.yaml` el bloque `DeploymentPreference` de la función (4 líneas) con un cambio por el proceso normal. La función sigue publicando versiones con el alias `live` y la reversión se hace como en la fase 8; solo se pierde el despliegue gradual y la reversión automática opcional. |
| El control "Verificar validación en QA" falla | La solicitud hacia `produccion` no viene de `main`, o ese commit todavía no termina la **Validación en QA**. Espere a que termine y vuelva a ejecutar el control. |
