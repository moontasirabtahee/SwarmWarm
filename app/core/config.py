import os
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

# JWT Config Parameters
JWT_SECRET_KEY = os.getenv("SWARMWARM_JWT_SECRET", "super_secret_jwt_signing_key_987654321")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
