import requests
import mysql.connector
import time

# Configuración de la API
API_KEY = "70c102fffa4eee4b0b2d1700b3a279ff"
BASE_URL = "https://api.elsevier.com/content/search/scopus"

# Configuración de la base de datos MySQL
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "articleservice"
}

# Función para conectar a MySQL
def connect_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Error al conectar a MySQL: {err}")
        return None

# Crear tabla si no existe, con restricción UNIQUE en el título
def create_table():
    conn = connect_db()
    if conn is None:
        return
    cursor = conn.cursor()
    cursor.execute("USE " + DB_CONFIG["database"])
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            authors TEXT,
            publication_date DATE,
            title TEXT UNIQUE,  -- Restringe títulos duplicados
            link TEXT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Verificar si un artículo ya existe en la base de datos
def article_exists(title):
    conn = connect_db()
    if conn is None:
        return False
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles WHERE title = %s", (title,))
    exists = cursor.fetchone()[0] > 0
    cursor.close()
    conn.close()
    return exists

# Guardar un artículo en la base de datos (evitando duplicados)
def save_article(authors, publication_date, title, link):
    if article_exists(title):
        print(f"⚠️ El artículo '{title}' ya está en la base de datos. Saltando...")
        return

    conn = connect_db()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO articles (authors, publication_date, title, link)
            VALUES (%s, %s, %s, %s)
        """, (authors, publication_date, title, link))
        conn.commit()
        print(f"✅ Artículo '{title}' guardado en la base de datos.")
    except mysql.connector.Error as err:
        print(f"⚠️ Error al guardar '{title}': {err}")
    finally:
        cursor.close()
        conn.close()

# Función para obtener artículos de ScienceDirect
def fetch_articles(query="Human Computer Interaction", max_results=500):
    articles_saved = 0
    start_index = 0

    while articles_saved < max_results:
        params = {
            "query": query,
            "apiKey": API_KEY,
            "count": 25,  # Máximo permitido por consulta
            "start": start_index
        }

        headers = {
            "X-ELS-APIKey": API_KEY,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(BASE_URL, params=params, headers=headers)

        if response.status_code != 200:
            print("❌ Error en la solicitud:", response.json())
            break

        data = response.json()
        articles = data.get("search-results", {}).get("entry", [])

        if not articles:
            print("⚠️ No se encontraron más artículos.")
            break

        for article in articles:
            title = article.get("dc:title", "Sin título")
            link = article.get("link", [{}])[0].get("@href", "Sin enlace")
            publication_date = article.get("prism:coverDate", None)
            authors_list = article.get("authors", [])
            authors = ", ".join([author.get("$", "Desconocido") for author in authors_list]) if authors_list else "Desconocido"

            save_article(authors, publication_date, title, link)
            articles_saved += 1

            if articles_saved >= max_results:
                break

        start_index += 25  # Avanzar al siguiente lote
        time.sleep(2)  # Evitar sobrecargar la API

    print(f"✅ Se guardaron {articles_saved} artículos en la base de datos.")

# Ejecutar el script
if __name__ == "__main__":
    create_table()
    fetch_articles()