"""Lambda entry point for the API Gateway HTTP API."""

from mangum import Mangum

from app.api import app

handler = Mangum(app, lifespan="off")
