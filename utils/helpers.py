import os
import re


def get_next_crop_index(crop_dir: str, base_name: str) -> int:
    """
    Restituisce il prossimo indice disponibile per un'immagine croppata.
    Es: se esistono img1_1.jpg e img1_2.jpg, restituisce 3.
    """
    existing_files = [
        f for f in os.listdir(crop_dir)
        if f.startswith(base_name + "_")
    ]

    indices = []
    for f in existing_files:
        fname = os.path.splitext(f)[0]
        match = re.search(r'_(\d+)$', fname)
        if match:
            indices.append(int(match.group(1)))

    return max(indices) + 1 if indices else 1