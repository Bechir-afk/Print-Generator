import io
import smtplib
from email.message import EmailMessage
from typing import List, Optional, Callable
from PySide6.QtCore import QThread, Signal
from pathlib import Path
from PIL import Image

from project_io import TextBoxDef
from render_engine import render_single, _sanitize_filename
import logging

log = logging.getLogger(__name__)

class EmailWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(int)
    finished_err = Signal(str)

    def __init__(self, template_path: str, text_boxes: List[TextBoxDef], datasets: dict, max_rows: int,
                 smtp_server: str, smtp_port: int, sender: str, password: str,
                 receiver_column: str, subject: str, body: str):
        super().__init__()
        self.template_path = template_path
        self.text_boxes = text_boxes
        self.datasets = datasets
        self.max_rows = max_rows
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender
        self.password = password
        self.receiver_column = receiver_column
        self.subject = subject
        self.body = body

    def run(self):
        try:
            template_img = Image.open(self.template_path).convert("RGBA")
            
            # Parse receiver_column format e.g. "[tab_id] HeaderName"
            rec_tab = None
            rec_header = None
            if self.receiver_column and self.receiver_column.startswith("[") and "]" in self.receiver_column:
                rec_tab, rec_header = self.receiver_column[1:].split("]", 1)
                rec_header = rec_header.strip()

            sent_count = 0
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                
                for i in range(self.max_rows):
                    # Determine receiver email
                    receiver_email = ""
                    if rec_tab and rec_tab in self.datasets and rec_header:
                        rows = self.datasets[rec_tab]["rows"]
                        if rows:
                            r_idx = min(i, len(rows) - 1)
                            receiver_email = str(rows[r_idx].get(rec_header, "")).strip()

                    if not receiver_email or "@" not in receiver_email:
                        self.progress.emit(i + 1, self.max_rows)
                        continue  # Skip invalid emails
                        
                    # Render
                    img = render_single(template_img, self.text_boxes, self.datasets, i)
                    filename = _sanitize_filename(receiver_email.split("@")[0]) + "_certificate.png"
                    
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    # Create Message
                    msg = EmailMessage()
                    msg['Subject'] = self.subject
                    msg['From'] = self.sender
                    msg['To'] = receiver_email
                    msg.set_content(self.body)
                    msg.add_attachment(img_byte_arr, maintype='image', subtype='png', filename=filename)
                    
                    server.send_message(msg)
                    sent_count += 1
                    
                    self.progress.emit(i + 1, self.max_rows)

            self.finished_ok.emit(sent_count)
        except Exception as e:
            log.exception("Email worker error")
            self.finished_err.emit(str(e))
