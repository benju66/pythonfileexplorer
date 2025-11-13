import os
import json
import pandas as pd
import markdown
import fitz  # PyMuPDF
from PyPDF2 import PdfReader
from docx import Document
from bs4 import BeautifulSoup
from PIL import Image
import cairosvg

class FilePreview:
    @staticmethod
    def preview_text_file(file_path):
        """Preview .txt, .py, .pyc, .json, .ini, .log files."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            return f"Error previewing text file: {e}"

    @staticmethod
    def preview_pdf(file_path):
        """Preview .pdf files using PyMuPDF."""
        try:
            document = fitz.open(file_path)
            text = "\n".join([page.get_text() for page in document])
            document.close()
            return text
        except Exception as e:
            return f"Error previewing PDF: {e}"

    @staticmethod
    def preview_docx(file_path):
        """Preview .docx files."""
        try:
            document = Document(file_path)
            return "\n".join([paragraph.text for paragraph in document.paragraphs])
        except Exception as e:
            return f"Error previewing DOCX: {e}"

    @staticmethod
    def preview_xlsx(file_path):
        """Preview .xlsx and .xls files."""
        try:
            df = pd.read_excel(file_path, engine="openpyxl")
            return df.head().to_string()
        except Exception as e:
            return f"Error previewing Excel file: {e}"

    @staticmethod
    def preview_image(file_path):
        """Preview image files (returns metadata)."""
        try:
            with Image.open(file_path) as img:
                return f"Image size: {img.size}, Format: {img.format}, Mode: {img.mode}"
        except Exception as e:
            return f"Error previewing image: {e}"

    @staticmethod
    def preview_svg(file_path):
        """Convert and preview .svg files as text."""
        try:
            png_output = file_path.replace(".svg", ".png")
            cairosvg.svg2png(url=file_path, write_to=png_output)
            return f"SVG converted to PNG: {png_output}"
        except Exception as e:
            return f"Error previewing SVG: {e}"

    @staticmethod
    def preview_csv(file_path):
        """Preview .csv files using pandas."""
        try:
            df = pd.read_csv(file_path)
            return df.head().to_string()
        except Exception as e:
            return f"Error previewing CSV: {e}"

    @staticmethod
    def preview_html(file_path):
        """Preview .html, .css, .js files."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                soup = BeautifulSoup(content, "html.parser")
                return soup.prettify()
        except Exception as e:
            return f"Error previewing HTML file: {e}"

    @staticmethod
    def preview_md(file_path):
        """Preview .md files as rendered HTML."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                md_content = file.read()
                return markdown.markdown(md_content)
        except Exception as e:
            return f"Error previewing Markdown file: {e}"

    @staticmethod
    def get_preview(file_path):
        """Determine file type and return an appropriate preview."""
        extension = os.path.splitext(file_path)[1].lower()
        
        if extension in [".txt", ".py", ".json", ".ini", ".log"]:
            return FilePreview.preview_text_file(file_path)
        elif extension == ".pdf":
            return FilePreview.preview_pdf(file_path)
        elif extension == ".docx":
            return FilePreview.preview_docx(file_path)
        elif extension in [".xlsx", ".xls"]:
            return FilePreview.preview_xlsx(file_path)
        elif extension in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".ico"]:
            return FilePreview.preview_image(file_path)
        elif extension == ".svg":
            return FilePreview.preview_svg(file_path)
        elif extension == ".csv":
            return FilePreview.preview_csv(file_path)
        elif extension in [".html", ".css", ".js"]:
            return FilePreview.preview_html(file_path)
        elif extension == ".md":
            return FilePreview.preview_md(file_path)
        else:
            return "No preview available for this file type."
