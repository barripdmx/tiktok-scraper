"""
Gemini API - Test de API key en todos los modelos disponibles
stdlib-only (urllib, json)
"""

import json
import urllib.request
import urllib.error
import sys

API_KEY = "TU_GEMINI_API_KEY_AQUI"  # <-- cambia esto

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def list_models():
    url = f"{BASE_URL}/models?key={API_KEY}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    return data.get("models", [])


def test_model(model_name):
    """Envía un prompt simple al modelo y devuelve (ok, respuesta_o_error)"""
    url = f"{BASE_URL}/{model_name}:generateContent?key={API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": "Hola, responde solo con OK"}]}]
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        # Extraer texto de respuesta
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "(sin texto)")
        )
        return True, text.strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body[:200]
        return False, f"HTTP {e.code}: {msg}"
    except Exception as e:
        return False, str(e)


def main():
    print(f"Usando API key: {API_KEY[:8]}...{API_KEY[-4:]}\n")

    print("Obteniendo lista de modelos...")
    try:
        models = list_models()
    except Exception as e:
        print(f"Error al listar modelos: {e}")
        sys.exit(1)

    # Filtrar solo modelos que soporten generateContent
    testable = [
        m for m in models
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]

    print(f"Modelos con generateContent: {len(testable)} de {len(models)} totales\n")
    print(f"{'MODELO':<50} {'OK':^4} {'RESPUESTA'}")
    print("-" * 100)

    ok_count = 0
    for m in testable:
        name = m["name"]  # formato: "models/gemini-2.0-flash"
        ok, result = test_model(name)
        status = "✓" if ok else "✗"
        if ok:
            ok_count += 1
        # Truncar respuesta larga
        result_display = result[:60] + "..." if len(result) > 60 else result
        print(f"{name:<50} {status:^4} {result_display}")

    print("-" * 100)
    print(f"\nResumen: {ok_count}/{len(testable)} modelos funcionando con tu API key")


if __name__ == "__main__":
    main()