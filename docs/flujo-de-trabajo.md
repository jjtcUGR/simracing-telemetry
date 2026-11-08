# Flujo de trabajo

## Estrategia de ramas

Se sigue un flujo basado en *feature branches* sobre una única rama principal:

* **`main`**: rama estable. Siempre debe compilar y pasar la CI. Está protegida: no se hace *push* directo, todo cambio entra mediante *pull request*.
* **Ramas de trabajo**, creadas desde `main` y con el prefijo del tipo de cambio:
  * `feat/<descripcion>`: nueva funcionalidad (ej. `feat/ingesta-validacion`).
  * `fix/<descripcion>`: corrección de errores.
  * `docs/<descripcion>`: documentación.
  * `chore/<descripcion>`: configuración, CI, dependencias.
  * `refactor/<descripcion>`: cambios internos sin alterar el comportamiento.

Ciclo de vida de un cambio:

1. Elegir o crear la historia de usuario (*issue*) en el tablero.
2. Crear la rama desde `main` actualizada: `git switch -c feat/ingesta-validacion`.
3. Hacer commits pequeños y semánticos.
4. Abrir un *pull request* hacia `main` con la plantilla, enlazando el *issue* (`Resuelve #N`).
5. Esperar a que la CI pase, revisar y fusionar. Borrar la rama tras la fusión.

Cada entrega de hito se marca con una etiqueta de versión semántica (`v0.1.0` para el Hito 1, `v0.2.0` para el Hito 2… hasta `v1.0.0` en el Hito 5).

## Convención de commits

Se usa [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/):

```
<tipo>(<ámbito opcional>): <descripción en imperativo y minúscula>
```

| Tipo | Uso | Ejemplo |
| :--- | :--- | :--- |
| `feat` | Nueva funcionalidad | `feat(ingesta): valida rangos de presiones del setup` |
| `fix` | Corrección de error | `fix(busqueda): devuelve lista vacía si no hay setups` |
| `docs` | Documentación | `docs: añade diagrama de arquitectura` |
| `refactor` | Reestructuración sin cambio funcional | `refactor(analisis): extrae cálculo de vuelta ideal` |
| `test` | Pruebas | `test(analisis): cubre sesiones con vueltas inválidas` |
| `chore` | Configuración, CI, dependencias | `chore(ci): publica imágenes en GHCR` |

## Etiquetas de los issues

| Etiqueta | Uso |
| :--- | :--- |
| `user-story` | Historia de usuario (obligatoria en las historias). |
| `ingesta`, `analisis`, `busqueda`, `infra` | Componente afectado. |
| `bug` | Error detectado. |
| `documentation` | Tareas de documentación. |
