import re
import io
import logging
from flask import Request, make_response, jsonify, send_file
import zcatalyst_sdk
import os
import tempfile
import xlsxwriter
import pandas as pd
from flask import send_file
from io import BytesIO
import PyPDF2

def extract_text_from_pdf(file_path):
    """ Extract text from a readable PDF file """
    text = ""
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text()
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {e}")
    return text.strip()

def extract_pf_fields(text, readable=True):
    if readable:
        field_patterns = {
            "TRRN No": r"TRRN No\s*:\s*(.*)",
            "Challan Status": r"(.*)\s*Challan Status\s*:\s*(.*)",
            "Challan Generated On": r"(.*)\s*Challan Generated On\s*:\s*(.*)",
            "Establishment ID": r"(.*)\s*Establishment ID\s*:\s*(.*)",
            "Establishment Name": r"(.*)\s*Establishment Name\s*:\s*(.*)",
            "Challan Type": r"(.*)\s*Challan Type\s*:\s*(.*)",
            "Total Members": r"(.*)\s*Total Members\s*:\s*(.*)",
            "Wage Month": r"(.*)\s*Wage Month\s*:\s*(.*)",
            "Total Amount (Rs)": r"(.*)\s*Total Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-1 Amount (Rs)": r"(.*)\s*Account-1 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-2 Amount (Rs)": r"(.*)\s*Account-2 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-10 Amount (Rs)": r"(.*)\s*Account-10 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-21 Amount (Rs)": r"(.*)\s*Account-21 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-22 Amount (Rs)": r"(.*)\s*Account-22 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Payment Confirmation Bank":r"Payment\s*Confirmation\s*[\s\n]*Bank\s*:\s*(.*?[A-Za-z\s\-]+)",
            "CRN": r"(.*)\s*CRN\s*:\s*(.*)",
            "Payment Date": r"Payment Date\s*:\s*(.*)",
            "Payment Confirmation Date": r"Payment Confirmation Date\s*:\s*([0-9]{2}-[A-Z]{3}-[0-9]{4})",
            # 
            "Presentation Date": r"Presentation Date\s*:\s*(.*)",
            "Realization Date": r"Realization Date\s*:\s*(.*)",
            "Date of Credit": r"Date of Credit\s*:\s*(.*)",
            "Total PMRPY Benefit": r"(.*)\s*Total PMRPY Benefit\s*:\s*(.*)"
        }
    else:
        field_patterns = {
            "TRRN No": r"TRRN No\s*:\s*(.*)",
            "Challan Status": r"Challan Status\s*:\s*(.*)",
            "Challan Generated On": r"Challan Generated On\s*:\s*(.*)",
            "Establishment ID": r"Establishment ID\s*:\s*(.*)",
            "Establishment Name": r"Establishment Name\s*:\s*(.*)",
            "Challan Type": r"Challan Type\s*:\s*(.*)",
            "Total Members": r"Total Members\s*:\s*(.*)",
            "Wage Month": r"Wage Month\s*:\s*(.*)",
            "Total Amount (Rs)": r"Total Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-1 Amount (Rs)": r"Account-1 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-2 Amount (Rs)": r"Account-2 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-10 Amount (Rs)": r"Account-10 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-21 Amount (Rs)": r"Account-21 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Account-22 Amount (Rs)": r"Account-22 Amount\s*\(Rs\)\s*:\s*(.*)",
            "Payment Confirmation Bank": r"Payment Confirmation Bank\s*:\s*(.*)",
            "CRN": r"CRN\s*:\s*(.*)",
            "Payment Date": r"Payment Date\s*:\s*(.*)",
            "Payment Confirmation Date": r"Payment Confirmation Date\s*:\s*(.*)",
            "Presentation Date": r"Presentation Date\s*:\s*(.*)",
            "Realization Date": r"Realization Date\s*:\s*(.*)",
            "Date of Credit": r"Date of Credit\s*:\s*(.*)",
            "Total PMRPY Benefit": r"Total PMRPY Benefit\s*:\s*(.*)"
        }
    extracted_data = {}
    for field, pattern in field_patterns.items():
        match = re.search(pattern, text)
        # if match:
        #     extracted_data[field] = match.group(1).strip()

        if match:
            value = match.group(1).strip()
            if field == "Payment Confirmation Bank" and not value:
                continue  # Skip this field if it's empty
            extracted_data[field] = value

    # Combine the relevant fields
    extracted_data["Presentation/Payment Date"] = extracted_data.get("Presentation Date") or extracted_data.get("Payment Date")
    extracted_data["Realization/Payment Confirmation Date"] = extracted_data.get("Realization Date") or extracted_data.get("Payment Confirmation Date")

    # Remove the original fields to avoid duplication
    extracted_data.pop("Presentation Date", None)
    extracted_data.pop("Payment Date", None)
    extracted_data.pop("Realization Date", None)
    extracted_data.pop("Payment Confirmation Date", None)

    return extracted_data

def extract_esi_fields(text):
    field_patterns = {
        "Transaction Status": r"Transaction status\s*:\s*(.*?)\s*\n",
        "Employer's Code No": r"Employer's Code No\s*:\s*(.*?)\s*\n",
        "Employer's Name": r"Employer's Name\s*:\s*(.*?)\s*\n",
        "Challan Period": r"Challan Period\s*:\s*(.*?)\s*\n",
        "Challan Number": r"Challan Number\s*:\s*(.*?)\s*\n",
        "Challan Created Date": r"Challan\s+Created\s+Date\s*[:\-]?\s*(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})",
        "Challan Submitted Date": r"Challan\s+Submitted\s+Date\s*[:\-]?\s*(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})",
        "Amount Paid": r"Amount Paid\s*:\s*(.*?)\s*\n",
        "Transaction Number": r"Transaction Number\s*:\s*(.*?)\s*\n"
    }
    extracted_data = {}
    for field, pattern in field_patterns.items():
        match = re.search(pattern, text, re.DOTALL)
        if match:
            extracted_data[field] = match.group(1).strip()
    return extracted_data

def extract_tds_fields(text):
    field_patterns = {
        "ITNS No.": r"ITNS No\.:?\s*([^\n]*)",
        "PAN": r"PAN\s*:? *([^\n]*)",
        "Name": r"Name\s*:? *([^\n]*)",
        "Assessment Year": r"Assessment Year\s*:? *([^\n]*)",
        "Financial Year": r"Financial Year\s*:? *([^\n]*)",
        "Major Head": r"Major Head\s*:? *([^\n]*)",
        "Minor Head": r"Minor Head\s*:? *([^\n]*)",
        "Nature of Payment" : r"Nature of Payment\s*:? *([^\n]*)",
        "Amount (in Rs.)": r"Amount \(in Rs\.\)\s*:? *₹?\s*([^\n]*)",
        "Amount (in words)": r"Amount \(in words\)\s*:? *([^\n]*)",
        "CIN": r"CIN\s*:? *([^\n]*)",
        "Mode of Payment": r"Mode of Payment\s*:? *([^\n]*)",
        "Bank Name": r"Bank Name\s*:? *([^\n]*)",
        "Bank Reference Number": r"Bank Reference Number\s*:? *([^\n]*)",
        "Date of Deposit": r"Date of Deposit\s*:? *([\d]{2}-[A-Za-z]{3}-[\d]{4})",
        "BSR code": r"BSR code\s*:? *([0-9]{7})",
        "Challan No": r"Challan No\s*:? *([0-9]{5})",
        "Tender Date": r"Tender Date\s*:? *(\d{2}/\d{2}/\d{4})",
        "A Tax": r"A *Tax *([^\n]*)",
        "B Surcharge": r"B *Surcharge *([^\n]*)",
        "C Cess": r"C *Cess *([^\n]*)",
        "D Interest": r"D *Interest *([^\n]*)",
        "E Penalty": r"E *Penalty *([^\n]*)",
        "F Fee under section 234E": r"F *Fee under section 234E*([^\n]*)",
        "Total (A+B+C+D+E+F)": r"Total \(A\+B\+C\+D\+E\+F\) *([^\n]*)",
        "Total (In Words)": r"Total \(In Words\) *([^\n]*)"
    }
    extracted_data = {}
    for field, pattern in field_patterns.items():
        match = re.search(pattern, text)
        if match:
            extracted_data[field] = match.group(1).strip()
    return extracted_data

def handler(request: Request):
    try:
        app = zcatalyst_sdk.initialize()
        logger = logging.getLogger()

        # Log request details
        logger.info(f"Request path: {request.path}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request files: {request.files}")
        logger.info(f"Request form: {request.form}")

        if request.method == "POST":
            if 'data' not in request.files:
                response = make_response(jsonify({"Error": "Invalid Request - 'data' missing"}), 400)
                return response

            file_data_list = request.files.getlist('data')
            temp_dir = tempfile.gettempdir()
            all_extracted_data = []

            for file_data in file_data_list:
                file_name = file_data.filename
                file_path = os.path.join(temp_dir, file_name)
                file_data.save(file_path)

                # Try to extract text directly from the file (assuming it's a PDF)
                extracted_text = extract_text_from_pdf(file_path)

                if not extracted_text:  # If no text extracted, assume it's non-readable and use OCR
                    zia = app.zia()
                    with open(file_path, 'rb') as img:
                        try:
                            raw_response = zia.extract_optical_characters(img, {'language': 'eng', 'modelType': 'OCR'})
                            if isinstance(raw_response, dict):
                                extracted_text = raw_response.get('text', '')
                            else:
                                extracted_text = raw_response.json().get('text', '')
                        except Exception as zia_err:
                            logger.error(f"Error calling Zia OCR API: {zia_err}")
                            return make_response(jsonify({"status": "Internal Server Error", "message": str(zia_err)}), 500)
                    readable = False
                else:
                    readable = True

                # Process the extracted text based on the path
                if request.path == "/pfocr":
                    extracted_data = extract_pf_fields(extracted_text, readable)
                elif request.path == "/esiocr":
                    extracted_data = extract_esi_fields(extracted_text)
                elif request.path == "/tds":
                    extracted_data = extract_tds_fields(extracted_text)
                else:
                    response = make_response(jsonify({"Error": "Invalid Request - Wrong path"}), 404)
                    return response

                all_extracted_data.append(extracted_data)

            # Convert extracted data to a DataFrame
            df = pd.DataFrame(all_extracted_data)
            print(all_extracted_data)

            # Create a BytesIO buffer to hold the Excel file
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')

            output.seek(0)

            return send_file(output, as_attachment=True, download_name='extracted_data.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        else:
            response = make_response(jsonify({"Error": "Invalid Request - Wrong method"}), 404)
            return response

    except Exception as err:
        logger.error(f"Exception in python function: {err}")
        response = make_response(jsonify({"status": "Internal Server Error", "message": str(err)}), 500)
        return response
