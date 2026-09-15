import os
import json
import logging
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

# Setup logging
logger = logging.getLogger("database")
logging.basicConfig(level=logging.INFO)

class DatabaseService:
    def __init__(self):
        self.client = None
        self.db = None
    #initialize the database connection
    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(settings.MONGODB_URL)
            self.db = self.client[settings.DATABASE_NAME]
            logger.info(f"Connected to MongoDB at {settings.MONGODB_URL}")
            # Run auto-seed
            await self.seed_if_empty()
            await self.ensure_indexes()
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise e

    async def close(self):
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")

    async def seed_if_empty(self):
        # 1. Seed Users
        user_count = await self.db.users.count_documents({})
        if user_count == 0:
            logger.info("Seeding default admin user...")
            # Use bcrypt directly for hashing
            salt = bcrypt.gensalt()
            hashed_pw = bcrypt.hashpw(settings.ADMIN_PASSWORD.encode('utf-8'), salt).decode('utf-8')
            await self.db.users.insert_one({
                "username": "admin",
                "hashed_password": hashed_pw,
                "full_name": "Administrador SLEP",
                "role": "admin"
            })
            logger.info("Admin user seeded successfully with credentials from ADMIN_PASSWORD env var.")

        # 2. Seed Establishments and split metrics/counterparts
        est_count = await self.db.establishments.count_documents({})
        if est_count == 0:
            logger.info("Database is empty. Starting seeding from establishments.json...")
            json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "establishments.json"))
            
            if not os.path.exists(json_path):
                logger.error(f"Seeding source file not found at {json_path}!")
                return

            with open(json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            establishments_to_insert = []
            counterparts_to_insert = []
            metrics_to_insert = []

            for item in raw_data:
                rbd = item.get("rbd")
                if not rbd:
                    continue

                # --- 1. Extract Metrics ---
                metrics_raw = item.get("metrics", {})
                
                # We create metric records for multiple years (2022 to 2026)
                # For 2026 (current latest year)
                metrics_to_insert.append({
                    "rbd": rbd,
                    "year": 2026,
                    "enrollment": metrics_raw.get("matricula_2026", 0),
                    "attendance_avg": metrics_raw.get("asistencia_2025", ""),  # fallback or latest
                    "ive_basica": metrics_raw.get("ive_basica", 0.0),
                    "ive_media": metrics_raw.get("ive_media", 0.0),
                    "num_teachers": metrics_raw.get("num_docentes", 0),
                    "num_assistants": metrics_raw.get("num_asistentes", 0),
                    "promoted": metrics_raw.get("promovidos", 0),
                    "failed": metrics_raw.get("reprobados", 0),
                    "transferred": metrics_raw.get("trasladados", 0),
                    "dropouts": metrics_raw.get("desertores", 0),
                    "desempeno_basica": metrics_raw.get("desempeno_basica_2019", ""),
                    "desempeno_media": metrics_raw.get("desempeno_media_2019", ""),
                    "grade_avg": metrics_raw.get("promedio_general", 0.0),
                    "ptje_nem": metrics_raw.get("ptje_nem", 0.0),
                    "ptje_ranking": metrics_raw.get("ptje_ranking", 0.0),
                    "score_lectura": metrics_raw.get("lectura", 0.0),
                    "score_matematica1": metrics_raw.get("matematica1", 0.0),
                    "score_matematica2": metrics_raw.get("matematica2", 0.0),
                    "score_historia": metrics_raw.get("historia_sociales", 0.0),
                    "score_ciencia": metrics_raw.get("ciencia", 0.0),
                    "total_rendidores": metrics_raw.get("total_rendidores", 0),
                    "tasa_promocion": metrics_raw.get("tasa_promocion", 0.0),
                    "tasa_reprobacion": metrics_raw.get("tasa_reprobacion", 0.0),
                    "tasa_desercion": metrics_raw.get("tasa_desercion", 0.0),
                    "tasa_retencion": metrics_raw.get("tasa_retencion", 0.0)
                })
                # For historical enrollment years
                for year, key in [(2025, "matricula_2025"), (2024, "matricula_2024"), (2023, "matricula_2023"), (2022, "matricula_2022")]:
                    val = metrics_raw.get(key, 0)
                    # We only insert if we have enrollment or if it's 2025 (which has attendance)
                    if val > 0 or year == 2025:
                        metrics_to_insert.append({
                            "rbd": rbd,
                            "year": year,
                            "enrollment": val,
                            "attendance_avg": metrics_raw.get("asistencia_2025", "") if year == 2025 else "",
                            "ive_basica": 0.0,
                            "ive_media": 0.0,
                            "num_teachers": 0,
                            "num_assistants": 0
                        })

                # --- 2. Extract Counterparts (Strategy Pattern / Typed Subdocuments) ---
                cp_raw = item.get("counterparts", {})

                # Roles fijos sin variación por año
                role_mappings = {
                    "personal_procesos_adm": ("PERSONAL_PROCESOS_ADM", "SLEP"),
                    "gestor_infraestructura": ("GESTOR_INFRAESTRUCTURA", "SLEP"),
                    "comprador": ("COMPRADOR", "SLEP"),
                    "rrhh": ("RRHH", "SLEP"),
                    "infraestructura": ("INFRAESTRUCTURA", "SLEP"),
                    "compras": ("COMPRAS", "SLEP"),
                    "ti": ("TI", "SLEP"),
                    "profesional_ame_nt": ("PROFESIONAL_AME_NT", "SLEP"),
                    "profesional_inclusion": ("PROFESIONAL_INCLUSION", "SLEP"),
                    "utp_jefe": ("UTP_JEFE", "ESTABLECIMIENTO"),
                    "pie_encargado": ("PIE_ENCARGADO", "ESTABLECIMIENTO"),
                    "convivencia_encargado": ("CONVIVENCIA_ESCOLAR", "ESTABLECIMIENTO"),
                    "inspector_general": ("INSPECTOR_GENERAL", "ESTABLECIMIENTO"),
                    "sige_encargado": ("SIGE_ENCARGADO", "ESTABLECIMIENTO")
                }

                # Roles con posible sufijo de año en los datos fuente (ej: territorial_2026).
                # Se resuelve dinámicamente para no depender del año en el código.
                # Detecta cualquier clave que empiece con el prefijo del rol.
                year_variant_roles = {
                    "territorial": ("TERRITORIAL", "SLEP"),
                }

                seen_roles = set()

                # Procesar roles fijos
                for field_name, (role, origin) in role_mappings.items():
                    name_val = cp_raw.get(field_name, "")
                    if name_val and name_val != "-":
                        role_key = (role, origin)
                        if role_key in seen_roles:
                            continue
                        seen_roles.add(role_key)
                        counterparts_to_insert.append({
                            "rbd": rbd,
                            "role": role,
                            "origin": origin,
                            "name": name_val,
                            "email": cp_raw.get(f"{field_name}_email", ""),
                            "phone": cp_raw.get(f"{field_name}_phone", "")
                        })

                # Procesar roles con variantes de año: busca el primero disponible
                for prefix, (role, origin) in year_variant_roles.items():
                    role_key = (role, origin)
                    if role_key in seen_roles:
                        continue
                    # Ordenar claves para preferir la más reciente (mayor año)
                    candidates = sorted(
                        [k for k in cp_raw if k == prefix or k.startswith(f"{prefix}_")],
                        reverse=True
                    )
                    for field_name in candidates:
                        name_val = cp_raw.get(field_name, "")
                        if name_val and name_val != "-":
                            seen_roles.add(role_key)
                            counterparts_to_insert.append({
                                "rbd": rbd,
                                "role": role,
                                "origin": origin,
                                "name": name_val,
                                "email": cp_raw.get(f"{field_name}_email", ""),
                                "phone": cp_raw.get(f"{field_name}_phone", "")
                            })
                            break

                # Also insert the director as a counterpart from general_info / main data
                director_name = item.get("general_info", {}).get("director", "")
                if director_name:
                    counterparts_to_insert.append({
                        "rbd": rbd,
                        "role": "DIRECTOR",
                        "origin": "ESTABLECIMIENTO",
                        "name": director_name,
                        "email": item.get("general_info", {}).get("director_email", ""),
                        "phone": item.get("general_info", {}).get("director_phone", "")
                    })

                # --- 3. Build base establishment document ---
                # Exclude metrics and counterparts from the main establishment document
                est_doc = {
                    "rbd": rbd,
                    "rbd_dv": item.get("rbd_dv", ""),
                    "rbd_full": item.get("rbd_full", f"{rbd}"),
                    "name": item.get("name", ""),
                    "comuna": item.get("comuna", ""),
                    "area_type": item.get("area_type", ""),
                    "address": item.get("address", ""),
                    "general_info": item.get("general_info", {}),
                    "connectivity": item.get("connectivity", {}),
                    "printers": item.get("printers", {}),
                    "licenses": item.get("licenses", [])
                }
                establishments_to_insert.append(est_doc)

            # Insert all documents into collections
            if establishments_to_insert:
                await self.db.establishments.insert_many(establishments_to_insert)
                logger.info(f"Inserted {len(establishments_to_insert)} establishments.")
            if counterparts_to_insert:
                await self.db.counterparts.insert_many(counterparts_to_insert)
                logger.info(f"Inserted {len(counterparts_to_insert)} counterparts.")
            if metrics_to_insert:
                await self.db.metrics.insert_many(metrics_to_insert)
                logger.info(f"Inserted {len(metrics_to_insert)} metrics.")

            logger.info("Database seeding completed successfully.")

    async def ensure_indexes(self):
        """BE-01: Crea índices optimizados en todas las colecciones.
        Idempotente: usar create_index() con motor/pymongo es seguro si el índice ya existe."""
        logger.info("Ensuring MongoDB indexes...")

        # Establishments
        await self.db.establishments.create_index("rbd", unique=True, background=True)
        await self.db.establishments.create_index([("comuna", 1), ("area_type", 1)], background=True)
        await self.db.establishments.create_index("name", background=True)
        await self.db.establishments.create_index("general_info.category", background=True)

        # Counterparts
        await self.db.counterparts.create_index("rbd", background=True)
        await self.db.counterparts.create_index([("rbd", 1), ("role", 1)], background=True)

        # Metrics
        await self.db.metrics.create_index([("rbd", 1), ("year", -1)], unique=True, background=True)
        await self.db.metrics.create_index("year", background=True)

        logger.info("MongoDB indexes ensured.")

db_service = DatabaseService()
