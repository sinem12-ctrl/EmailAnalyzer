# Email Data Downloader & Analyzer

A Flask-based web application to fetch, clean, and analyze email data from your account.

The app allows exporting raw, cleaned, spam, or starred emails in CSV or JSON format and generating charts for daily question and answer counts.
---

## Features

- Fetch **raw emails**, **cleaned emails**, **spam emails**, and **starred emails** from your account.  
- Export data in **CSV** or **JSON** format.  
- Automatically generate **charts** showing daily email statistics.  
- Handles date ranges or single dates.  
- Unique file naming to avoid overwriting existing files.  
- Flash messages to notify success or errors.
- 
---

## Requirements 

- Python 3.9+
- Flask
- pandas
- matplotlib
- numpy

Install dependencies via pip:  
Gerekli kütüphaneleri yüklemek için:

```bash
pip install flask pandas matplotlib numpy
```
## Folder Structure

```bash
project/
│
├─ app.py                 # Main Flask application / Ana Flask uygulaması
├─ templates/
│  ├─ index.html          # Main page / Ana sayfa
│  └─ ...
├─ data_processors/       # Custom modules for processing emails / E-postaları işleyen özel modüller
│  ├─ raw_data.py
│  ├─ cleaned_content.py
│  └─ spam_cleaning.py
└─ README.md
```

## Usage 
1. Run the Flask app:

```bash
python app.py
```
2. Open your browser and go to http://127.0.0.1:5000.
3. Fill in your email, password, select data type(s), export format(s), and date options.
4. Optionally, check "Save chart" to generate a PNG chart of daily email statistics.
5. Click Submit to download data and view charts in your Downloads folder.

## Notes

* The app generates unique filenames if a file with the same name already exists.
* Charts include daily question and answer counts with an overlay of the answer ratio.
* Make sure your email account allows access via this app (IMAP/SMTP or API).

## License

This project is released under the MIT License.
