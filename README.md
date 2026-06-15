# CAT: Concept Annotation Tool

<p align="center">
  <b>A Concept Annotation Tool for Supporting the Development of Interpretable Deep Learning Models</b>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#usage">Usage</a> •
  <a href="#export">Export</a> •
  <a href="#citation">Citation</a>
</p>

---

## Overview

CAT (Concept Annotation Tool) is a free, open-source desktop application developed in Python with PyQt5. It is designed to facilitate the rapid and versatile enrichment of any image dataset with fine-grained annotations, including attributes, part locations, bounding boxes, and image crops.

CAT is fully configurable through a simple text file — no coding required. It can be used by domain experts and non-experts alike, thanks to its visual attribute interface that helps annotators choose the correct label through image-based associations.

> 📄 If you use CAT in your research, please cite our paper (see [Citation](#citation)).

---

## Features

| Feature | Description |
|---|---|
| 🖼️ Visual attribute interface | Select attributes via icon buttons instead of typing |
| 👁️ Visibility levels | Mark each category as Not Visible / Partially Visible / Fully Visible |
| 📍 Part coordinate picking | Click on the image to mark the center of each category |
| ✂️ Crop mode | Extract individual subjects from multi-subject images |
| 📦 Bounding box mode | Draw and save bounding boxes for part localization |
| 💾 CSV output | Annotations saved incrementally to a CSV file |
| 🔄 JSON export | Export all annotations to a structured JSON file |
| 🗂️ CSV versioning | Automatic timestamped backup before every save |
| 📊 Statistics window | Charts showing attribute distribution per category |
| 🔍 Image search & filter | Filter by annotated / not annotated, search by filename |
| 🌙 Dark / Light theme | Switch between themes from the View menu |
| 🖥️ Cross-platform | Runs on Windows, macOS, and Linux |

---

## Installation

### Option 1 — Download the executable (recommended)

Pre-built executables are available on the [Releases](../../releases) page:

- **Windows**: `CAT-windows.exe`
- **macOS**: `CAT-macos.app` (or `.dmg`)

No Python installation required.

### Option 2 — Run from source

**Requirements:** Python 3.10+

1. Clone the repository:
```bash
git clone https://github.com/antdimarino/CAT.git
cd CAT
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

### Dependencies

```
PyQt5>=5.15
pandas>=1.5
qt-material>=2.14
matplotlib>=3.7
```

---

## Configuration

CAT is configured through a plain text file (`questions.txt` by default). This file defines the categories, annotation instructions, and possible attribute values for your dataset.

### File format

Each line defines one group of attributes for a category:

```
CategoryName||Instruction for the annotator|Option1|Option2|Option3
```

- `CategoryName` — the part or concept to annotate (e.g., Hat, Color, Borders)
- `||` — separator between category name and instruction
- `Instruction` — text shown to the annotator as guidance
- `Option1|Option2|...` — the possible attribute values, separated by `|`

A category can span multiple lines if it has multiple attribute groups:

```
Hat||Choose from the following Hat Shapes:|Campanulate|Conical|Convex|Depressed|Flat
Hat||Choose from the following Hat Color:|Red|Red-Orange|Yellow-Orange|White|Brown
Hat||Choose from the following Hat Surface:|Smooth|Fibrillated|Flaked|Warty|Zoned
```

### Boolean attributes

Use `True|False` as the two options for yes/no questions:

```
Gills or Tubes||Does the mushroom have gills?|True|False
```

### Visual icons

Each attribute can have an associated reference icon shown in the interface. Place `.png` images in the `imgs/` folder with the **exact same name** as the attribute (case-sensitive):

```
imgs/
  Convex.png
  Campanulate.png
  Red.png
  ...
```

### Loading a custom configuration file

From the application menu: **Tools → Load questions file...**

You can load any `.txt` file formatted as described above. The application will reload the annotation panel accordingly.

> ⚠️ Avoid changing the configuration between annotation sessions to prevent inconsistencies in existing annotations.

---

## Usage

### 1. Launch the application

```bash
python main.py
```

Or open the downloaded executable.

### 2. Load a directory

Click **Load Directory** and select the folder containing your images.

You will be asked whether you have an existing CSV file:
- **Load existing CSV** — continue annotating a previously started session
- **Create new CSV** — start from scratch; a new CSV with all image filenames will be created automatically
- **Continue without CSV** — browse images without saving annotations

### 3. Annotate an image

For each image, and for each category defined in your configuration file:

1. **Set visibility** — click one of the three eye icons:
   - 🚫 Not Visible
   - 👁️ Partially Visible
   - 👁️ Fully Visible
   
   If a category is not visible, its attributes are automatically disabled.

2. **Mark the part location** — after selecting Partially or Fully Visible, click on the image to mark the center of that category. A colored cross will appear.

3. **Select attributes** — click the icon buttons to select the appropriate attribute values for that category.

4. **Submit** — click **Submit** to save the annotation to the CSV file. The next image will load automatically.

### 4. Navigate images

- **← Previous / Next →** — navigate sequentially
- **⇩ Jump button** — jump directly to the first unannotated image
- **Filter buttons** — show All / Todo (unannotated) / Done (annotated) images
- **Search bar** — filter images by filename
- **Arrow keys** — navigate with keyboard (← →)

### 5. Crop mode

Enable via **Tools → Enable Crop Mode**.

Draw a rectangle on the image to crop a subject. The cropped image is saved in a `{species}_cropped/` folder alongside the original, and a corresponding row is added to a separate cropped CSV file.

Use **Copy Whole Image** to copy the entire image to the cropped folder without drawing a rectangle.

### 6. Bounding box mode

Enable via **Tools → Enable Bbox Mode**.

Draw a rectangle on the image to define a bounding box. Click **Submit Bbox** to save the coordinates to the CSV.

---

## Export

### CSV format

Annotations are saved to the CSV file provided at startup. Three columns are added or updated:

| Column | Description |
|---|---|
| `attributes` | Binary vector encoding selected attribute values (one-hot per question) |
| `visibility` | Binary vector encoding visibility level per category (3 values per category) |
| `parts` | Part center coordinates, formatted as `x:y` per category, separated by `\|` |

### JSON export

From the menu: **Tools → Export JSON**

The exported JSON has the following structure per image:

```json
{
  "img1.jpg": {
    "visibility": {
      "Hat": "Fully Visible",
      "Gills or Tubes": "Not Visible"
    },
    "attributes": {
      "Choose from the following Hat Shapes:": "Convex",
      "Choose from the following Hat Color:": "Red"
    },
    "parts": {
      "Hat": { "x": 120, "y": 85 },
      "Gills or Tubes": null
    }
  }
}
```

### CSV versioning

Every time you press **Submit**, a timestamped backup of the CSV is automatically saved in a `csv_backups/` subfolder next to the original CSV file:

```
csv_backups/
  annotations_2026-04-13_15-30-00.csv
  annotations_2026-04-13_16-45-12.csv
  ...
```

The last 10 backups are kept automatically.

---

## Statistics

Open the statistics window from: **Statistics → View Attribute Distribution**

The window shows:
- **Overview tab** — pie chart of annotation progress and stacked bar chart of visibility distribution per category
- **One tab per category** — bar charts showing how many times each attribute value was selected

Click **Export all charts as PNG** to save all charts to a folder of your choice.

---

## Project structure

```
CAT/
├── main.py                    # Application entry point
├── questions.txt                # Default configuration file
├── style.qss                  # Light theme stylesheet
├── style_dark.qss             # Dark theme stylesheet
├── config.json                # Last session paths (auto-generated)
├── ui/
│   ├── image_browser.py       # Main application window
│   ├── image_label.py         # Interactive image widget
│   ├── statistics_window.py   # Statistics and charts window
│   └── collapsible_section.py # Collapsible sidebar sections
├── core/
│   ├── csv_manager.py         # CSV read/write and versioning
│   └── export_manager.py      # JSON export
├── utils/
│   └── helpers.py             # Utility functions
└── imgs/                   # Attribute reference icons (.png)
```

---

## Citation

If you use CAT in your research, please cite:

```bibtex
TBA
```

---

## Authors

- **Vincenzo Bevilacqua** — National Research Council of Italy (CNR), ICAR
- **Antonio Di Marino** — National Research Council of Italy (CNR), ICAR
- **Angelo Ciaramella** — University of Naples Parthenope
- **Ivanoe De Falco** — National Research Council of Italy (CNR), ICAR
- **Giovanna Sannino** — National Research Council of Italy (CNR), ICAR

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
