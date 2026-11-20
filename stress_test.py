import concurrent.futures
import time
import requests

# URL de tu app corriendo localmente
URL = "http://127.0.0.1:8000/"
TOTAL_PETICIONES = 100
CONCURRENCIA = 15  # Hilos simultáneos

def hacer_peticion(i):
    inicio = time.time()
    try:
        response = requests.get(URL, timeout=5)
        duracion = time.time() - inicio
        return response.status_code, duracion
    except Exception as e:
        return str(e), 0

print(f"🚀 Iniciando prueba de estrés: {TOTAL_PETICIONES} peticiones con {CONCURRENCIA} hilos concurrentes...")
tiempo_global_inicio = time.time()

exitosos = 0
fallidos = 0
tiempos = []

with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCIA) as executor:
    futures = [executor.submit(hacer_peticion, i) for i in range(TOTAL_PETICIONES)]
    for future in concurrent.futures.as_completed(futures):
        status, duracion = future.result()
        if status == 200:
            exitosos += 1
            tiempos.append(duracion)
        else:
            fallidos += 1

tiempo_total = time.time() - tiempo_global_inicio

print("\n📊 --- RESULTADOS DE LA PRUEBA ---")
print(f"Tiempo total transcurrido: {tiempo_total:.2f} segundos")
print(f"Peticiones exitosas (200 OK): {exitosos}")
print(f"Peticiones fallidas/error: {fallidos}")
if tiempos:
    print(f"Tiempo promedio de respuesta: {(sum(tiempos) / len(tiempos)) * 1000:.2f} ms")
    print(f"Respuesta más rápida: {min(tiempos) * 1000:.2f} ms")
    print(f"Respuesta más lenta: {max(tiempos) * 1000:.2f} ms")