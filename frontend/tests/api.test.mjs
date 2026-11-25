// Pruebas del cliente HTTP con Node; no necesitan Vue, Vite ni una red.
import test from 'node:test'
import assert from 'node:assert/strict'
import { apiFetch } from '../src/services/api.js'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
const map = new Map()
globalThis.localStorage = { getItem:k=>map.get(k)??null, setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k) }
globalThis.window = new EventTarget()
function resp(status, datos) { return {status,ok:status>=200&&status<300,json:async()=>datos} }
test('api envía token y conserva prefijos', async()=>{
  map.set('token','A')
  globalThis.fetch=async(url,opts)=>{assert.equal(url,'/api/foro/preguntas');assert.equal(opts.headers.Authorization,'Bearer A');return resp(200,[])}
  assert.deepEqual(await apiFetch('foro','/preguntas'),[])
})
test('respuesta de otra sesión no se entrega',async()=>{
  map.set('token','A')
  globalThis.fetch=async()=>{map.set('token','B');return resp(200,{privado:true})}
  await assert.rejects(apiFetch('usuarios','/mensajes'),{name:'AbortError'})
  assert.equal(map.get('token'),'B')
})
test('un 401 de la sesión actual limpia el token y emite evento',async()=>{
  map.set('token','A');map.set('usuario','{}')
  let aviso=false;window.addEventListener('sesion-expirada',()=>{aviso=true},{once:true})
  globalThis.fetch=async()=>resp(401,{error:'Expirada'})
  await assert.rejects(apiFetch('usuarios','/mensajes'),/Expirada/)
  assert.equal(map.has('token'),false);assert.equal(map.has('usuario'),false);assert.equal(aviso,true)
})
test('un 401 de sesión anterior no cierra la nueva',async()=>{
  map.set('token','A')
  globalThis.fetch=async()=>{map.set('token','B');return resp(401,{error:'Expirada'})}
  await assert.rejects(apiFetch('usuarios','/mensajes'),{name:'AbortError'})
  assert.equal(map.get('token'),'B')
})
test('redirect solo permite rutas internas',()=>{
  const src=readFileSync(new URL('../src/services/sesion.js',import.meta.url),'utf8')
  const funcion=src.match(/export function destinoSeguro\(valor\) \{[\s\S]*?\n\}/)[0].replace('export ','')
  const ctx=vm.createContext({});vm.runInContext(funcion,ctx)
  for(const v of ['//example.org','/\\example.org','/\n/example.org','https://example.org',null]) assert.equal(ctx.destinoSeguro(v),'/')
  assert.equal(ctx.destinoSeguro('/preguntas/123?x=1'),'/preguntas/123?x=1')
})

test('una respuesta exitosa vacía JSON no se confunde con error', async()=>{
  map.clear(); globalThis.fetch=async()=>resp(200,[])
  assert.deepEqual(await apiFetch('foro','/preguntas?orden=para_ti'),[])
})
test('un borrador inexistente puede devolver null JSON',async()=>{
  map.clear(); globalThis.fetch=async()=>resp(200,null)
  assert.equal(await apiFetch('foro','/preguntas/borrador'),null)
})
test('una respuesta HTML exitosa no es una lista vacía',async()=>{
  map.clear(); globalThis.fetch=async()=>({ok:true,status:200,json:async()=>{throw new SyntaxError('HTML')}})
  await assert.rejects(apiFetch('foro','/preguntas'),/se esperaba JSON/)
})
test('error de versión conserva HTTP y mensaje original',async()=>{
  map.clear(); globalThis.fetch=async()=>resp(400,{error:'Filtros o paginación inválidos'})
  await assert.rejects(apiFetch('foro','/preguntas?orden=para_ti'),e=>e.status===400&&e.message.includes('reiniciado')&&e.message.includes('Filtros o paginación inválidos'))
})
test('un 400 actualizado muestra el campo inválido, sin sugerir versión anterior',async()=>{
  map.clear();globalThis.fetch=async()=>({...resp(400,{error:'Filtros o paginación inválidos',detalle:'Filtros inválidos: tipo'}),headers:new Headers({'X-Foro-Revision':'comunidades-multimedia-1'})})
  await assert.rejects(apiFetch('foro','/preguntas?orden=para_ti'),e=>e.status===400&&e.message.includes('tipo')&&!e.message.includes('reiniciado'))
})
test('error de votos sin JSON identifica código 404',async()=>{
  map.clear(); globalThis.fetch=async()=>({ok:false,status:404,json:async()=>{throw new SyntaxError('HTML')}})
  await assert.rejects(apiFetch('usuarios','/usuarios/perfil/votos?tipo=respuesta'),e=>e.status===404&&e.message.includes('reiniciado'))
})
test('distingue error de red y cancelación',async()=>{
  map.clear();globalThis.fetch=async()=>{throw new TypeError('red')}
  await assert.rejects(apiFetch('foro','/preguntas'),/No se pudo conectar/)
  globalThis.fetch=async()=>{throw new DOMException('cancelada','AbortError')}
  await assert.rejects(apiFetch('foro','/preguntas'),{name:'AbortError'})
})
