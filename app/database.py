# Importamos las herramientas necesarias
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# Le decimos a Python que lea el archivo .env
load_dotenv()

# Leemos la URL de conexión que escribimos en .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Creamos el motor de conexión con Supabase
engine = create_engine(DATABASE_URL)

# Creamos la fábrica de sesiones
# Cada vez que la API necesite hablar con la BD abre una sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base es la clase madre de todos nuestros modelos
Base = declarative_base()


# Esta función abre y cierra la sesión automáticamente
# La usaremos en cada endpoint de la API
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
