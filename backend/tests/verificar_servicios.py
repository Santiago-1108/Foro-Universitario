"""Diagnóstico de solo lectura, exclusivo de localhost. Sin credenciales ni escrituras."""
import argparse
import json
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

REVISION = 'comunidades-multimedia-1'
SERVICIOS = {'usuarios': (5000, 'usuarios'), 'foro': (5001, 'preguntas'), 'interacciones': (5002, 'votos')}

def consultar(url, revision=False, modulo=None):
    try:
        with urlopen(url, timeout=12) as respuesta:
            datos = json.load(respuesta)
            if revision and (not isinstance(datos, dict) or datos.get('revision') != REVISION or modulo not in datos.get('modulos', [])):
                print('INCOMPATIBLE:', url, 'Revisa la carpeta y reinicia el proceso.'); return False
            print('OK:', url, f'({len(datos)} resultados)' if isinstance(datos,list) else '')
            return True
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
        print('ERROR:', url, str(error)); return False

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--puerto-frontend', type=int, default=5173)
    args=parser.parse_args()
    if not 1 <= args.puerto_frontend <= 65535: parser.error('Puerto inválido')
    base=f'http://127.0.0.1:{args.puerto_frontend}'
    resultados=[]
    for servicio,(puerto,modulo) in SERVICIOS.items():
        resultados.append(consultar(f'http://127.0.0.1:{puerto}/estado-api', True, modulo))
        resultados.append(consultar(f'{base}/api/{servicio}/estado-api', True, modulo))
    if all(resultados):
        resultados.append(consultar(f'{base}/api/foro/preguntas?orden=para_ti&vista=todas&limite=21&offset=0'))
        resultados.append(consultar(f'{base}/api/foro/categorias'))
        resultados.append(consultar(f'{base}/api/foro/comunidades'))
    print('Diagnóstico correcto.' if all(resultados) else 'Corrige los servicios indicados antes de continuar.')
    return 0 if all(resultados) else 1

if __name__=='__main__': raise SystemExit(main())
