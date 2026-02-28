import os
import time
import zipfile
import threading
import sqlite3

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

def is_file_processed(db_path, filepath):
    """Checks if a file has already been processed."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_files WHERE filepath = ?", (filepath,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_file_as_processed(db_path, filepath):
    """Marks a file as processed in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO processed_files (filepath) VALUES (?)", (filepath,))
    conn.commit()
    conn.close()

def process_cbz_file(filepath, log_file, db_path):
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
            print(log_entry.strip(), flush=True)
            with open(log_file, 'a') as log:
                log.write(log_entry)
        # No log output for files that already have ComicInfo.xml

    mark_file_as_processed(db_path, filepath)

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

def loading_animation(stop_flag):
    """Displays a loading animation (skipped in Docker)."""
    if IN_DOCKER:
        return
    animation = ["", ".", "..", "..."]
    while not stop_flag.is_set():
        for frame in animation:
            if stop_flag.is_set():
                break
            clear_console()
            print("Manga Metadata Fixer by HDShock")
            print("\nScanning New Manga" + frame)
            print("\n\nProcess Queue:\n\n")
            time.sleep(0.5)

def process_files(directory, log_file, db_path):
    """Processes .cbz files in the directory."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".cbz"):
                filepath = os.path.join(root, file)
                process_cbz_file(filepath, log_file, db_path)

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
    """Main function to process .cbz files in a directory tree, running every 5 minutes."""
    manga_directory = get_manga_directory()
    data_dir = get_data_directory()

    while True:
        log_file = os.path.join(data_dir, "process_log.txt")
        db_path = os.path.join(data_dir, "processed_files.db")

        initialize_database(db_path)
        check_log_size(log_file)

        print("Manga Metadata Fixer by HDShock - Scanning...", flush=True)

        stop_flag = threading.Event()
        animation_thread = threading.Thread(target=loading_animation, args=(stop_flag,))
        animation_thread.start()

        try:
            process_files(manga_directory, log_file, db_path)
        finally:
            stop_flag.set()
            animation_thread.join()

        print(f"Scan complete. Next run in 5 minutes. Log: {log_file}", flush=True)

        time.sleep(300)

if __name__ == "__main__":
    main()
