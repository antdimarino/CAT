import os
import json
import pandas as pd


def export_to_json(
    csv_path: str,
    questions_for_category: dict,
    output_path: str = None
) -> str | None:
    """
    Esporta le annotazioni dal CSV in un file JSON strutturato.
    
    Il JSON avrà questa struttura per ogni immagine:
    {
        "img1.jpg": {
            "visibility": {
                "Hat": "Fully Visible",
                "Gills": "Not Visible",
                ...
            },
            "attributes": {
                "Hat Shape": "Convex",
                "Hat Color": "Red",
                ...
            },
            "parts": {
                "Hat": {"x": 120, "y": 85},
                ...
            }
        }
    }
    
    Restituisce il percorso del file JSON creato, o None in caso di errore.
    """
    if not csv_path or not os.path.exists(csv_path):
        print("Export JSON: CSV non trovato.")
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Export JSON: errore lettura CSV: {e}")
        return None

    # Costruisce la lista ordinata di tutte le domande/opzioni
    # per decodificare il vettore binario degli attributi
    all_questions = []
    for category, qlist in questions_for_category.items():
        for question, options in qlist:
            all_questions.append({
                "category": category,
                "question": question,
                "options": options
            })

    result = {}

    for _, row in df.iterrows():
        filename = str(row.get("filename", ""))
        if not filename:
            continue

        entry = {
            "visibility": {},
            "attributes": {},
            "parts": {}
        }

        # --- Visibilità ---
        vis_str = str(row.get("visibility", "")).strip()
        if vis_str and vis_str != "nan":
            vis_vals = [v.strip() for v in vis_str.split(",")]
            idx = 0
            visibility_labels = ["Not Visible", "Partially Visible", "Fully Visible"]
            for category in questions_for_category.keys():
                slice_vals = vis_vals[idx: idx + 3]
                idx += 3
                label = "Not Visible"
                for i, val in enumerate(slice_vals):
                    if val == "1":
                        label = visibility_labels[i]
                        break
                entry["visibility"][category] = label

        # --- Attributi ---
        attr_str = str(row.get("attributes", "")).strip()
        if attr_str and attr_str != "nan":
            attr_vals = [v.strip() for v in attr_str.split(",")]
            idx = 0
            for q in all_questions:
                options = q["options"]
                question = q["question"]

                if len(options) == 2 and set(options) == {"True", "False"}:
                    # Caso booleano: 1 = True, 0 = False
                    if idx < len(attr_vals):
                        value = "True" if attr_vals[idx] == "1" else "False"
                        entry["attributes"][question] = value
                    idx += 1
                else:
                    # Caso multi-opzione: vettore one-hot
                    n = len(options)
                    if idx + n <= len(attr_vals):
                        selected = None
                        for i, val in enumerate(attr_vals[idx: idx + n]):
                            if val == "1":
                                selected = options[i]
                                break
                        entry["attributes"][question] = selected
                    idx += n

        # --- Parti (coordinate) ---
        parts_str = str(row.get("parts", "")).strip()
        if parts_str and parts_str != "nan":
            categories = list(questions_for_category.keys())
            per_category = parts_str.split("|")
            if len(per_category) < len(categories):
                per_category += [""] * (len(categories) - len(per_category))
            for cat, coords_str in zip(categories, per_category):
                coords_str = coords_str.strip()
                if coords_str:
                    try:
                        x_str, y_str = coords_str.split(":")
                        x = float(x_str) if "." in x_str else int(x_str)
                        y = float(y_str) if "." in y_str else int(y_str)
                        entry["parts"][cat] = {"x": x, "y": y}
                    except Exception:
                        entry["parts"][cat] = None
                else:
                    entry["parts"][cat] = None

        result[filename] = entry

    # Percorso output: stesso del CSV ma con estensione .json
    if output_path is None:
        output_path = os.path.splitext(csv_path)[0] + ".json"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        print(f"Export JSON completato: {output_path}")
        return output_path
    except Exception as e:
        print(f"Errore scrittura JSON: {e}")
        return None