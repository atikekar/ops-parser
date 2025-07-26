import streamlit as st
import pytesseract
from pytesseract import Output
from pdf2image import convert_from_bytes
import pandas as pd
import re
from io import BytesIO
import cv2
from matplotlib import pyplot as plt
from PIL import Image
import PyPDF2
from calendar import month_name
import pdfplumber
import base64
import numpy as np
import os 

# Define the Page class
class Page:
    def __init__(self, page_in, month_in, year_in, name_in, total_in):
        self.page = page_in
        self.month = month_in
        self.year = year_in
        self.name = name_in
        self.total = total_in

# Function to display PDF preview in Streamlit
def display_pdf_preview(input_file):
    # Convert PDF to base64 for embedding
    pdf_bytes = input_file.read()
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    pdf_data_uri = f"data:application/pdf;base64,{pdf_base64}"

    # Embed the PDF in the Streamlit app using an iframe
    st.components.v1.html(f'<iframe src="{pdf_data_uri}" width="700" height="500"></iframe>', height=600)

# Extract month from text
def find_month(text):
    matches = []
    lines = text.split('\n')
    for line in lines:
        month_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        match = re.search(month_pattern, line, re.IGNORECASE)
        if match:
            month = match.group(0).capitalize()
            matches.append(month)
        numeric_month_pattern = r'\b(\d{1,2})[/-]\d{1,2}[/-]\d{4}\b'
        match = re.search(numeric_month_pattern, line)
        if match:
            month_number = match.group(1)
            month_name_found = month_name[int(month_number)]  # Get month name from month_number
            matches.append(month_name_found)
    if matches:
        return max(set(matches), key=matches.count)
    return None

# Extract year from text
def find_year(text):
    matches = []
    lines = text.split('\n')
    for line in lines:
        year_pattern = r'\b(20)\d{2}\b'
        match = re.search(year_pattern, line)
        if match:
            matches.append(int(match.group(0)))
    if matches:
        return max(set(matches), key=matches.count)
    return None

# Extract PDF title from the metadata or fallback to text
def name_backup(file_bytes, text):
    if file_bytes:
        # Using BytesIO to simulate a file-like object from the byte data
        with BytesIO(file_bytes) as file:
            reader = PyPDF2.PdfReader(file)
            metadata = reader.metadata
            if metadata and '/Title' in metadata:
                return metadata['/Title']
            else:
                lines = text.split('\n')
                return lines[0]  # Capitalize the first letter

# Extract name from text or fallback to PDF title
def find_name(text, file_bytes=None):
    matches = []
    lines = text.split('\n')
    for line in lines:
        match = re.search(r'(Name:|Operator:|Facility)[^a-zA-Z0-9]*[:\s-]?\s*(.*)', line, re.IGNORECASE)
        if match:
            name = line.split(':')[-1].strip()
            matches.append(name)
    if not matches:
        pdf_title = name_backup(file_bytes, text)
        return pdf_title
    else:
        return matches[0]

# Extract table data from lines
def extract_table(lines):
    table_data = []
    for line in lines:
        #if line contains all numbers or contains "Total" or "Energy" or "Usage"
        if re.search(r'\bTotal\b|\bEnergy\b|\bUsage\b', line, re.IGNORECASE) or all(char.isdigit() or char.isspace() for char in line):
            # Split the line into columns based on whitespace
            columns = re.split(r'\s+', line.strip())
            # Filter out empty columns
            columns = [col for col in columns if col]
            if columns:
                table_data.append(columns)
    return table_data

# Extract total energy from the "Energy" column in the table
def find_total_energy(image):
    # Get OCR data with bounding boxes
    data = pytesseract.image_to_data(image, output_type=Output.DICT)

    # Find the position of the "Energy" column header
    energy_positions = []

    for i, word in enumerate(data['text']):
        if re.search(r'\bEnergy\b', word, re.IGNORECASE):
            x = data['left'][i]
            y = data['top'][i]
            w = data['width'][i]
            h = data['height'][i]
            center_x = x + w // 2
            energy_positions.append((center_x, y))  # x-center and y-top of "Energy"

    if not energy_positions:
        return []  # Return empty list if no "Energy" header found
    
# Extract text from image using OCR (pytesseract)
def text_from_image(images):
    extracted_text = []
    for image in images:
        if isinstance(image, Image.Image):
            text = pytesseract.image_to_string(image)
            extracted_text.append(text)
        else:
            raise TypeError("Unsupported image object")
    
    return extracted_text

# Function to generate page data and CSV
def find_page_data(extracted_text, images, file_bytes=None):
    page_data = []

    st.write(f"Total pages in PDF: {len(extracted_text)}")

    for i, page in enumerate(extracted_text):
        month_in = find_month(page)
        print(month_in)
        year_in = find_year(page)
        print(year_in)
        name_in = find_name(page, file_bytes=file_bytes)  # Pass the file_bytes to find_name
        print(name_in)
        total_in = find_total_energy(images[i])
        print(total_in)
        page_data.append(Page(i + 1, month_in, year_in, name_in, total_in))
    
    return page_data

# Function to save data to CSV
def save_to_csv(page_data, output_csv_path):
    csv_data = []
    for page in page_data:
        csv_data.append({
            "Page": page.page,
            "Month": page.month,
            "Year": page.year,
            "Name": page.name,
            "Total Energy": page.total
        })
    df = pd.DataFrame(csv_data)
    df.to_csv(output_csv_path, index=False)
    df.to_csv("extracted_data.csv", index=False)

# Main function to execute the Streamlit app
def execute():
    os.environ["PATH"] += ":/opt/homebrew/opt/poppler/bin"
    st.set_page_config(page_title="PDF Processing Application", layout="wide")
    #input_file = st.file_uploader("Upload a PDF file", type=["pdf"], key="pdf_uploader")
    input_path = './sample1.pdf'
    input_file = open(input_path, "rb")

    if input_file is not None:
        st.write("Processing PDF...")
        file_bytes = input_file.read()

        progress_bar = st.progress(0, "Converting PDF to images...")
        images = convert_from_bytes(file_bytes, dpi=200, poppler_path="/opt/homebrew/opt/poppler/bin")

        progress_bar.progress(50, "Extracting text from images...")
        extracted_text = text_from_image(images)
        
        progress_bar.progress(75, "Converting to CSV file.")
        page_data = find_page_data(extracted_text, images, file_bytes=file_bytes)

        input_file_name = input_file.name if input_file.name else "extracted_data.pdf"
        csv_name = input_file_name.replace('.pdf', '_data.csv') if file_bytes else "extracted_data.csv"

        output_csv_path = "/tmp/extracted_data.csv"
        save_to_csv(page_data, output_csv_path)
        

        progress_bar.progress(100, "CSV file created successfully.")
        st.download_button(
            label="Download CSV File",
            data=open(output_csv_path, 'rb').read(),
            file_name=csv_name,
            mime='text/csv'
        )

st.write("## PDF Processing Application")
execute()