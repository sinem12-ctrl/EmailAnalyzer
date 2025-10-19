from flask import Flask, render_template, request, redirect, flash
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Custom data processing modules
from data_processors.raw_data import fetch_emails, fetch_starred_emails
from data_processors.cleaned_content import generate_chained_emails
from data_processors.spam_cleaning import process_spam_emails

# Generates a unique file name if a file with the same name exists
def unique_file_name(file_path: Path) -> Path:
    if not file_path.exists():
        return file_path
    stem, suffix, parent = file_path.stem, file_path.suffix, file_path.parent
    i = 2
    while True:
        new_name = f"{stem}_{i}{suffix}"
        new_file = parent / new_name
        if not new_file.exists():
            return new_file
        i += 1

# Creates a file name based on data type, today's date, and date filter
def create_file_name(data_type, today_dt, date_type, start_date, end_date):
    def format_date(dt):
        return dt.strftime("%d%m%Y") if dt else ""
    today_str = format_date(today_dt)
    start_str = format_date(start_date)
    end_str = format_date(end_date)

    if data_type == "spam":
        prefix = "spam_email"
    else:
        prefix = f"{data_type}_data"

    if date_type == "range":
        return f"{prefix}_{today_str}_{start_str}_{end_str}_range"
    elif date_type == "single":
        return f"{prefix}_{today_str}_{start_str}_{today_str}_range"
    else:
        return f"{prefix}_{today_str}"

# Generates a chart and saves it as PNG
def generate_and_save_chart(data_list, data_type, date_str, raw_data=None):
    records = []
    for i, entry in enumerate(data_list):
        entry_date_str = entry.get("date")
        if not entry_date_str and raw_data and i < len(raw_data):
            entry_date_str = raw_data[i].get("date")
        entry_date = pd.to_datetime(entry_date_str).date() if entry_date_str else None
        answered = entry.get("full_answer") and entry.get("full_answer").strip() != ""
        if entry_date:
            records.append({"Date": entry_date, "Answered": answered})

    if not records:
        print(f"⚠️ No chart generated for {data_type}: no data.")
        return False

    df = pd.DataFrame(records)
    summary = df.groupby("Date").agg(
        Question_Count=('Answered', 'count'),
        Answer_Count=('Answered', 'sum')
    ).reset_index()

    summary = summary[summary["Question_Count"] != 0]
    if summary.empty:
        print(f"⚠️ No chart generated for {data_type}: empty summary.")
        return False

    x = np.arange(len(summary))
    width = 0.35
    plt.figure(figsize=(12, 7))
    plt.bar(x - width/2, summary["Question_Count"], width, label="Question Count", color='royalblue')
    plt.bar(x + width/2, summary["Answer_Count"], width, label="Answer Count", color='seagreen')
    ratio = summary["Answer_Count"] / summary["Question_Count"]
    plt.plot(x, ratio * summary["Question_Count"].max(), color='orange', marker='o', label='Answer Ratio')
    plt.xticks(x, summary["Date"].astype(str), rotation=45)
    plt.title("Daily Question and Answer Count")
    plt.legend()

    for i in x:
        plt.text(i - width/2, summary["Question_Count"].iloc[i] + 0.1, str(summary["Question_Count"].iloc[i]), ha='center')
        plt.text(i + width/2, summary["Answer_Count"].iloc[i] + 0.1, str(summary["Answer_Count"].iloc[i]), ha='center')
    plt.tight_layout()

    downloads = Path.home() / "Downloads"
    downloads.mkdir(exist_ok=True)
    file = unique_file_name(downloads / f"chart_{data_type}_{date_str}.png")
    try:
        plt.savefig(file, dpi=300)
        print(f"✅ Chart saved: {file}")
    except Exception as e:
        print("❌ Chart error:", e)
        plt.close()
        return False
    plt.close()
    return True


app = Flask(__name__)
app.secret_key = "secret_key"

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
    except:
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        data_types = request.form.getlist("data_type")
        formats = request.form.getlist("format")
        date_type = request.form.get("date_type")
        start_date_raw = request.form.get("single_date") if date_type == "single" else request.form.get("range_start")
        end_date_raw = None if date_type == "single" else request.form.get("range_end")
        save_chart = request.form.get("save_chart") == "yes"

        if not email or not password or not data_types or not formats:
            flash("Please fill all required fields!", "danger")
            return redirect("/")

        today = datetime.now()
        start_date = parse_date(start_date_raw)
        end_date = parse_date(end_date_raw)
        downloads = Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)

        try:
            for data_type in data_types:
                file_name = create_file_name(data_type, today, date_type, start_date, end_date)

                if data_type == "raw":
                    raw_emails = fetch_emails(email, password, start_date, end_date)
                    if not raw_emails:
                        flash("❗ No raw data found, file not created.", "warning")
                        continue

                    if "json" in formats:
                        file_json = unique_file_name(downloads / f"{file_name}.json")
                        with open(file_json, "w", encoding="utf-8") as f:
                            json.dump(raw_emails, f, ensure_ascii=False, indent=2)

                    if "csv" in formats:
                        file_csv = unique_file_name(downloads / f"{file_name}.csv")
                        pd.DataFrame(raw_emails).to_csv(file_csv, index=False)

                    if save_chart:
                        generate_and_save_chart(raw_emails, "raw", today.strftime("%d%m%Y"))
                    flash("✅ Raw emails saved successfully.", "success")

                elif data_type == "cleaned":
                    raw_emails = fetch_emails(email, password, start_date, end_date)
                    cleaned = generate_chained_emails(raw_emails)
                    if not cleaned:
                        flash("❗ No cleaned data found, file not created.", "warning")
                        continue

                    if "json" in formats:
                        file_json = unique_file_name(downloads / f"{file_name}.json")
                        with open(file_json, "w", encoding="utf-8") as f:
                            json.dump(cleaned, f, ensure_ascii=False, indent=2)

                    if "csv" in formats:
                        file_csv = unique_file_name(downloads / f"{file_name}.csv")
                        pd.DataFrame(cleaned).to_csv(file_csv, index=False)

                    if save_chart:
                        generate_and_save_chart(cleaned, "cleaned", today.strftime("%d%m%Y"), raw_data=raw_emails)
                    flash("✅ Cleaned emails saved successfully.", "success")

                elif data_type == "spam":
                    spam_emails = process_spam_emails(email, password, start_date, end_date)
                    if not spam_emails:
                        flash("❗ No spam data found, file not created.", "warning")
                        continue

                    if "json" in formats:
                        file_json = unique_file_name(downloads / f"{file_name}.json")
                        with open(file_json, "w", encoding="utf-8") as f:
                            json.dump(spam_emails, f, ensure_ascii=False, indent=2)

                    if "csv" in formats:
                        file_csv = unique_file_name(downloads / f"{file_name}.csv")
                        pd.DataFrame(spam_emails).to_csv(file_csv, index=False)

                    if save_chart:
                        generate_and_save_chart(spam_emails, "spam", today.strftime("%d%m%Y"))
                    flash("✅ Spam emails saved successfully.", "success")

                elif data_type == "starred":
                    starred = fetch_starred_emails(email, password, start_date, end_date)
                    if not starred:
                        flash("❗ No starred emails found, file not created.", "warning")
                        continue

                    if "json" in formats:
                        file_json = unique_file_name(downloads / f"{file_name}.json")
                        with open(file_json, "w", encoding="utf-8") as f:
                            json.dump(starred, f, ensure_ascii=False, indent=2)

                    if "csv" in formats:
                        file_csv = unique_file_name(downloads / f"{file_name}.csv")
                        pd.DataFrame(starred).to_csv(file_csv, index=False)

                    if save_chart:
                        generate_and_save_chart(starred, "starred", today.strftime("%d%m%Y"))
                    flash("✅ Starred emails saved successfully.", "success")

        except Exception as e:
            flash(f"❌ An error occurred: {e}", "danger")

        return redirect("/")

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
