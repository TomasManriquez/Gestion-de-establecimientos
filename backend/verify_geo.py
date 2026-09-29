import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys

async def verify_geo():
    try:
        client = AsyncIOMotorClient('mongodb://localhost:27017')
        db = client['slep_llanquihue']
        col = db.establishments
        
        total = await col.count_documents({})
        with_loc = await col.count_documents({"location": {"$exists": True, "$ne": None}})
        
        print(f"TOTAL_ESTABLISHMENTS: {total}")
        print(f"WITH_LOCATION: {with_loc}")
        
        if total > 0:
            sample = await col.find_one({"location": {"$exists": True, "$ne": None}})
            if sample:
                print(f"SAMPLE_LOCATION: {sample.get('location')}")
            else:
                print("SAMPLE_LOCATION: None")
        else:
            print("DATABASE_EMPTY")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(verify_geo())
