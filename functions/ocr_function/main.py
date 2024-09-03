from flask import Flask, request
from EsiOcr import handler # Import the handler function from OCR.py
# from PfOcr import handler

app = Flask(__name__)

@app.route('/pfocr', methods=['POST'])
def ocr_endpoint():
    return handler(request)


# @app.route('/pfocr', methods = ['POST'])
# def pfocr_endpoint():
#     return handler(request)
app.config['TIMEOUT'] = 120

if __name__ == "__main__":
    app.run(debug=True)
