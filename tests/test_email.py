import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PIL import Image

from project_io import TextBoxDef
from email_engine import EmailWorker

class TestEmailWorker(unittest.TestCase):
    @patch("email_engine.smtplib.SMTP")
    def test_email_worker_success(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        with tempfile.TemporaryDirectory() as tmpdir:
            tpl_path = Path(tmpdir) / "template.png"
            Image.new("RGBA", (400, 300), "white").save(tpl_path)

            box = TextBoxDef(
                id="b1", x=50, y=50, width=300, height=50,
                font_path="", font_size=24,
                hex_color="#000000", variable="Name", linked_csv="0"
            )
            
            datasets = {
                "0": {
                    "headers": ["Email", "Name"],
                    "rows": [
                        {"Email": "alice@example.com", "Name": "Alice"},
                        {"Email": "bob@example.com", "Name": "Bob"},
                        {"Email": "invalid_email", "Name": "Charlie"} # Should be skipped
                    ]
                }
            }

            worker = EmailWorker(
                str(tpl_path), [box], datasets, max_rows=3,
                smtp_server="localhost", smtp_port=587,
                sender="me@example.com", password="pass",
                receiver_column="[0] Email", subject="Test", body="Hello"
            )
            
            # Use synchronous run for testing
            worker.run()
            
            # Expecting 2 valid emails sent
            self.assertEqual(mock_server.send_message.call_count, 2)
            
            # Check MIME payload
            first_msg = mock_server.send_message.call_args_list[0][0][0]
            self.assertEqual(first_msg['Subject'], "Test")
            self.assertEqual(first_msg['To'], "alice@example.com")
            
            # Assert attachment exists
            self.assertTrue(first_msg.is_multipart())

if __name__ == "__main__":
    unittest.main()
