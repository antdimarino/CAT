import os
import json
import shutil
import pandas as pd
from datetime import datetime

CONFIG_PATH = "config.json"
MAX_BACKUPS = 10


def load_config() -> dict:
    """Carica la configurazione dal file config.json."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Errore caricamento config: {e}")
    return {
        "images_path": "",
        "cropped_dir": "",
        "csv_path": "",
        "answers_dir": "",
        "icons_path": ""
    }


def save_config(config: dict):
    """Salva la configurazione nel file config.json."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Errore salvataggio config: {e}")


def load_csv(csv_path: str) -> pd.DataFrame | None:
    """Carica un file CSV e restituisce un DataFrame, o None in caso di errore."""
    try:
        return pd.read_csv(csv_path)
    except Exception as e:
        print(f"Errore caricamento CSV {csv_path}: {e}")
        return None


def save_annotations(
    csv_path: str,
    image_name: str,
    attributes_str: str,
    visibility_str: str,
    points_str: str,
    df: pd.DataFrame
) -> pd.DataFrame | None:
    """
    Salva le annotazioni per un'immagine nel CSV.
    Esegue automaticamente il backup prima di sovrascrivere.
    Restituisce il DataFrame aggiornato, o None in caso di errore.
    """
    try:
        # Backup automatico prima di ogni salvataggio
        backup_csv(csv_path)

        if "attributes" not in df.columns:
            df["attributes"] = ""
        if "visibility" not in df.columns:
            df["visibility"] = ""
        if "parts" not in df.columns:
            df["parts"] = ""

        df.loc[df["filename"] == image_name, "attributes"] = attributes_str
        df.loc[df["filename"] == image_name, "visibility"] = visibility_str
        df.loc[df["filename"] == image_name, "parts"] = points_str

        df.to_csv(csv_path, index=False)
        return df

    except Exception as e:
        print(f"Errore salvataggio annotazioni: {e}")
        return None


def backup_csv(csv_path: str):
    """
    Crea una copia di backup del CSV nella sottocartella csv_backups/.
    Mantiene solo gli ultimi MAX_BACKUPS backup, eliminando i più vecchi.
    """
    if not os.path.exists(csv_path):
        return

    try:
        backup_dir = os.path.join(os.path.dirname(csv_path), "csv_backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base_name = os.path.splitext(os.path.basename(csv_path))[0]
        backup_name = f"{base_name}_{timestamp}.csv"
        backup_path = os.path.join(backup_dir, backup_name)

        shutil.copy2(csv_path, backup_path)
        print(f"Backup creato: {backup_path}")

        # Mantieni solo gli ultimi MAX_BACKUPS backup
        existing_backups = sorted([
            f for f in os.listdir(backup_dir)
            if f.startswith(base_name) and f.endswith(".csv")
        ])

        while len(existing_backups) > MAX_BACKUPS:
            oldest = os.path.join(backup_dir, existing_backups.pop(0))
            os.remove(oldest)
            print(f"Backup rimosso (troppo vecchio): {oldest}")

    except Exception as e:
        print(f"Errore durante il backup: {e}")


def load_cropped_csv(folder_path: str, species_name: str) -> pd.DataFrame | None:
    """
    Carica il CSV delle immagini croppate, se esiste.
    """
    if not species_name:
        return None

    cropped_csv_path = os.path.join(
        os.path.dirname(folder_path),
        f"{species_name}_cropped.csv"
    )

    if os.path.exists(cropped_csv_path):
        return load_csv(cropped_csv_path)

    return None


def get_species_name(df: pd.DataFrame) -> str:
    """
    Estrae il nome della specie dal DataFrame, se disponibile.
    """
    if df is not None and "species" in df.columns and not df.empty:
        return str(df.iloc[0]["species"]).replace(" ", "_")
    return ""

def sync_csv_with_folder(df: pd.DataFrame, image_list: list) -> pd.DataFrame:
    """
    Aggiunge al DataFrame le righe mancanti per le immagini
    presenti nella cartella ma non nel CSV.
    Restituisce il DataFrame aggiornato.
    """
    if "filename" not in df.columns:
        return df

    existing_files = set(df["filename"].tolist())
    missing_files = [img for img in image_list if img not in existing_files]

    if not missing_files:
        return df

    # Crea righe vuote per le immagini mancanti
    empty_rows = pd.DataFrame({"filename": missing_files})

    # Aggiunge le colonne mancanti con valori vuoti
    for col in df.columns:
        if col != "filename":
            empty_rows[col] = ""

    df = pd.concat([df, empty_rows], ignore_index=True)
    print(f"Aggiunte {len(missing_files)} nuove immagini al CSV: {missing_files}")
    return df