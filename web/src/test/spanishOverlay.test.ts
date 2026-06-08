import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('Spanish locale overlay', () => {
  it('preserves workflow chrome, run, queue, and console translations for regenerated locales', () => {
    const source = readFileSync(resolve(__dirname, '../../scripts/es-overlay.ts'), 'utf8');

    [
      "'Search workflow': 'Buscar en flujo de trabajo'",
      "'Find a node by name, type, or parameter': 'Buscar nodo por nombre, tipo o parametro'",
      "'No matching nodes': 'No hay nodos coincidentes'",
      "'Add notes about this workflow...': 'Agregar notas sobre este flujo de trabajo...'",
      "'Close dialog': 'Cerrar dialogo'",
      "'Workflow saved': 'Flujo de trabajo guardado'",
      "'No runs yet — execute a workflow to see results': 'Aun no hay ejecuciones; ejecuta un flujo de trabajo para ver resultados'",
      "'Load workflow into editor': 'Cargar flujo de trabajo en el editor'",
      "'Diff outputs against previous run': 'Comparar salidas con la ejecucion anterior'",
      "'Queue is empty': 'La cola esta vacia'",
      "'Filter logs...': 'Filtrar registros...'",
      "'Save logs to file': 'Guardar registros en archivo'",
      "'No templates yet': 'Aun no hay plantillas'",
      "'Save current workflow as template': 'Guardar flujo de trabajo actual como plantilla'",
      "'Publish template': 'Publicar plantilla'",
      "'Unpublish template': 'Retirar plantilla'",
      "'Public': 'Publica'",
      "'Private': 'Privada'",
      "'Category': 'Categoria'",
      "'Instantiate': 'Instanciar'",
      "'Published by': 'Publicado por'",
      "'Rating': 'Valoracion'",
      "'{{count}} rating': '{{count}} valoracion'",
      "'{{count}} ratings': '{{count}} valoraciones'",
      "'Bookmark': 'Agregar marcador'",
      "'Remove bookmark': 'Quitar marcador'",
      "'Starred': 'Marcada'",
      "'Remove star': 'Quitar estrella'",
      "'Grid size': 'Tamano de cuadricula'",
      "'Edge style': 'Estilo de enlace'",
      "'Step': 'Escalonado'",
      "'Orthogonal': 'Ortogonal'",
      "'Straight': 'Recto'",
      "'Workspace root': 'Raiz del espacio de trabajo'",
      "'Cache location': 'Ubicacion de cache'",
      "'Cleared {{count}} cache entry': '{{count}} entrada de cache borrada'",
      "'Cleared {{count}} cache entries': '{{count}} entradas de cache borradas'",
      "'Anonymous telemetry': 'Telemetria anonima'",
      "'Crash reports': 'Informes de fallos'",
      "'Debug logging': 'Registro de depuracion'",
      "'Experimental features': 'Funciones experimentales'",
      "'Off by default — may be unstable': 'Desactivadas por defecto; pueden ser inestables'",
    ].forEach(entry => expect(source).toContain(entry));
  });
});
