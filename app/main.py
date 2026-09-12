
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from azure.cosmos import CosmosClient, PartitionKey


# ---------------------------------------------------------
# Load .env from project root
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


# ---------------------------------------------------------
# Cosmos DB configuration
# ---------------------------------------------------------

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "ContactDb")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "Contacts")


if not COSMOS_ENDPOINT or not COSMOS_KEY:
    raise RuntimeError(
        "COSMOS_ENDPOINT and COSMOS_KEY are required in .env"
    )


# ---------------------------------------------------------
# Cosmos DB connection
# ---------------------------------------------------------

cosmos_client = CosmosClient(
    COSMOS_ENDPOINT,
    credential=COSMOS_KEY
)

database = cosmos_client.create_database_if_not_exists(
    id=COSMOS_DATABASE
)

container = database.create_container_if_not_exists(
    id=COSMOS_CONTAINER,
    partition_key=PartitionKey(path="/partitionKey")
)


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="FastAPI Cosmos DB Contact Application",
    version="1.0.0"
)


# ---------------------------------------------------------
# Request model
# ---------------------------------------------------------

class ContactRequest(BaseModel):
    name: str
    phone: str


# ---------------------------------------------------------
# Home page
# ---------------------------------------------------------

@app.get("/")
def home():
    return FileResponse(
        BASE_DIR / "app" / "static" / "index.html"
    )


# ---------------------------------------------------------
# Display records page
# ---------------------------------------------------------

@app.get("/records")
def records_page():
    return FileResponse(
        BASE_DIR / "app" / "static" / "records.html"
    )


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "UP"
    }


# ---------------------------------------------------------
# Save contact
# ---------------------------------------------------------

@app.post("/contacts")
def create_contact(contact: ContactRequest):

    name = contact.name.strip()
    phone = contact.phone.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Name is required"
        )

    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required"
        )

    item = {
        "id": str(uuid4()),
        "name": name,
        "phone": phone,
        "partitionKey": "CONTACT",
        "createdAt": datetime.now(timezone.utc).isoformat()
    }

    try:

        created_item = container.create_item(
            body=item
        )

        return {
            "message": "Contact saved successfully",
            "data": created_item
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save contact: {str(e)}"
        )


# ---------------------------------------------------------
# Get all contacts
# ---------------------------------------------------------

@app.get("/contacts")
def get_contacts():

    try:

        query = """
        SELECT
            c.id,
            c.name,
            c.phone,
            c.createdAt
        FROM c
        ORDER BY c.createdAt DESC
        """

        items = list(
            container.query_items(
                query=query,
                enable_cross_partition_query=True
            )
        )

        return {
            "count": len(items),
            "data": items
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch contacts: {str(e)}"
        )