# Badgr - Certificate & Badge Generator

![Badgr Icon](icon.png)

**Badgr** is a sleek, modern desktop application built with Python and PySide6 that automates the generation and email delivery of customized certificates, badges, and print assets from CSV data.

## Features

- **Dynamic Data Merging**: Load any CSV file, map the columns directly onto your canvas, and generate hundreds of personalized PNGs in seconds.
- **Smart Alignment Guides (Règle)**: Automatically snap your text elements to the center of the canvas or align them relative to other text boxes.
- **Native OS Fonts**: Access all your Windows system fonts directly from a searchable dropdown menu. No need to manually browse for `.ttf` files!
- **Batch Email Delivery**: Instantly email certificates directly to participants using the built-in SMTP engine—no massive local disk storage required! The app securely generates and attaches PNGs in memory on the fly.
- **Visual Design Canvas**: Drag-and-drop workflow, real-time previews, and instant customization (size, color, alignment).
- **Dark Mode UI**: Clean, modern dark mode crafted with Qt Fusion.

## Installation

### Prerequisites
- Python 3.10+
- Windows OS (Required for native system font lookup)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/Badgr.git
   cd Badgr
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Activate on PowerShell:
   .\.venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Start the application by running:
```bash
python main.py
```

### Quick Workflow
1. **Load Template**: Click "Load Template (PNG)" to add your blank certificate or badge background.
2. **Load Data**: Click "Load CSV Data" to import your participant list.
3. **Add Elements**: Double click anywhere on the canvas to create a text box.
4. **Map & Style**: Use the Properties panel to link the text box to a CSV column (e.g., "Name"), pick a native Windows font, and style the text.
5. **Generate or Send**:
   - **Batch Generate**: Saves all certificates as PNG files to your local machine.
   - **Send Emails**: Directly emails each participant their unique certificate. (Requires SMTP credentials, e.g., Gmail App Password).

## Tech Stack
- **UI Framework**: PySide6 (Qt for Python)
- **Image Rendering**: Pillow (PIL)
- **Background Processing**: Qt QThread
- **Email Delivery**: smtplib (Standard Library)

---
*Created with love by Bechir Touskié*
