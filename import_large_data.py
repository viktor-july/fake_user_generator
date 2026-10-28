import asyncio
import csv
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def main():
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    print("Connected to database")

    # -------------------------------------------------
    # 1. Clear old name data for en_US and de_DE
    # -------------------------------------------------
    await conn.execute("DELETE FROM first_names WHERE locale IN ('en_US', 'de_DE')")
    await conn.execute("DELETE FROM last_names  WHERE locale IN ('en_US', 'de_DE')")
    print("Cleared old first_names and last_names")

    # -------------------------------------------------
    # 2. Import names.csv
    # -------------------------------------------------
    with open("names.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        first_names = []
        last_names = []

        for row in reader:
            # English
            if row["en_name"].strip():
                first_names.append(("en_US", row["en_name"].strip(), None))
            if row["en_surname"].strip():
                last_names.append(("en_US", row["en_surname"].strip()))

            # German
            if row["de_name"].strip():
                first_names.append(("de_DE", row["de_name"].strip(), None))
            if row["de_surname"].strip():
                last_names.append(("de_DE", row["de_surname"].strip()))

    await conn.executemany(
        "INSERT INTO first_names (locale, name, gender) VALUES ($1, $2, $3)",
        first_names
    )
    await conn.executemany(
        "INSERT INTO last_names (locale, name) VALUES ($1, $2)",
        last_names
    )
    print(f"Imported {len(first_names)} first names and {len(last_names)} last names")

    # -------------------------------------------------
    # 3. Clear + import streets
    # -------------------------------------------------
    await conn.execute("DELETE FROM street_names WHERE locale IN ('en_US', 'de_DE')")

    with open("US_DE_streets_500.csv", encoding="utf-8-sig") as f:  # utf-8-sig strips the BOM
        reader = csv.DictReader(f)
        streets = []

        for row in reader:
            us = (row.get("US_street") or "").strip()
            de = (row.get("DE_street") or "").strip()
            if us:
                streets.append(("en_US", us))
            if de:
                streets.append(("de_DE", de))

    await conn.executemany(
        "INSERT INTO street_names (locale, name) VALUES ($1, $2)",
        streets
    )
    print(f"Imported {len(streets)} street names")

    # -------------------------------------------------
    # 4. Quick verification
    # -------------------------------------------------
    counts = await conn.fetch("""
        SELECT 'first_names' AS t, locale, COUNT(*) 
        FROM first_names GROUP BY locale
        UNION ALL
        SELECT 'last_names', locale, COUNT(*) 
        FROM last_names GROUP BY locale
        UNION ALL
        SELECT 'street_names', locale, COUNT(*) 
        FROM street_names GROUP BY locale
        ORDER BY 1, 2
    """)

    print("\nCurrent counts:")
    for row in counts:
        print(f"  {row['t']:15} {row['locale']}: {row['count']}")

    await conn.close()
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())