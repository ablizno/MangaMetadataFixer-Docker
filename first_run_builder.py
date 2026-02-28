import os
import time
import zipfile
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

# Detect if running without a TTY (e.g. Docker)
IN_DOCKER = not os.isatty(1)

def create_comicinfo_xml(series_name, title_name):
    """Creates an XML string for ComicInfo.xml."""
    import xml.etree.ElementTree as ET
    comic_info = ET.Element("ComicInfo")
    title = ET.SubElement(comic_info, "Title")
    title.text = title_name
    series = ET.SubElement(comic_info, "Series")
    series.text = series_name
    return ET.tostring(comic_info, encoding="utf-8", method="xml").decode("utf-8")

def initialize_database(db_path):
    """Initializes the SQLite database to track processed files."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            filepath TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def cleanup_sql_journal(data_dir):
    """Deletes SQLite journal files at the beginning to prevent locking issues."""
    for file in os.listdir(data_dir):
        if file.endswith(".db-journal"):
            os.remove(os.path.join(data_dir, file))

def is_file_processed(db_path, filepath):
    """Checks if a file has already been processed."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_files WHERE filepath = ?", (filepath,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_files_as_processed(db_path, filepaths):
    """Marks a batch of files as processed in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executemany("INSERT OR IGNORE INTO processed_files (filepath) VALUES (?)", [(fp,) for fp in filepaths])
    conn.commit()
    conn.close()

def process_cbz_file(filepath, log_file, db_path, processed_files_batch):
    """Checks if ComicInfo.xml exists in the .cbz file and creates one if not."""
    if is_file_processed(db_path, filepath):
        return

    with zipfile.ZipFile(filepath, 'a') as cbz:
        if "ComicInfo.xml" not in cbz.namelist():
            series_name = os.path.basename(os.path.dirname(filepath))
            title_name, _ = os.path.splitext(os.path.basename(filepath))
            comicinfo_content = create_comicinfo_xml(series_name, title_name)
            cbz.writestr("ComicInfo.xml", comicinfo_content)
            log_entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Added ComicInfo.xml to {filepath}\n"
            with open(log_file, 'a') as log:
                log.write(log_entry)

    processed_files_batch.append(filepath)

def check_log_size(log_file):
    """Checks the size of the log file and deletes it if it exceeds 50MB."""
    if os.path.exists(log_file):
        if os.path.getsize(log_file) > 50 * 1024 * 1024:
            print(f"Log file exceeds 50MB. Deleting {log_file}...")
            os.remove(log_file)

def clear_console():
    """Clears the console screen, skipped in Docker."""
    if not IN_DOCKER:
        os.system('cls' if os.name == 'nt' else 'clear')

_last_progress_pct = -1

def print_progress_bar(current, total, bar_length=40):
    """Prints progress. In Docker, only logs at each 10% milestone."""
    global _last_progress_pct
    percent = (current / total) * 100
    if IN_DOCKER:
        pct_int = int(percent) // 10 * 10
        if pct_int != _last_progress_pct:
            print(f"Progress: {pct_int}% ({current}/{total})", flush=True)
            _last_progress_pct = pct_int
    else:
        filled_length = int(bar_length * current // total)
        bar = '=' * filled_length + '-' * (bar_length - filled_length)
        print(f"\r[{bar}] {percent:.2f}% ({current}/{total})", end="")

def process_files(directory, log_file, db_path, total_files, batch_size=500):
    """Processes .cbz files in the directory with a progress bar."""
    processed_files_batch = []
    processed_count = 0

    with ThreadPoolExecutor() as executor:
        futures = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".cbz"):
                    filepath = os.path.join(root, file)
                    if is_file_processed(db_path, filepath):
                        continue
                    future = executor.submit(process_cbz_file, filepath, log_file, db_path, processed_files_batch)
                    futures.append(future)

        for future in as_completed(futures):
            processed_count += 1
            if processed_count % 10 == 0:
                print_progress_bar(processed_count, total_files)
            if processed_count % batch_size == 0:
                mark_files_as_processed(db_path, processed_files_batch)
                processed_files_batch.clear()

        if processed_files_batch:
            mark_files_as_processed(db_path, processed_files_batch)

def get_data_directory():
    """Reads the data directory from the DATA_DIR environment variable."""
    data_directory = os.environ.get("DATA_DIR", "/data").strip()
    if not os.path.isdir(data_directory):
        raise FileNotFoundError(
            f"DATA_DIR does not exist or is not mounted: {data_directory}"
        )
    return data_directory

def get_manga_directory():
    """Reads the manga directory from the MANGA_DIR environment variable."""
    manga_directory = os.environ.get("MANGA_DIR", "/manga").strip()
    if not os.path.isdir(manga_directory):
        raise FileNotFoundError(
            f"MANGA_DIR does not exist or is not mounted: {manga_directory}"
        )
    return manga_directory

def main():
    """Main function to process .cbz files in a directory tree, running once."""
    manga_directory = get_manga_directory()
    data_dir = get_data_directory()

    cleanup_sql_journal(data_dir)

    clear_console()
    print("Manga Metadata Fixer by HDShock")
    print(f"Manga directory: {manga_directory}")

    log_file = os.path.join(data_dir, "process_log.txt")
    db_path = os.path.join(data_dir, "processed_files.db")

    initialize_database(db_path)
    check_log_size(log_file)

    print(f"Log file location: {log_file}")

    total_files = sum(
        len([f for f in files if f.endswith('.cbz')])
        for _, _, files in os.walk(manga_directory)
    )
    print(f"Total files to process: {total_files}", flush=True)

    process_files(manga_directory, log_file, db_path, total_files)

    print("First Scan complete!", flush=True)

if __name__ == "__main__":
    main()
