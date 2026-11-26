import os
import psycopg2
from psycopg2.extras import execute_values

DB_KARO = os.environ.get("DB_KARO")
DB_DELI = os.environ.get("DB_DELI")
DB_LANGKAT = os.environ.get("DB_LANGKAT")
DB_PUSAT = os.environ.get("DB_PUSAT")

KONEKSI_KABUPATEN = {
    "KARO": DB_KARO,
    "DELI SERDANG": DB_DELI,
    "LANGKAT": DB_LANGKAT,
}

if not all(KONEKSI_KABUPATEN.values()) or not DB_PUSAT:
    raise ValueError(
        "Salah satu secret database (DB_KARO, DB_DELI, DB_LANGKAT, DB_PUSAT) kosong."
    )

SQL_BUAT_TABEL_PUSAT = """
CREATE TABLE IF NOT EXISTS petani_pusat (
    kode_petani VARCHAR(20) PRIMARY KEY,
    nama_petani VARCHAR(100) NOT NULL,
    desa VARCHAR(100) NOT NULL,
    komoditas VARCHAR(100) NOT NULL,
    luas_lahan NUMERIC(8,2) NOT NULL,
    wilayah_sumber VARCHAR(50) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

SQL_UPSERT_PUSAT = """
INSERT INTO petani_pusat (
    kode_petani,
    nama_petani,
    desa,
    komoditas,
    luas_lahan,
    wilayah_sumber,
    updated_at
)
VALUES %s
ON CONFLICT (kode_petani)
DO UPDATE SET
    nama_petani = EXCLUDED.nama_petani,
    desa = EXCLUDED.desa,
    komoditas = EXCLUDED.komoditas,
    luas_lahan = EXCLUDED.luas_lahan,
    wilayah_sumber = EXCLUDED.wilayah_sumber,
    updated_at = EXCLUDED.updated_at;
"""


def ambil_data_kabupaten(connection_string, wilayah):
    conn = psycopg2.connect(connection_string, sslmode="require")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    kode_petani,
                    nama_petani,
                    desa,
                    komoditas,
                    luas_lahan,
                    updated_at
                FROM petani;
            """)
            rows = cur.fetchall()
        print(f"{wilayah}: {len(rows)} baris dibaca dari tabel petani")
        return [(wilayah, row) for row in rows]
    finally:
        conn.close()


def main():
    semua_data_pusat = []

    for wilayah, conn_str in KONEKSI_KABUPATEN.items():
        semua_data_pusat.extend(ambil_data_kabupaten(conn_str, wilayah))

    kode_ditemukan = [row[1][0] for row in semua_data_pusat]
    if len(kode_ditemukan) != len(set(kode_ditemukan)):
        raise ValueError("Ada kode_petani duplikat antar database kabupaten.")

    if not semua_data_pusat:
        print("Tidak ada data ditemukan di database kabupaten. Proses dilewati.")
        return

    nilai_pusat = [
        (
            row[0],    # kode_petani
            row[1],    # nama_petani
            row[2],    # desa
            row[3],    # komoditas
            row[4],    # luas_lahan
            wilayah,   # wilayah_sumber
            row[5],    # updated_at
        )
        for wilayah, row in semua_data_pusat
    ]

    conn = psycopg2.connect(DB_PUSAT, sslmode="require")
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_BUAT_TABEL_PUSAT)
            execute_values(cur, SQL_UPSERT_PUSAT, nilai_pusat)
        conn.commit()
        print(f"SINKRONISASI BERHASIL: {len(nilai_pusat)} baris diproses ke petani_pusat.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
