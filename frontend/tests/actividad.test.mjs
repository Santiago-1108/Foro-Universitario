import test from 'node:test'
import assert from 'node:assert/strict'
import { actividadDeTipo } from '../src/utils/actividad.js'
const actividad=[{id:1,tipo:'publicacion'},{id:1,tipo:'respuesta'},{id:1,tipo:'comentario'}]
for(const tipo of ['publicacion','respuesta','comentario']) test(`actividad exclusiva: ${tipo}`,()=>assert.deepEqual(actividadDeTipo(actividad,tipo),actividad.filter(a=>a.tipo===tipo)))
test('general conserva actividad mixta',()=>assert.deepEqual(actividadDeTipo(actividad,'general'),actividad))
test('una sección vacía no recupera actividad ajena',()=>assert.deepEqual(actividadDeTipo([actividad[0]],'comentario'),[]))
