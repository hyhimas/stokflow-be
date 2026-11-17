import sys
import os

# Pastikan folder root terbaca oleh runtime Python Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
