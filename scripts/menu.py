# -*- coding: utf-8 -*-
import os
import sys
import subprocess

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def run_script(path):
    print(f"\n🚀 Ejecutando: {os.path.basename(path)}...")
    print("-" * 50)
    try:
        # Ejecutamos con el mismo intérprete de python actual
        # Usamos el path completo para evitar errores de ruta
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), path))
        subprocess.run([sys.executable, script_path], check=True)
    except subprocess.CalledProcessError:
        print(f"\n❌ Error al ejecutar el script.")
    except KeyboardInterrupt:
        print(f"\n⏹️ Ejecución cancelada por el usuario.")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
    input("\nPresiona Enter para volver al menú...")

def main():
    while True:
        clear_screen()
        print("""
============================================================
           TIKTOK OSINT & ANALYTICS TOOLKIT
============================================================
0.  🔑 CONFIGURACIÓN: Iniciar sesión y guardar cookies
    (Haz esto primero para evitar bloqueos)

--- FASE 1: SCRAPING (DESCARGAR DATOS) ---
1.  👤 Scraper de Usuario: Descarga videos de un perfil (@user)
2.  #️⃣ Scraper de Hashtag: Descarga videos por palabra/hashtag
3.  💬 Scraper de Comentarios: Descarga miles de comentarios (Pro)

--- FASE 2: ANÁLISIS (PROCESAR DATOS) ---
4.  📊 Analítica de Publicaciones: Estadísticas de vistas y likes
5.  🗣️ Analítica de Comentarios: Nubes de palabras y actividad
6.  🤖 Sentimiento con IA: Clasifica con Groq gratis (Pos/Neg/Neu)
7.  🔄 Comparativa: Analiza usuarios entre distintas cuentas

--- FASE 3: VISUALIZACIÓN (REPORTES) ---
8.  🌐 GENERAR INFORME HTML: Crea el reporte web interactivo
9.  🕸️ Grafo de Redes: Genera archivo GEXF para Gephi (Nodos)
10. 📅 Análisis de Bots: Gráficas de fecha de creación de cuentas

--- OTROS ---
11. 📂 Abrir carpeta de resultados (Outputs)
12. 📜 Ver Archivos en raíz (Listar)
Q.  ❌ Salir
============================================================
        """)
        
        choice = input("Selecciona una opción (0-12 o Q): ").strip().upper()

        if choice == '0':
            run_script("src/scrapers/1-guardar_sesion.py")
        elif choice == '1':
            run_script("src/scrapers/1_tiktok_scraper_user.py")
        elif choice == '2':
            run_script("src/scrapers/2_tiktok_scraper_hastag_api.py")
        elif choice == '3':
            run_script("src/scrapers/2_tiktok_scraper_comentarios_api.py")
        elif choice == '4':
            run_script("src/analysis/analitica_publicaciones.py")
        elif choice == '5':
            run_script("src/analysis/analitica_comentarios.py")
        elif choice == '6':
            run_script("src/analysis/analizar_sentimiento_groq.py")
        elif choice == '7':
            run_script("src/analysis/comparativa_usuarios.py")
        elif choice == '8':
            run_script("src/visualization/generar_informe_html.py")
        elif choice == '9':
            run_script("src/visualization/crear_gexf.py")
        elif choice == '10':
            run_script("src/utils/enriquecer_csv_fechas_creacion.py")
        elif choice == '11':
            path = os.path.join(os.getcwd(), "outputs", "graphics")
            print(f"Carpeta de resultados: {path}")
            if os.name == 'nt':
                os.startfile(path)
            else:
                subprocess.run(['open', path])
            input("\nPresiona Enter para continuar...")
        elif choice == '12':
            os.system('dir' if os.name == 'nt' else 'ls -R')
            input("\nPresiona Enter para continuar...")
        elif choice == 'Q':
            print("¡Hasta pronto!")
            break
        else:
            input("Opción no válida. Presiona Enter para intentar de nuevo...")

if __name__ == "__main__":
    main()
