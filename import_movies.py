#!/usr/bin/env python3
"""
Script untuk mengisi database movies.db dari file CSV IMDb Top 1000
"""

import sqlite3
import csv
import sys
from pathlib import Path


def create_database(db_path):
    """Membuat database dan tabel movies jika belum ada"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Membuat tabel movies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poster_link TEXT,
            title TEXT NOT NULL,
            released_year INTEGER,
            certificate TEXT,
            runtime INTEGER,
            genre TEXT,
            imdb_rating REAL,
            overview TEXT,
            meta_score REAL,
            director TEXT,
            star1 TEXT,
            star2 TEXT,
            star3 TEXT,
            star4 TEXT,
            no_of_votes INTEGER,
            gross REAL
        )
    ''')
    
    conn.commit()
    return conn


def clean_value(value, data_type='string'):
    """Membersihkan nilai dari CSV"""
    if value == '' or value is None:
        return None
    
    value = value.strip()
    
    if data_type == 'integer':
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    elif data_type == 'float':
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    else:
        return value


def import_csv_to_db(csv_path, db_path):
    """Import data dari CSV ke database"""
    # Membuat atau membuka database
    conn = create_database(db_path)
    cursor = conn.cursor()
    
    # Menghapus data lama jika ada
    cursor.execute('DELETE FROM movies')
    print("Data lama telah dihapus.")
    
    # Membaca dan memasukkan data dari CSV
    imported_count = 0
    error_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            try:
                cursor.execute('''
                    INSERT INTO movies (
                        poster_link, title, released_year, certificate,
                        runtime, genre, imdb_rating, overview, meta_score,
                        director, star1, star2, star3, star4,
                        no_of_votes, gross
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    clean_value(row['Poster_Link']),
                    clean_value(row['Series_Title']),
                    clean_value(row['Released_Year'], 'integer'),
                    clean_value(row['Certificate']),
                    clean_value(row['Runtime'], 'integer'),
                    clean_value(row['Genre']),
                    clean_value(row['IMDB_Rating'], 'float'),
                    clean_value(row['Overview']),
                    clean_value(row['Meta_score'], 'float'),
                    clean_value(row['Director']),
                    clean_value(row['Star1']),
                    clean_value(row['Star2']),
                    clean_value(row['Star3']),
                    clean_value(row['Star4']),
                    clean_value(row['No_of_Votes'], 'integer'),
                    clean_value(row['Gross'], 'float')
                ))
                imported_count += 1
                
                # Progress indicator
                if imported_count % 100 == 0:
                    print(f"Imported {imported_count} movies...")
                    
            except Exception as e:
                error_count += 1
                print(f"Error importing movie '{row.get('Series_Title', 'Unknown')}': {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"Import selesai!")
    print(f"Total film berhasil diimport: {imported_count}")
    print(f"Total error: {error_count}")
    print(f"{'='*50}")


def show_sample_data(db_path, limit=5):
    """Menampilkan beberapa data contoh dari database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(f'SELECT title, released_year, imdb_rating, director FROM movies LIMIT {limit}')
    rows = cursor.fetchall()
    
    print(f"\n{'='*50}")
    print(f"Sample data dari database (top {limit}):")
    print(f"{'='*50}")
    for row in rows:
        print(f"Title: {row[0]}")
        print(f"Year: {row[1]}, Rating: {row[2]}, Director: {row[3]}")
        print("-" * 50)
    
    # Menampilkan statistik
    cursor.execute('SELECT COUNT(*) FROM movies')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT AVG(imdb_rating) FROM movies WHERE imdb_rating IS NOT NULL')
    avg_rating = cursor.fetchone()[0]
    
    print(f"\nStatistik:")
    print(f"Total film di database: {total}")
    print(f"Rata-rata IMDb rating: {avg_rating:.2f}")
    print(f"{'='*50}\n")
    
    conn.close()


def main():
    # Path file
    csv_path = '/mnt/user-data/uploads/imdb_top_1000_cleaned.csv'
    db_path = '/home/claude/movies.db'
    
    # Cek apakah file CSV ada
    if not Path(csv_path).exists():
        print(f"Error: File CSV tidak ditemukan di {csv_path}")
        sys.exit(1)
    
    print(f"Memulai import dari {csv_path} ke {db_path}...")
    print(f"{'='*50}\n")
    
    # Import data
    import_csv_to_db(csv_path, db_path)
    
    # Tampilkan sample data
    show_sample_data(db_path)
    
    print(f"Database berhasil dibuat di: {db_path}")


if __name__ == '__main__':
    main()
